"""
StandardRepository - репозиторий для работы со стандартами в БД.
Бот работает только через этот репозиторий, не напрямую с интернетом.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class StandardRepository:
    """
    Репозиторий для работы со стандартами в БД.
    Единственная точка доступа бота к стандартам.
    """
    
    def __init__(self, db_session, cache_manager=None):
        """
        Инициализация репозитория.
        
        Args:
            db_session: SQLAlchemy сессия БД
            cache_manager: CacheManager (опционально)
        """
        self.db = db_session
        self.cache = cache_manager
    
    def find_by_code(self, family: str, code: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Найти стандарт по коду.
        
        Pipeline:
        1. Проверить кэш (если включен)
        2. Проверить БД
        3. Если нет → вернуть None (бот предложит скачать)
        
        Args:
            family: Семейство стандарта (ISO, DIN, GOST, OST...)
            code: Код стандарта
            use_cache: Использовать кэш
            
        Returns:
            Данные стандарта или None
        """
        # 1. Проверяем кэш
        if use_cache and self.cache:
            cached = self.cache.get(family, code)
            if cached:
                logger.debug(f"Standard found in cache: {family} {code}")
                return cached
        
        # 2. Проверяем БД
        if not self.db:
            logger.warning("DB session not available")
            return None
        
        try:
            from standards.database.models import Standard
            
            # Нормализуем family
            family_upper = family.upper()
            if family_upper == 'ОСТ':
                family_upper = 'OST'
            
            # Ищем стандарт
            standard = self.db.query(Standard).filter(
                Standard.family == family_upper,
                Standard.code == code
            ).first()
            
            if not standard:
                logger.debug(f"Standard not found in DB: {family} {code}")
                return None
            
            # Формируем результат
            result = {
                'id': str(standard.id),
                'family': standard.family,
                'code': standard.code,
                'full_code': standard.full_code,
                'title': standard.title,
                'country': standard.country,
                'year': standard.year,
                'version_hash': standard.version_hash,
                'status': standard.status,
                'needs_review': standard.needs_review,
                'last_updated': standard.last_updated.isoformat() if standard.last_updated else None
            }
            
            # Загружаем распарсенные данные (таблицы)
            if standard.tables:
                result['tables'] = [
                    {
                        'section': t.section_name,
                        'data': t.json_data,
                        'type': t.data_type
                    }
                    for t in standard.tables
                ]
            
            # Сохраняем в кэш
            if use_cache and self.cache:
                self.cache.set(family, code, result)
            
            logger.debug(f"Standard found in DB: {family} {code}")
            return result
        
        except Exception as e:
            logger.error(f"Error finding standard: {e}", exc_info=True)
            return None
    
    def mark_as_suspicious(self, standard_id: str) -> bool:
        """
        Пометить стандарт как подозрительный ("это не то").
        
        Args:
            standard_id: ID стандарта
            
        Returns:
            True если успешно
        """
        if not self.db:
            return False
        
        try:
            from standards.database.models import Standard, StandardStatus
            
            standard = self.db.query(Standard).filter(Standard.id == standard_id).first()
            if not standard:
                return False
            
            standard.needs_review = True
            standard.status = StandardStatus.SUSPICIOUS.value
            
            self.db.commit()
            
            # Инвалидируем кэш
            if self.cache:
                self.cache.delete(standard.family, standard.code)
            
            logger.info(f"Marked {standard.full_code} as suspicious")
            return True
        
        except Exception as e:
            logger.error(f"Error marking as suspicious: {e}", exc_info=True)
            self.db.rollback()
            return False
    
    def get_suspicious_standards(self) -> List[Dict[str, Any]]:
        """
        Получить список подозрительных стандартов (требующих проверки).
        
        Returns:
            Список стандартов с needs_review=True
        """
        if not self.db:
            return []
        
        try:
            from standards.database.models import Standard
            
            standards = self.db.query(Standard).filter(
                Standard.needs_review == True
            ).all()
            
            return [
                {
                    'id': str(s.id),
                    'full_code': s.full_code,
                    'status': s.status,
                    'last_updated': s.last_updated.isoformat() if s.last_updated else None
                }
                for s in standards
            ]
        
        except Exception as e:
            logger.error(f"Error getting suspicious standards: {e}", exc_info=True)
            return []
