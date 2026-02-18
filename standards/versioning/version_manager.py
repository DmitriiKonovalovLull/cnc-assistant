"""
VersionManager - управление версиями стандартов через SHA256 hash.
"""

import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class VersionManager:
    """
    Менеджер версий стандартов.
    Использует SHA256 для определения изменений.
    """
    
    def __init__(self, db_session=None):
        """
        Инициализация менеджера версий.
        
        Args:
            db_session: SQLAlchemy сессия БД
        """
        self.db = db_session
    
    def calculate_hash(self, file_path: Path) -> str:
        """
        Вычислить SHA256 хеш файла.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            SHA256 хеш в hex формате
        """
        sha256_hash = hashlib.sha256()
        
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            raise
    
    def calculate_hash_from_bytes(self, data: bytes) -> str:
        """
        Вычислить SHA256 хеш из байтов.
        
        Args:
            data: Данные файла в байтах
            
        Returns:
            SHA256 хеш в hex формате
        """
        return hashlib.sha256(data).hexdigest()
    
    def check_version_changed(
        self,
        standard_id: str,
        new_hash: str,
        family: str,
        code: str
    ) -> bool:
        """
        Проверить, изменилась ли версия стандарта.
        
        Args:
            standard_id: ID стандарта в БД (UUID)
            new_hash: Новый SHA256 хеш
            family: Семейство стандарта
            code: Код стандарта
            
        Returns:
            True если версия изменилась
        """
        if not self.db:
            logger.warning("DB session not available, cannot check version")
            return False
        
        try:
            from standards.database.models import Standard
            
            # Ищем стандарт
            if standard_id:
                standard = self.db.query(Standard).filter(Standard.id == standard_id).first()
            else:
                standard = self.db.query(Standard).filter(
                    Standard.family == family,
                    Standard.code == code
                ).first()
            
            if not standard:
                # Стандарт не найден - это новая версия
                return True
            
            # Сравниваем хеши
            if standard.version_hash != new_hash:
                logger.info(
                    f"Version changed for {family} {code}: "
                    f"old={standard.version_hash[:16]}..., new={new_hash[:16]}..."
                )
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"Error checking version: {e}", exc_info=True)
            return False
    
    def save_new_version(
        self,
        standard_id: str,
        version_hash: str,
        file_path: Path,
        published_date: Optional[date] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Сохранить новую версию стандарта.
        
        Args:
            standard_id: ID стандарта
            version_hash: SHA256 хеш версии
            file_path: Путь к файлу
            published_date: Дата публикации
            metadata: Дополнительные метаданные
            
        Returns:
            ID новой версии или None
        """
        if not self.db:
            logger.warning("DB session not available, cannot save version")
            return None
        
        try:
            from standards.database.models import Standard, StandardVersion
            
            standard = self.db.query(Standard).filter(Standard.id == standard_id).first()
            if not standard:
                logger.error(f"Standard {standard_id} not found")
                return None
            
            # Создаем новую версию
            file_size = file_path.stat().st_size if file_path.exists() else 0
            
            new_version = StandardVersion(
                standard_id=standard_id,
                version_hash=version_hash,
                published_date=published_date,
                file_path=str(file_path),
                file_size=file_size,
                metadata=metadata or {}
            )
            
            self.db.add(new_version)
            
            # Обновляем стандарт
            from standards.database.models import StandardStatus
            
            standard.version_hash = version_hash
            standard.last_updated = datetime.utcnow()
            standard.status = StandardStatus.UPDATED.value
            
            self.db.commit()
            
            logger.info(f"Saved new version for {standard.family} {standard.code}: {version_hash[:16]}...")
            
            return str(new_version.id)
        
        except Exception as e:
            logger.error(f"Error saving version: {e}", exc_info=True)
            self.db.rollback()
            return None
    
    def get_version_history(self, standard_id: str) -> list:
        """
        Получить историю версий стандарта.
        
        Args:
            standard_id: ID стандарта
            
        Returns:
            Список версий
        """
        if not self.db:
            return []
        
        try:
            from standards.database.models import StandardVersion
            
            versions = self.db.query(StandardVersion).filter(
                StandardVersion.standard_id == standard_id
            ).order_by(StandardVersion.created_at.desc()).all()
            
            return [
                {
                    'id': str(v.id),
                    'hash': v.version_hash,
                    'published_date': v.published_date.isoformat() if v.published_date else None,
                    'created_at': v.created_at.isoformat(),
                    'file_size': v.file_size
                }
                for v in versions
            ]
        
        except Exception as e:
            logger.error(f"Error getting version history: {e}", exc_info=True)
            return []
