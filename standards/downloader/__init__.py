"""
Модуль скачивания стандартов.
"""

from standards.downloader.standard_downloader import (
    StandardDownloader,
    download_all_standards,
)

__all__ = ["StandardDownloader", "download_all_standards"]
