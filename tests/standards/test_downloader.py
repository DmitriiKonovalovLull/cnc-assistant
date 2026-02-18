"""
Тесты для модуля скачивания стандартов.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from standards.downloader.standard_downloader import StandardDownloader


class TestStandardDownloader:
    """Тесты загрузчика стандартов."""
    
    def test_downloader_initialization(self, tmp_path):
        """Тест инициализации загрузчика."""
        storage_dir = tmp_path / "standards"
        downloader = StandardDownloader(storage_dir=str(storage_dir))
        
        assert downloader.storage_dir.exists()
        assert (storage_dir / "iso").exists()
        assert (storage_dir / "gost").exists()
    
    @patch('standards.downloader.standard_downloader.requests.Session')
    def test_download_mock(self, mock_session, tmp_path):
        """Тест скачивания с моком."""
        # Настраиваем мок
        mock_response = Mock()
        mock_response.content = b"fake pdf content"
        mock_response.raise_for_status = Mock()
        
        mock_session_instance = Mock()
        mock_session_instance.get.return_value = mock_response
        mock_session_instance.headers = {}
        mock_session.return_value = mock_session_instance
        
        storage_dir = tmp_path / "standards"
        downloader = StandardDownloader(storage_dir=str(storage_dir))
        downloader.session = mock_session_instance
        
        # Скачиваем файл
        file_path = downloader.download(
            url="http://example.com/test.pdf",
            name="test",
            source="ISO"
        )
        
        assert file_path is not None
        assert file_path.exists()
        assert file_path.name == "test.pdf"
    
    def test_sha256_calculation(self, tmp_path):
        """Тест вычисления SHA256."""
        storage_dir = tmp_path / "standards"
        downloader = StandardDownloader(storage_dir=str(storage_dir))
        
        # Создаем тестовый файл
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        sha256 = downloader._calculate_sha256(test_file)
        
        # SHA256 должен быть строкой из 64 символов
        assert len(sha256) == 64
        assert isinstance(sha256, str)
    
    def test_metadata_save_load(self, tmp_path):
        """Тест сохранения и загрузки метаданных."""
        storage_dir = tmp_path / "standards"
        downloader = StandardDownloader(storage_dir=str(storage_dir))
        
        # Добавляем метаданные
        downloader.metadata["test:standard"] = {
            "url": "http://example.com/test.pdf",
            "sha256": "abc123",
            "download_date": "2024-01-01",
        }
        
        # Сохраняем
        downloader._save_metadata()
        
        # Создаем новый загрузчик и проверяем загрузку
        downloader2 = StandardDownloader(storage_dir=str(storage_dir))
        
        assert "test:standard" in downloader2.metadata
        assert downloader2.metadata["test:standard"]["sha256"] == "abc123"
    
    def test_verify_file(self, tmp_path):
        """Тест проверки целостности файла."""
        storage_dir = tmp_path / "standards"
        downloader = StandardDownloader(storage_dir=str(storage_dir))
        
        # Создаем тестовый файл
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        # Вычисляем SHA256
        sha256 = downloader._calculate_sha256(test_file)
        
        # Проверяем файл
        assert downloader.verify_file(test_file, sha256) is True
        
        # Проверяем с неправильным SHA256
        assert downloader.verify_file(test_file, "wrong_hash") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
