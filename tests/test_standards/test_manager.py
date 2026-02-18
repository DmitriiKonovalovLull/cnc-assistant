"""
Базовые unit-тесты для StandardManager.
"""

import pytest
from pathlib import Path
from sqlalchemy.orm import Session

from app.standards.manager import StandardManager
from app.standards.models import Standard


@pytest.fixture
def db_session():
    """Фикстура для сессии БД."""
    # TODO: Использовать тестовую БД
    from app.core.database import SessionLocal
    return SessionLocal()


@pytest.fixture
def manager(db_session):
    """Фикстура для менеджера."""
    return StandardManager(db_session)


def test_calculate_hash(manager, tmp_path):
    """Тест вычисления SHA256 хеша."""
    # Создаем тестовый файл
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"test content")
    
    hash1 = manager.calculate_hash(test_file)
    hash2 = manager.calculate_hash(test_file)
    
    # Хеш должен быть одинаковым для одного файла
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 = 64 hex символа


def test_get_standard_not_found(manager):
    """Тест получения несуществующего стандарта."""
    result = manager.get_standard("ISO", "99999-99")
    assert result is None


def test_verify_integrity_empty(manager):
    """Тест проверки целостности пустой базы."""
    results = manager.verify_integrity()
    assert results['total_standards'] == 0
    assert results['all_ok'] is True
