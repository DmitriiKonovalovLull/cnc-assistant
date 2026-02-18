"""
FastAPI routes для работы со стандартами.
"""

import logging
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.standards.schemas import (
    StandardResponse, StandardFullResponse, UploadResponse,
    IntegrityCheckResponse, UpdateCheckResponse
)
from app.standards.manager import StandardManager
from app.standards.cache import CacheManager
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/standards", tags=["standards"])

# Глобальный cache manager (инициализируется при первом использовании)
_cache_manager: Optional[CacheManager] = None

def get_cache_manager() -> Optional[CacheManager]:
    """Получить cache manager (singleton)."""
    global _cache_manager
    if _cache_manager is None and settings.REDIS_ENABLED:
        _cache_manager = CacheManager()
    return _cache_manager


@router.get("/", response_model=List[StandardResponse])
def list_standards(
    family: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Получить список стандартов.
    
    Args:
        family: Фильтр по семейству (опционально)
        skip: Пропустить записей
        limit: Максимум записей
        db: Сессия БД
        
    Returns:
        Список стандартов
    """
    from app.standards.repository import StandardRepository
    
    repository = StandardRepository(db)
    
    if family:
        standards = repository.get_by_family(family)
    else:
        standards = repository.get_all(skip=skip, limit=limit)
    
    return standards


@router.get("/{family}/{code}", response_model=StandardFullResponse)
def get_standard(
    family: str,
    code: str,
    db: Session = Depends(get_db)
):
    """
    Получить стандарт по семейству и коду.
    
    Pipeline: Cache → Database
    
    Args:
        family: Семейство стандарта
        code: Код стандарта
        db: Сессия БД
        
    Returns:
        Данные стандарта
    """
    manager = StandardManager(db)
    cache_manager = get_cache_manager()
    
    # Проверяем кэш
    if cache_manager:
        cached = cache_manager.get(family, code)
        if cached:
            return cached
    
    # Ищем в БД
    standard_data = manager.get_standard(family, code)
    
    if not standard_data:
        raise HTTPException(status_code=404, detail=f"Standard {family} {code} not found")
    
    # Сохраняем в кэш
    if cache_manager:
        cache_manager.set(family, code, standard_data)
    
    return standard_data


@router.post("/upload", response_model=UploadResponse)
async def upload_standard(
    file: UploadFile = File(..., description="PDF файл стандарта"),
    family: str = Form(..., description="Семейство стандарта (ISO, DIN, GOST, OST...)"),
    code: str = Form(..., description="Код стандарта (например, 33056-80)"),
    full_code: str = Form(..., description="Полный код (например, ОСТ 1 33056-80)"),
    title: Optional[str] = Form(None, description="Название стандарта"),
    country: Optional[str] = Form(None, description="Страна/организация"),
    revision: Optional[str] = Form(None, description="Ревизия"),
    db: Session = Depends(get_db)
):
    """
    Загрузить стандарт из PDF файла.
    
    Flow:
    1. Принять PDF
    2. Вычислить SHA256
    3. Проверить есть ли стандарт с таким hash
    4. Если нет:
       - сохранить файл
       - распарсить
       - извлечь таблицы
       - сохранить JSON в StandardData
       - создать StandardVersion
    
    Args:
        file: PDF файл
        family: Семейство стандарта
        code: Код стандарта
        full_code: Полный код
        title: Название (опционально)
        country: Страна (опционально)
        revision: Ревизия (опционально)
        db: Сессия БД
        
    Returns:
        Результат загрузки
    """
    # Проверяем что это PDF
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be PDF")
    
    # Сохраняем временный файл
    temp_path = settings.STANDARDS_UPLOAD_DIR / file.filename
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Сохраняем загруженный файл
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Загружаем через менеджер
        manager = StandardManager(db)
        result = manager.upload_standard(
            file_path=temp_path,
            family=family,
            code=code,
            full_code=full_code,
            title=title,
            country=country,
            revision=revision
        )
        
        # Инвалидируем кэш
        cache_manager = get_cache_manager()
        if cache_manager:
            cache_manager.delete(family, code)
        
        return UploadResponse(
            success=result['success'],
            standard_id=result.get('standard_id'),
            message=result['message'],
            version_hash=result.get('version_hash')
        )
    
    except Exception as e:
        logger.error(f"Error uploading standard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    
    finally:
        # Удаляем временный файл
        if temp_path.exists():
            temp_path.unlink()


@router.post("/{standard_id}/mark-review")
def mark_for_review(
    standard_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Пометить стандарт для проверки ("это не то").
    
    Args:
        standard_id: UUID стандарта
        db: Сессия БД
        
    Returns:
        Результат операции
    """
    manager = StandardManager(db)
    
    if manager.mark_for_review(standard_id):
        # Инвалидируем кэш
        cache_manager = get_cache_manager()
        standard = manager.repository.get_by_id(standard_id)
        if standard and cache_manager:
            cache_manager.delete(standard.family, standard.code)
        
        return {"success": True, "message": "Standard marked for review"}
    else:
        raise HTTPException(status_code=404, detail="Standard not found")


@router.post("/check-updates", response_model=UpdateCheckResponse)
def check_updates(
    force: bool = False,
    db: Session = Depends(get_db)
):
    """
    Проверить обновления стандартов.
    
    Args:
        force: Принудительная проверка всех
        db: Сессия БД
        
    Returns:
        Результаты проверки
    """
    manager = StandardManager(db)
    results = manager.check_updates(force=force)
    
    return UpdateCheckResponse(**results)


@router.get("/integrity/check", response_model=IntegrityCheckResponse)
def verify_integrity(db: Session = Depends(get_db)):
    """
    Проверить целостность базы стандартов.
    
    Args:
        db: Сессия БД
        
    Returns:
        Результаты проверки целостности
    """
    manager = StandardManager(db)
    results = manager.verify_integrity()
    
    return IntegrityCheckResponse(**results)
