"""
OST Downloader - загрузка отраслевых стандартов СССР/РФ.
ОСТ редко доступны публично, поэтому downloader работает ограниченно.
"""

import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from standards.downloader.base_downloader import BaseDownloader

logger = logging.getLogger(__name__)


class OSTDownloader(BaseDownloader):
    """
    Downloader для ОСТ стандартов.
    
    ВАЖНО: ОСТ редко доступны публично.
    Основная стратегия: локальная база + загрузка пользователем.
    """
    
    def fetch_list(self) -> List[Dict[str, Any]]:
        """
        Получить список ОСТ стандартов.
        
        ВАЖНО: ОСТ не имеют публичного API.
        Используем известный список стандартов.
        
        Returns:
            Список известных ОСТ стандартов
        """
        # Известные ОСТ стандарты (из стандартных классов)
        known_ost = [
            {'id': '33056-80', 'code': 'ОСТ 1 33056-80', 'name': 'Гайка шестигранная высокая самоконтрящаяся'},
            {'id': '33057-80', 'code': 'ОСТ 1 33057-80', 'name': 'Гайка шестигранная высокая'},
            {'id': '33058-80', 'code': 'ОСТ 1 33058-80', 'name': 'Гайка шестигранная низкая'},
            {'id': '33059-80', 'code': 'ОСТ 1 33059-80', 'name': 'Болт авиационный'},
            {'id': '33060-80', 'code': 'ОСТ 1 33060-80', 'name': 'Болт авиационный'},
            {'id': '33080-80', 'code': 'ОСТ 1 33080-80', 'name': 'Болт авиационный'},
            # Добавить больше по мере необходимости
        ]
        
        logger.info(f"OST list: {len(known_ost)} known standards")
        return known_ost
    
    def download_standard(self, standard_id: str) -> Optional[Path]:
        """
        Скачать ОСТ стандарт.
        
        ВАЖНО: ОСТ редко доступны публично.
        Этот метод проверяет локальную базу и предлагает пользователю загрузить.
        
        Args:
            standard_id: ID стандарта (например "33056-80")
            
        Returns:
            Путь к файлу если найден локально, иначе None
        """
        # Проверяем локальную базу
        file_path = self.storage_dir / f"OST_{standard_id}.pdf"
        
        if file_path.exists() and self.validate_pdf(file_path):
            logger.info(f"OST {standard_id} found locally")
            return file_path
        
        # ОСТ не доступны публично
        logger.warning(
            f"OST {standard_id} not found locally. "
            f"ОСТ стандарты редко доступны публично. "
            f"Пользователь может загрузить файл вручную."
        )
        
        return None
