"""
Загрузка HTML/PDF из интернета.
"""

import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class WebScraper:
    """
    Скрейпер для загрузки контента из интернета.
    """
    
    def __init__(self):
        """Инициализация скрейпера."""
        pass
    
    def fetch_html(self, url: str) -> Optional[str]:
        """
        Загрузить HTML страницу.
        
        Args:
            url: URL страницы
            
        Returns:
            HTML контент или None при ошибке
        """
        try:
            import requests
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Failed to fetch HTML from {url}: {e}")
            return None
    
    def fetch_pdf(self, url: str) -> Optional[bytes]:
        """
        Загрузить PDF файл.
        
        Args:
            url: URL PDF файла
            
        Returns:
            Байты PDF или None при ошибке
        """
        try:
            import requests
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Failed to fetch PDF from {url}: {e}")
            return None
    
    def save_content(self, content: str, file_path: Path) -> bool:
        """
        Сохранить контент в файл.
        
        Args:
            content: Контент для сохранения
            file_path: Путь к файлу
            
        Returns:
            True если успешно сохранено
        """
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            logger.error(f"Failed to save content to {file_path}: {e}")
            return False
