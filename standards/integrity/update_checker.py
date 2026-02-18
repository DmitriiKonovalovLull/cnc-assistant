"""
UpdateChecker - проверка обновлений стандартов.
Проверяет раз в 6 месяцев (180 дней).
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Интервал проверки (180 дней = ~6 месяцев)
CHECK_INTERVAL_DAYS = 180


class UpdateChecker:
    """
    Проверка обновлений стандартов.
    Работает с БД, не напрямую с интернетом.
    """
    
    def __init__(self, db_session, downloader_manager):
        """
        Инициализация проверщика обновлений.
        
        Args:
            db_session: SQLAlchemy сессия БД
            downloader_manager: Менеджер downloaders
        """
        self.db = db_session
        self.downloader_manager = downloader_manager
    
    def check_updates(self, force: bool = False) -> Dict[str, Any]:
        """
        Проверить обновления всех стандартов.
        
        Args:
            force: Принудительная проверка (игнорировать интервал)
            
        Returns:
            Словарь с результатами проверки
        """
        if not self.db:
            logger.error("DB session not available")
            return {'error': 'DB session not available'}
        
        try:
            from standards.database.models import Standard
            from standards.versioning.version_manager import VersionManager
            
            version_manager = VersionManager(self.db)
            
            # Получаем стандарты для проверки
            if force:
                standards = self.db.query(Standard).filter(
                    Standard.status != StandardStatus.DEPRECATED.value
                ).all()
            else:
                # Только те, что не проверялись более CHECK_INTERVAL_DAYS дней
                cutoff_date = datetime.utcnow() - timedelta(days=CHECK_INTERVAL_DAYS)
                standards = self.db.query(Standard).filter(
                    Standard.status != StandardStatus.DEPRECATED.value,
                    Standard.last_checked < cutoff_date
                ).all()
            
            logger.info(f"Checking {len(standards)} standards for updates...")
            
            results = {
                'checked': 0,
                'updated': 0,
                'unchanged': 0,
                'errors': 0,
                'details': []
            }
            
            for standard in standards:
                try:
                    result = self.check_standard_update(standard, version_manager)
                    results['checked'] += 1
                    
                    if result['updated']:
                        results['updated'] += 1
                    elif result['unchanged']:
                        results['unchanged'] += 1
                    else:
                        results['errors'] += 1
                    
                    results['details'].append(result)
                
                except Exception as e:
                    logger.error(f"Error checking {standard.full_code}: {e}", exc_info=True)
                    results['errors'] += 1
                    results['details'].append({
                        'standard': standard.full_code,
                        'error': str(e)
                    })
            
            logger.info(
                f"Update check complete: {results['checked']} checked, "
                f"{results['updated']} updated, {results['unchanged']} unchanged, "
                f"{results['errors']} errors"
            )
            
            return results
        
        except Exception as e:
            logger.error(f"Error in check_updates: {e}", exc_info=True)
            return {'error': str(e)}
    
    def check_standard_update(
        self,
        standard,
        version_manager
    ) -> Dict[str, Any]:
        """
        Проверить обновление конкретного стандарта.
        
        Args:
            standard: Объект Standard из БД
            version_manager: VersionManager
            
        Returns:
            Словарь с результатом проверки
        """
        logger.debug(f"Checking update for {standard.family} {standard.code}")
        
        try:
            # Получаем downloader для семейства
            downloader = self.downloader_manager.get_downloader(standard.family)
            if not downloader:
                return {
                    'standard': standard.full_code,
                    'updated': False,
                    'unchanged': False,
                    'error': f'No downloader for {standard.family}'
                }
            
            # Пытаемся скачать новую версию
            # ВАЖНО: В production это должно быть через управляемый каталог,
            # а не массовое скачивание
            new_file_path = downloader.download_standard(standard.code)
            
            if not new_file_path or not new_file_path.exists():
                # Файл недоступен - обновляем только last_checked
                standard.last_checked = datetime.utcnow()
                self.db.commit()
                
                return {
                    'standard': standard.full_code,
                    'updated': False,
                    'unchanged': True,
                    'note': 'File not available for download'
                }
            
            # Вычисляем хеш новой версии
            new_hash = version_manager.calculate_hash(new_file_path)
            
            # Проверяем, изменилась ли версия
            if new_hash != standard.version_hash:
                # Версия изменилась - сохраняем новую версию
                version_manager.save_new_version(
                    standard_id=str(standard.id),
                    version_hash=new_hash,
                    file_path=new_file_path
                )
                
                # Обновляем last_checked
                standard.last_checked = datetime.utcnow()
                self.db.commit()
                
                logger.info(f"[UPDATED] {standard.full_code}")
                
                return {
                    'standard': standard.full_code,
                    'updated': True,
                    'unchanged': False,
                    'old_hash': standard.version_hash[:16],
                    'new_hash': new_hash[:16]
                }
            else:
                # Версия не изменилась
                standard.last_checked = datetime.utcnow()
                self.db.commit()
                
                logger.debug(f"[OK] {standard.full_code}")
                
                return {
                    'standard': standard.full_code,
                    'updated': False,
                    'unchanged': True
                }
        
        except Exception as e:
            logger.error(f"Error checking {standard.full_code}: {e}", exc_info=True)
            return {
                'standard': standard.full_code,
                'updated': False,
                'unchanged': False,
                'error': str(e)
            }
    
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
            
            logger.info(f"Marked {standard.full_code} as suspicious")
            
            return True
        
        except Exception as e:
            logger.error(f"Error marking as suspicious: {e}", exc_info=True)
            self.db.rollback()
            return False
    
    def force_recheck(self, standard_id: str) -> Dict[str, Any]:
        """
        Принудительная перепроверка стандарта.
        Используется когда пользователь говорит "это не то".
        
        Args:
            standard_id: ID стандарта
            
        Returns:
            Результат перепроверки
        """
        if not self.db:
            return {'error': 'DB session not available'}
        
        try:
            from standards.database.models import Standard
            from standards.versioning.version_manager import VersionManager
            
            standard = self.db.query(Standard).filter(Standard.id == standard_id).first()
            if not standard:
                return {'error': 'Standard not found'}
            
            version_manager = VersionManager(self.db)
            result = self.check_standard_update(standard, version_manager)
            
            # Снимаем флаг needs_review если обновление успешно
            if result.get('updated') or result.get('unchanged'):
                standard.needs_review = False
                if standard.status == StandardStatus.SUSPICIOUS.value:
                    standard.status = StandardStatus.ACTIVE.value
                self.db.commit()
            
            return result
        
        except Exception as e:
            logger.error(f"Error in force_recheck: {e}", exc_info=True)
            return {'error': str(e)}
