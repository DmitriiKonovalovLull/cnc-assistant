"""
StandardManager - главный менеджер системы стандартов.
Управляет загрузкой, обновлением, проверкой целостности.
"""

import logging
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.standards.models import Standard, StandardVersion
from app.standards.repository import StandardRepository
from app.standards.parser import PDFParser
from app.core.config import settings

logger = logging.getLogger(__name__)


class StandardManager:
    """
    Менеджер стандартов.
    Координирует работу repository, parser, versioning.
    """
    
    def __init__(self, db: Session):
        """
        Инициализация менеджера.
        
        Args:
            db: SQLAlchemy сессия
        """
        self.db = db
        self.repository = StandardRepository(db)
        self.parser = PDFParser()
    
    def calculate_hash(self, file_path: Path) -> str:
        """
        Вычислить SHA256 хеш файла.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            SHA256 хеш в hex формате
        """
        sha256_hash = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        return sha256_hash.hexdigest()
    
    def get_standard(self, family: str, code: str) -> Optional[Dict[str, Any]]:
        """
        Получить стандарт по семейству и коду.
        
        Args:
            family: Семейство стандарта
            code: Код стандарта
            
        Returns:
            Данные стандарта или None
        """
        standard = self.repository.get_by_code(family.upper(), code)
        if not standard:
            return None
        
        # Загружаем данные и версии
        data = self.repository.get_data(standard.id)
        versions = self.repository.get_versions(standard.id)
        
        return {
            'id': str(standard.id),
            'family': standard.family,
            'code': standard.code,
            'full_code': standard.full_code,
            'title': standard.title,
            'version_hash': standard.version_hash,
            'needs_review': standard.needs_review,
            'data': [
                {
                    'section': d.section_name,
                    'data': d.data,
                    'type': d.data_type
                }
                for d in data
            ],
            'versions_count': len(versions)
        }
    
    def upload_standard(
        self,
        file_path: Path,
        family: str,
        code: str,
        full_code: str,
        title: Optional[str] = None,
        country: Optional[str] = None,
        revision: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Загрузить стандарт из PDF файла.
        
        Flow:
        1. Вычислить SHA256
        2. Проверить есть ли стандарт с таким hash
        3. Если нет:
           - сохранить файл
           - распарсить
           - извлечь таблицы
           - сохранить JSON в StandardData
           - создать StandardVersion
        
        Args:
            file_path: Путь к загруженному PDF
            family: Семейство стандарта
            code: Код стандарта
            full_code: Полный код
            title: Название (опционально)
            country: Страна (опционально)
            revision: Ревизия (опционально)
            
        Returns:
            Словарь с результатом загрузки
        """
        try:
            # 1. Вычисляем хеш
            version_hash = self.calculate_hash(file_path)
            logger.info(f"Calculated hash for {full_code}: {version_hash[:16]}...")
            
            # 2. Проверяем есть ли стандарт с таким hash
            existing = self.repository.find_by_hash(version_hash)
            if existing:
                logger.info(f"Standard {full_code} already exists with same hash")
                return {
                    'success': True,
                    'standard_id': existing.id,
                    'message': f'Стандарт {full_code} уже существует',
                    'version_hash': version_hash,
                    'is_new': False
                }
            
            # 3. Сохраняем файл в хранилище
            storage_path = self._save_file(file_path, family, code, version_hash)
            
            # 4. Парсим PDF
            logger.info(f"Parsing PDF: {file_path.name}")
            parsed_data = self.parser.parse(file_path)
            
            # 5. Создаем стандарт
            standard_data = {
                'family': family.upper(),
                'code': code,
                'full_code': full_code,
                'title': title,
                'country': country,
                'revision': revision,
                'version_hash': version_hash,
                'source': 'user_upload',
                'needs_review': False
            }
            
            standard = self.repository.create(standard_data)
            logger.info(f"Created standard: {standard.id}")
            
            # 6. Сохраняем версию
            self.repository.add_version(
                standard_id=standard.id,
                version_hash=version_hash,
                file_path=str(storage_path),
                file_size=file_path.stat().st_size,
                version_metadata={'uploaded_at': datetime.utcnow().isoformat()}
            )
            
            # 7. Сохраняем распарсенные данные
            self._save_parsed_data(standard.id, parsed_data)
            
            logger.info(f"Successfully uploaded standard: {full_code}")
            
            return {
                'success': True,
                'standard_id': standard.id,
                'message': f'Стандарт {full_code} успешно загружен',
                'version_hash': version_hash,
                'is_new': True
            }
        
        except Exception as e:
            logger.error(f"Error uploading standard: {e}", exc_info=True)
            self.db.rollback()
            return {
                'success': False,
                'message': f'Ошибка загрузки: {str(e)}',
                'standard_id': None
            }
    
    def _save_file(self, file_path: Path, family: str, code: str, version_hash: str) -> Path:
        """
        Сохранить файл в хранилище.
        
        Args:
            file_path: Исходный файл
            family: Семейство
            code: Код
            version_hash: Хеш версии
            
        Returns:
            Путь к сохраненному файлу
        """
        # Создаем структуру: storage/{family}/{code}_{hash}.pdf
        family_dir = settings.STANDARDS_STORAGE_DIR / family.upper()
        family_dir.mkdir(parents=True, exist_ok=True)
        
        storage_path = family_dir / f"{code}_{version_hash[:16]}.pdf"
        
        # Копируем файл
        import shutil
        shutil.copy2(file_path, storage_path)
        
        logger.debug(f"Saved file to: {storage_path}")
        return storage_path
    
    def _save_parsed_data(self, standard_id: UUID, parsed_data: Dict[str, Any]) -> None:
        """
        Сохранить распарсенные данные в БД.
        
        Args:
            standard_id: UUID стандарта
            parsed_data: Распарсенные данные
        """
        # Сохраняем таблицы
        for table in parsed_data.get('tables', []):
            self.repository.add_data(
                standard_id=standard_id,
                section_name=f"table_{table.get('page', 0)}_{table.get('table_number', 0)}",
                data=table,
                data_type='table',
                page_number=table.get('page')
            )
        
        # Сохраняем структурированные данные
        if parsed_data.get('threads'):
            self.repository.add_data(
                standard_id=standard_id,
                section_name='threads',
                data=parsed_data['threads'],
                data_type='parameters'
            )
        
        if parsed_data.get('dimensions'):
            self.repository.add_data(
                standard_id=standard_id,
                section_name='dimensions',
                data=parsed_data['dimensions'],
                data_type='parameters'
            )
        
        if parsed_data.get('tolerances'):
            self.repository.add_data(
                standard_id=standard_id,
                section_name='tolerances',
                data=parsed_data['tolerances'],
                data_type='parameters'
            )
    
    def check_updates(self, force: bool = False) -> Dict[str, Any]:
        """
        Проверить обновления стандартов.
        
        В public режиме только проверяет метаданные (заглушка).
        В enterprise режиме может использовать API.
        
        Args:
            force: Принудительная проверка всех
            
        Returns:
            Словарь с результатами проверки
        """
        if settings.MODE == "public":
            # В public режиме только проверяем метаданные локально
            return self._check_updates_public(force)
        else:
            # В enterprise режиме можно использовать API
            return self._check_updates_enterprise(force)
    
    def _check_updates_public(self, force: bool) -> Dict[str, Any]:
        """
        Проверка обновлений в public режиме.
        Только локальная проверка метаданных.
        
        Args:
            force: Принудительная проверка
            
        Returns:
            Результаты проверки
        """
        if force:
            standards = self.repository.get_all(limit=1000)
        else:
            standards = self.repository.get_needing_update_check()
        
        results = {
            'checked': 0,
            'updated': 0,
            'unchanged': 0,
            'errors': 0,
            'details': []
        }
        
        for standard in standards:
            try:
                # В public режиме только обновляем last_checked
                # Реальная проверка обновлений требует API или ручной загрузки
                standard.last_checked = datetime.utcnow()
                self.db.commit()
                
                results['checked'] += 1
                results['unchanged'] += 1
                results['details'].append({
                    'standard': standard.full_code,
                    'status': 'checked',
                    'note': 'Public mode - manual update required'
                })
            
            except Exception as e:
                logger.error(f"Error checking {standard.full_code}: {e}")
                results['errors'] += 1
                results['details'].append({
                    'standard': standard.full_code,
                    'status': 'error',
                    'error': str(e)
                })
        
        return results
    
    def _check_updates_enterprise(self, force: bool) -> Dict[str, Any]:
        """
        Проверка обновлений в enterprise режиме.
        Может использовать официальный API.
        
        Args:
            force: Принудительная проверка
            
        Returns:
            Результаты проверки
        """
        # TODO: Реализовать проверку через API если доступен
        # Пока используем public логику
        return self._check_updates_public(force)
    
    def mark_for_review(self, standard_id: UUID) -> bool:
        """
        Пометить стандарт для проверки.
        
        Args:
            standard_id: UUID стандарта
            
        Returns:
            True если успешно
        """
        return self.repository.mark_for_review(standard_id)
    
    def verify_integrity(self) -> Dict[str, Any]:
        """
        Проверить целостность базы стандартов.
        
        Returns:
            Словарь с результатами проверки
        """
        standards = self.repository.get_all(limit=1000)
        
        results = {
            'total_standards': len(standards),
            'missing_files': 0,
            'corrupted_files': 0,
            'all_ok': True,
            'details': []
        }
        
        for standard in standards:
            # Получаем последнюю версию
            versions = self.repository.get_versions(standard.id)
            if not versions:
                results['missing_files'] += 1
                results['details'].append({
                    'standard': standard.full_code,
                    'issue': 'no_versions'
                })
                continue
            
            latest_version = versions[0]
            file_path = Path(latest_version.file_path)
            
            # Проверяем наличие файла
            if not file_path.exists():
                results['missing_files'] += 1
                results['details'].append({
                    'standard': standard.full_code,
                    'issue': 'file_missing',
                    'path': str(file_path)
                })
                continue
            
            # Проверяем хеш
            try:
                current_hash = self.calculate_hash(file_path)
                if current_hash != latest_version.version_hash:
                    results['corrupted_files'] += 1
                    results['details'].append({
                        'standard': standard.full_code,
                        'issue': 'hash_mismatch',
                        'expected': latest_version.version_hash[:16],
                        'actual': current_hash[:16]
                    })
            except Exception as e:
                results['corrupted_files'] += 1
                results['details'].append({
                    'standard': standard.full_code,
                    'issue': 'hash_check_failed',
                    'error': str(e)
                })
        
        results['all_ok'] = results['missing_files'] == 0 and results['corrupted_files'] == 0
        
        return results
