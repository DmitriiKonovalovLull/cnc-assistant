"""
StandardManager - главный менеджер стандартов.
Управляет загрузкой, проверкой и хранением стандартов всех стран.
"""

import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from standards.registry.standard_family import StandardFamily

logger = logging.getLogger(__name__)


class StandardManager:
    """
    Главный менеджер стандартов.
    Координирует работу downloaders, validators и storage.
    """
    
    def __init__(self, storage_dir: Path = None):
        """
        Инициализация менеджера.
        
        Args:
            storage_dir: Директория для хранения стандартов
        """
        if storage_dir is None:
            storage_dir = Path(__file__).parent.parent.parent / "standards_cache"
        
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Создаем поддиректории для каждого семейства
        for family in StandardFamily:
            (self.storage_dir / family.value).mkdir(exist_ok=True)
        
        # Загружаем downloaders (будут созданы отдельно)
        self.downloaders = {}
        self._load_downloaders()
    
    def _load_downloaders(self):
        """Загрузить downloaders для каждого семейства."""
        # Импортируем downloaders
        try:
            from standards.downloader.iso_downloader import ISODownloader
            self.downloaders[StandardFamily.ISO] = ISODownloader(self.storage_dir / "ISO")
        except ImportError:
            logger.warning("ISODownloader not available")
        
        try:
            from standards.downloader.din_downloader import DINDownloader
            self.downloaders[StandardFamily.DIN] = DINDownloader(self.storage_dir / "DIN")
        except ImportError:
            logger.warning("DINDownloader not available")
        
        try:
            from standards.downloader.gost_downloader import GOSTDownloader
            self.downloaders[StandardFamily.GOST] = GOSTDownloader(self.storage_dir / "GOST")
        except ImportError:
            logger.warning("GOSTDownloader not available")
        
        try:
            from standards.downloader.ost_downloader import OSTDownloader
            self.downloaders[StandardFamily.OST] = OSTDownloader(self.storage_dir / "OST")
        except ImportError:
            logger.warning("OSTDownloader not available")
        
        # TODO: Добавить остальные downloaders
    
    def get_downloader(self, family: str):
        """
        Получить downloader для семейства.
        
        Args:
            family: Название семейства (ISO, DIN, GOST, OST...)
            
        Returns:
            Downloader или None
        """
        try:
            family_enum = StandardFamily[family.upper()]
            return self.downloaders.get(family_enum)
        except KeyError:
            return None
    
    def update_all(self) -> Dict[str, Any]:
        """
        Обновить все стандарты.
        
        Returns:
            Словарь с результатами обновления
        """
        results = {}
        
        logger.info("=== Updating all standards ===")
        
        for family in StandardFamily:
            family_name = family.value
            logger.info(f"Updating {family_name}...")
            
            downloader = self.downloaders.get(family)
            if not downloader:
                logger.warning(f"No downloader for {family_name}")
                results[family_name] = {
                    'success': False,
                    'error': 'No downloader available'
                }
                continue
            
            try:
                result = downloader.download_all()
                if result.get('success'):
                    count = result.get('count', 0)
                    logger.info(f"[OK] {family_name} downloaded ({count} standards)")
                    results[family_name] = {
                        'success': True,
                        'count': count
                    }
                else:
                    logger.error(f"[FAIL] {family_name}: {result.get('error', 'Unknown error')}")
                    results[family_name] = {
                        'success': False,
                        'error': result.get('error', 'Unknown error')
                    }
            except Exception as e:
                logger.error(f"[FAIL] {family_name}: {e}", exc_info=True)
                results[family_name] = {
                    'success': False,
                    'error': str(e)
                }
        
        # Проверяем целостность после обновления
        integrity_result = self.verify_integrity()
        results['integrity'] = integrity_result
        
        logger.info("=== Update complete ===")
        
        return results
    
    def verify_integrity(self) -> Dict[str, Any]:
        """
        Проверить целостность базы стандартов.
        
        Returns:
            Словарь с результатами проверки
        """
        logger.info("=== Verifying integrity ===")
        
        results = {
            'families': {},
            'total_standards': 0,
            'missing_files': [],
            'corrupted_files': [],
            'all_ok': True
        }
        
        for family in StandardFamily:
            family_name = family.value
            family_dir = self.storage_dir / family_name
            
            if not family_dir.exists():
                results['families'][family_name] = {
                    'count': 0,
                    'status': 'not_found'
                }
                continue
            
            # Подсчитываем файлы
            pdf_files = list(family_dir.glob("*.pdf"))
            json_files = list(family_dir.glob("*.json"))
            
            count = len(pdf_files)
            results['families'][family_name] = {
                'count': count,
                'status': 'ok' if count > 0 else 'empty'
            }
            results['total_standards'] += count
            
            # Проверяем целостность файлов (если есть валидатор)
            downloader = self.downloaders.get(family)
            if downloader and hasattr(downloader, 'verify_files'):
                try:
                    verification = downloader.verify_files()
                    if verification.get('missing'):
                        results['missing_files'].extend(verification['missing'])
                    if verification.get('corrupted'):
                        results['corrupted_files'].extend(verification['corrupted'])
                except Exception as e:
                    logger.warning(f"Verification failed for {family_name}: {e}")
        
        # Проверяем общий статус
        if results['missing_files'] or results['corrupted_files']:
            results['all_ok'] = False
        
        logger.info(f"Integrity check complete: {results['total_standards']} standards, "
                   f"{len(results['missing_files'])} missing, {len(results['corrupted_files'])} corrupted")
        
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """
        Получить статус базы стандартов.
        
        Returns:
            Словарь со статусом каждого семейства
        """
        status = {}
        
        for family in StandardFamily:
            family_name = family.value
            family_dir = self.storage_dir / family_name
            
            if not family_dir.exists():
                status[family_name] = {
                    'count': 0,
                    'status': 'not_found'
                }
                continue
            
            pdf_files = list(family_dir.glob("*.pdf"))
            count = len(pdf_files)
            
            status[family_name] = {
                'count': count,
                'status': 'ok' if count > 0 else 'empty'
            }
        
        return status
    
    def format_status_message(self) -> str:
        """
        Форматировать сообщение со статусом для пользователя.
        
        Returns:
            Отформатированное сообщение
        """
        status = self.get_status()
        integrity = self.verify_integrity()
        
        lines = ["=== <b>STANDARD SYSTEM CHECK</b> ===\n"]
        
        for family_name, info in status.items():
            count = info['count']
            status_icon = "✅" if count > 0 else "❌"
            
            # Проверяем наличие проблем
            if integrity.get('missing_files'):
                missing = [f for f in integrity['missing_files'] if family_name in f]
                if missing:
                    status_icon = "⚠️"
                    lines.append(f"{status_icon} {family_name}: {count} ({len(missing)} missing)")
                else:
                    lines.append(f"{status_icon} {family_name}: {count}")
            else:
                lines.append(f"{status_icon} {family_name}: {count}")
        
        lines.append("")
        
        if integrity.get('all_ok'):
            lines.append("Integrity: ✅ PASSED")
        else:
            lines.append("Integrity: ⚠️ ISSUES FOUND")
            if integrity.get('missing_files'):
                lines.append(f"Missing: {len(integrity['missing_files'])} files")
            if integrity.get('corrupted_files'):
                lines.append(f"Corrupted: {len(integrity['corrupted_files'])} files")
        
        lines.append("================================")
        
        return "\n".join(lines)
