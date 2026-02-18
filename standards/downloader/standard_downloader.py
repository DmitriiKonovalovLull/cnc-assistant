"""
Модуль скачивания стандартов из официальных источников.
Поддержка ГОСТ, ISO, DIN и других систем.
"""

import os
import json
import hashlib
import logging
import time
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class StandardDownloader:
    """
    Класс для скачивания стандартов из официальных источников.
    Поддерживает retry, проверку SHA256, версионирование.
    """
    
    # Источники стандартов
    STANDARD_SOURCES = {
        "GOST": {
            "base_url": "https://standartgost.ru",
            "format": "pdf",
        },
        "OST": {
            "base_url": "https://standartgost.ru",  # ОСТ часто на тех же сайтах что и ГОСТ
            "format": "pdf",
            "note": "ОСТ редко доступны публично, может потребоваться ручной поиск"
        },
        "ISO": {
            "base_url": "https://www.iso.org",
            "format": "pdf",
        },
        "DIN": {
            "base_url": "https://www.din.de",
            "format": "pdf",
        },
    }
    
    def __init__(self, storage_dir: str = "standards/raw"):
        """
        Инициализация загрузчика стандартов.
        
        Args:
            storage_dir: Директория для сохранения скачанных файлов
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Создаем поддиректории для каждого источника
        for source in self.STANDARD_SOURCES.keys():
            (self.storage_dir / source.lower()).mkdir(exist_ok=True)
        
        # Настройка сессии с retry
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # User-Agent для запросов
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        })
        
        # Метаданные загруженных стандартов
        self.metadata_file = self.storage_dir / "metadata.json"
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict:
        """Загрузить метаданные загруженных стандартов."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load metadata: {e}")
        return {}
    
    def _save_metadata(self) -> None:
        """Сохранить метаданные."""
        try:
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")
    
    def _calculate_sha256(self, file_path: Path) -> str:
        """Вычислить SHA256 хеш файла."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def download(
        self,
        url: str,
        name: str,
        source: str = "ISO",
        force: bool = False
    ) -> Optional[Path]:
        """
        Скачать стандарт по URL.
        
        Args:
            url: URL для скачивания
            name: Имя стандарта (например "ISO-965-1")
            source: Источник стандарта (GOST, ISO, DIN)
            force: Принудительно перезаписать существующий файл
            
        Returns:
            Путь к скачанному файлу или None при ошибке
        """
        # Определяем расширение файла
        parsed_url = urlparse(url)
        ext = os.path.splitext(parsed_url.path)[1] or ".pdf"
        
        # Путь для сохранения
        source_dir = self.storage_dir / source.lower()
        file_path = source_dir / f"{name}{ext}"
        
        # Проверяем, не скачан ли уже файл
        if file_path.exists() and not force:
            logger.info(f"File already exists: {file_path}")
            return file_path
        
        try:
            logger.info(f"Downloading {name} from {url}...")
            
            # Скачиваем файл
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Сохраняем файл
            with open(file_path, "wb") as f:
                f.write(response.content)
            
            # Вычисляем SHA256
            sha256 = self._calculate_sha256(file_path)
            
            # Сохраняем метаданные
            metadata_key = f"{source}:{name}"
            self.metadata[metadata_key] = {
                "url": url,
                "file_path": str(file_path),
                "sha256": sha256,
                "download_date": datetime.now().isoformat(),
                "file_size": file_path.stat().st_size,
                "source": source,
            }
            self._save_metadata()
            
            logger.info(f"✅ Downloaded {name} ({file_path.stat().st_size} bytes, SHA256: {sha256[:16]}...)")
            
            return file_path
        
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to download {name}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Error downloading {name}: {e}")
            return None
    
    def download_standard(self, standard_id: str, source: str = "ISO") -> Optional[Path]:
        """
        Скачать стандарт по его идентификатору.
        
        Args:
            standard_id: Идентификатор стандарта (например "965-1" для ISO 965-1)
            source: Источник стандарта (GOST, OST, ISO, DIN)
            
        Returns:
            Путь к скачанному файлу или None
        """
        # Нормализуем источник
        source_upper = source.upper()
        if source_upper == 'ОСТ':
            source_upper = 'OST'
        
        # Формируем URL (упрощенно, в реальности нужны конкретные URL для каждого источника)
        source_config = self.STANDARD_SOURCES.get(source_upper)
        if not source_config:
            logger.error(f"Unknown source: {source}")
            return None
        
        # Для ОСТ - особое предупреждение
        if source_upper == 'OST':
            logger.warning(
                f"⚠️ ОСТ {standard_id} редко доступны публично. "
                f"Может потребоваться ручной поиск или загрузка пользователем."
            )
        
        # В реальности здесь должна быть логика формирования правильного URL
        # Для примера используем заглушку
        url = f"{source_config['base_url']}/standard/{standard_id}"
        
        name = f"{source_upper}-{standard_id.replace('/', '-')}"
        
        return self.download(url, name, source_upper)
    
    def verify_file(self, file_path: Path, expected_sha256: Optional[str] = None) -> bool:
        """
        Проверить целостность файла по SHA256.
        
        Args:
            file_path: Путь к файлу
            expected_sha256: Ожидаемый SHA256 (если известен)
            
        Returns:
            True если файл корректен
        """
        if not file_path.exists():
            return False
        
        actual_sha256 = self._calculate_sha256(file_path)
        
        if expected_sha256:
            return actual_sha256 == expected_sha256
        
        # Если ожидаемый SHA256 не указан, проверяем по метаданным
        for metadata in self.metadata.values():
            if metadata.get("file_path") == str(file_path):
                return actual_sha256 == metadata.get("sha256")
        
        return True
    
    def get_downloaded_standards(self, source: Optional[str] = None) -> List[Dict]:
        """
        Получить список скачанных стандартов.
        
        Args:
            source: Фильтр по источнику (опционально)
            
        Returns:
            Список метаданных стандартов
        """
        if source:
            return [
                {**meta, "name": name}
                for name, meta in self.metadata.items()
                if meta.get("source", "").upper() == source.upper()
            ]
        return [{**meta, "name": name} for name, meta in self.metadata.items()]


def download_all_standards() -> Dict[str, any]:
    """
    Скачать все стандарты из списка.
    
    Returns:
        Словарь с результатами загрузки
    """
    downloader = StandardDownloader()
    results = {
        "downloaded": [],
        "failed": [],
        "skipped": [],
    }
    
    # Список стандартов для загрузки (пример)
    standards_to_download = [
        {"source": "ISO", "id": "965-1", "name": "ISO-965-1"},
        {"source": "ISO", "id": "286-1", "name": "ISO-286-1"},
        # Добавить больше стандартов по необходимости
    ]
    
    for standard in standards_to_download:
        file_path = downloader.download_standard(
            standard["id"],
            standard["source"]
        )
        
        if file_path:
            results["downloaded"].append(standard["name"])
        else:
            results["failed"].append(standard["name"])
    
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = download_all_standards()
    print(f"Downloaded: {len(results['downloaded'])}")
    print(f"Failed: {len(results['failed'])}")
