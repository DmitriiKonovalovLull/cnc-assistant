"""
Базовый класс для downloaders стандартов.
"""

import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseDownloader(ABC):
    """
    Базовый класс для загрузки стандартов.
    Каждый downloader для конкретной страны наследуется от этого класса.
    """
    
    def __init__(self, storage_dir: Path):
        """
        Инициализация downloader.
        
        Args:
            storage_dir: Директория для хранения стандартов этого семейства
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    @abstractmethod
    def fetch_list(self) -> List[Dict[str, Any]]:
        """
        Получить список доступных стандартов.
        
        Returns:
            Список словарей с информацией о стандартах
        """
        pass
    
    @abstractmethod
    def download_standard(self, standard_id: str) -> Optional[Path]:
        """
        Скачать конкретный стандарт.
        
        Args:
            standard_id: ID стандарта
            
        Returns:
            Путь к скачанному файлу или None
        """
        pass
    
    def download_all(self) -> Dict[str, Any]:
        """
        Скачать все доступные стандарты.
        
        Returns:
            Словарь с результатами загрузки
        """
        logger.info(f"Starting download for {self.__class__.__name__}")
        
        try:
            standards_list = self.fetch_list()
            if not standards_list:
                return {
                    'success': False,
                    'error': 'No standards list available',
                    'count': 0
                }
            
            downloaded = 0
            failed = 0
            
            for standard_info in standards_list:
                standard_id = standard_info.get('id') or standard_info.get('code')
                if not standard_id:
                    continue
                
                try:
                    result = self.download_standard(standard_id)
                    if result:
                        downloaded += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.warning(f"Failed to download {standard_id}: {e}")
                    failed += 1
            
            return {
                'success': True,
                'count': downloaded,
                'failed': failed,
                'total': len(standards_list)
            }
        
        except Exception as e:
            logger.error(f"Error in download_all: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'count': 0
            }
    
    def validate_pdf(self, file_path: Path) -> bool:
        """
        Проверить валидность PDF файла.
        
        Args:
            file_path: Путь к PDF файлу
            
        Returns:
            True если файл валиден
        """
        if not file_path.exists():
            return False
        
        # Базовая проверка: файл существует и не пустой
        if file_path.stat().st_size == 0:
            return False
        
        # Проверяем что это PDF (первые байты)
        try:
            with open(file_path, 'rb') as f:
                header = f.read(4)
                if header != b'%PDF':
                    return False
        except Exception:
            return False
        
        return True
    
    def calculate_sha(self, file_path: Path) -> str:
        """
        Вычислить SHA256 хеш файла.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            SHA256 хеш
        """
        import hashlib
        
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def store_metadata(self, standard_id: str, metadata: Dict[str, Any]) -> None:
        """
        Сохранить метаданные стандарта.
        
        Args:
            standard_id: ID стандарта
            metadata: Метаданные
        """
        metadata_file = self.storage_dir / "metadata.json"
        
        import json
        metadata_dict = {}
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata_dict = json.load(f)
            except Exception:
                pass
        
        metadata_dict[standard_id] = metadata
        
        try:
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata_dict, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")
    
    def verify_files(self) -> Dict[str, List[str]]:
        """
        Проверить целостность файлов.
        
        Returns:
            Словарь с списками missing и corrupted файлов
        """
        result = {
            'missing': [],
            'corrupted': []
        }
        
        metadata_file = self.storage_dir / "metadata.json"
        if not metadata_file.exists():
            return result
        
        import json
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata_dict = json.load(f)
            
            for standard_id, metadata in metadata_dict.items():
                file_path = Path(metadata.get('file_path', ''))
                if not file_path or not file_path.exists():
                    result['missing'].append(standard_id)
                    continue
                
                if not self.validate_pdf(file_path):
                    result['corrupted'].append(standard_id)
        
        except Exception as e:
            logger.error(f"Error verifying files: {e}")
        
        return result
