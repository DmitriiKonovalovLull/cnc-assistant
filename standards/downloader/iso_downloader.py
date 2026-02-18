"""
ISO Downloader - загрузка международных стандартов ISO.
"""

import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from standards.downloader.base_downloader import BaseDownloader

logger = logging.getLogger(__name__)


class ISODownloader(BaseDownloader):
    """
    Downloader для ISO стандартов.
    
    ВАЖНО: ISO стандарты платные и требуют API ключ или подписку.
    Здесь базовая реализация для структуры.
    """
    
    def fetch_list(self) -> List[Dict[str, Any]]:
        """
        Получить список ISO стандартов.
        
        Returns:
            Список известных ISO стандартов
        """
        # Известные ISO стандарты (из системы стандартов)
        known_iso = [
            {'id': '965-1', 'code': 'ISO 965-1', 'name': 'Резьбы метрические ISO общего назначения'},
            {'id': '286-1', 'code': 'ISO 286-1', 'name': 'Система допусков и посадок'},
            {'id': '68-1', 'code': 'ISO 68-1', 'name': 'Резьбы метрические ISO'},
            # Добавить больше по мере необходимости
        ]
        
        logger.info(f"ISO list: {len(known_iso)} known standards")
        return known_iso
    
    def download_standard(self, standard_id: str) -> Optional[Path]:
        """
        Скачать ISO стандарт.
        
        ВАЖНО: ISO стандарты платные, требуют API ключ.
        
        Args:
            standard_id: ID стандарта (например "965-1")
            
        Returns:
            Путь к файлу если найден локально, иначе None
        """
        # Проверяем локальную базу
        file_path = self.storage_dir / f"ISO_{standard_id}.pdf"
        
        if file_path.exists() and self.validate_pdf(file_path):
            logger.info(f"ISO {standard_id} found locally")
            return file_path
        
        logger.warning(
            f"ISO {standard_id} requires API key or subscription. "
            f"ISO standards are paid and not publicly available."
        )
        
        return None
