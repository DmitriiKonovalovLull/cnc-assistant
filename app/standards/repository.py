"""
Repository для работы со стандартами в БД.
Единственная точка доступа к данным стандартов.
"""

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.standards.models import Standard, StandardData, StandardVersion
from app.core.config import settings

logger = logging.getLogger(__name__)


class StandardRepository:
    """
    Репозиторий для работы со стандартами.
    Инкапсулирует всю логику работы с БД.
    """
    
    def __init__(self, db: Session):
        """
        Инициализация репозитория.
        
        Args:
            db: SQLAlchemy сессия
        """
        self.db = db
    
    def get_by_code(self, family: str, code: str) -> Optional[Standard]:
        """
        Найти стандарт по семейству и коду.
        
        Args:
            family: Семейство стандарта
            code: Код стандарта
            
        Returns:
            Standard или None
        """
        return self.db.query(Standard).filter(
            Standard.family == family.upper(),
            Standard.code == code
        ).first()
    
    def get_by_id(self, standard_id: UUID) -> Optional[Standard]:
        """
        Найти стандарт по ID.
        
        Args:
            standard_id: UUID стандарта
            
        Returns:
            Standard или None
        """
        return self.db.query(Standard).filter(Standard.id == standard_id).first()
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[Standard]:
        """
        Получить все стандарты с пагинацией.
        
        Args:
            skip: Пропустить записей
            limit: Максимум записей
            
        Returns:
            Список стандартов
        """
        return self.db.query(Standard).offset(skip).limit(limit).all()
    
    def get_by_family(self, family: str) -> List[Standard]:
        """
        Получить стандарты по семейству.
        
        Args:
            family: Семейство стандарта
            
        Returns:
            Список стандартов
        """
        return self.db.query(Standard).filter(Standard.family == family.upper()).all()
    
    def create(self, standard_data: Dict[str, Any]) -> Standard:
        """
        Создать новый стандарт.
        
        Args:
            standard_data: Данные стандарта
            
        Returns:
            Созданный Standard
        """
        standard = Standard(**standard_data)
        self.db.add(standard)
        self.db.commit()
        self.db.refresh(standard)
        return standard
    
    def update(self, standard: Standard, update_data: Dict[str, Any]) -> Standard:
        """
        Обновить стандарт.
        
        Args:
            standard: Объект Standard
            update_data: Данные для обновления
            
        Returns:
            Обновленный Standard
        """
        for key, value in update_data.items():
            setattr(standard, key, value)
        
        standard.last_updated = datetime.utcnow()
        self.db.commit()
        self.db.refresh(standard)
        return standard
    
    def mark_for_review(self, standard_id: UUID) -> bool:
        """
        Пометить стандарт для проверки.
        
        Args:
            standard_id: UUID стандарта
            
        Returns:
            True если успешно
        """
        standard = self.get_by_id(standard_id)
        if not standard:
            return False
        
        standard.needs_review = True
        self.db.commit()
        return True
    
    def get_needing_update_check(self) -> List[Standard]:
        """
        Получить стандарты, требующие проверки обновлений.
        
        Returns:
            Список стандартов с last_checked > UPDATE_CHECK_INTERVAL_DAYS дней назад
        """
        cutoff_date = datetime.utcnow() - timedelta(days=settings.UPDATE_CHECK_INTERVAL_DAYS)
        
        return self.db.query(Standard).filter(
            Standard.last_checked < cutoff_date
        ).all()
    
    def add_data(self, standard_id: UUID, section_name: str, data: Dict[str, Any], 
                  data_type: Optional[str] = None, page_number: Optional[int] = None) -> StandardData:
        """
        Добавить структурированные данные к стандарту.
        
        Args:
            standard_id: UUID стандарта
            section_name: Название раздела
            data: Данные (JSON)
            data_type: Тип данных
            page_number: Номер страницы
            
        Returns:
            Созданный StandardData
        """
        standard_data = StandardData(
            standard_id=standard_id,
            section_name=section_name,
            data=data,
            data_type=data_type,
            page_number=page_number
        )
        self.db.add(standard_data)
        self.db.commit()
        self.db.refresh(standard_data)
        return standard_data
    
    def get_data(self, standard_id: UUID) -> List[StandardData]:
        """
        Получить все данные стандарта.
        
        Args:
            standard_id: UUID стандарта
            
        Returns:
            Список StandardData
        """
        return self.db.query(StandardData).filter(
            StandardData.standard_id == standard_id
        ).all()
    
    def add_version(self, standard_id: UUID, version_hash: str, file_path: str,
                    file_size: Optional[int] = None, version_metadata: Optional[Dict[str, Any]] = None) -> StandardVersion:
        """
        Добавить версию стандарта.
        
        Args:
            standard_id: UUID стандарта
            version_hash: SHA256 хеш версии
            file_path: Путь к файлу
            file_size: Размер файла
            version_metadata: Метаданные версии
            
        Returns:
            Созданный StandardVersion
        """
        version = StandardVersion(
            standard_id=standard_id,
            version_hash=version_hash,
            file_path=file_path,
            file_size=file_size,
            version_metadata=version_metadata or {}
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        return version
    
    def get_versions(self, standard_id: UUID) -> List[StandardVersion]:
        """
        Получить все версии стандарта.
        
        Args:
            standard_id: UUID стандарта
            
        Returns:
            Список версий
        """
        return self.db.query(StandardVersion).filter(
            StandardVersion.standard_id == standard_id
        ).order_by(StandardVersion.created_at.desc()).all()
    
    def find_by_hash(self, version_hash: str) -> Optional[Standard]:
        """
        Найти стандарт по хешу версии.
        
        Args:
            version_hash: SHA256 хеш
            
        Returns:
            Standard или None
        """
        return self.db.query(Standard).filter(
            Standard.version_hash == version_hash
        ).first()
