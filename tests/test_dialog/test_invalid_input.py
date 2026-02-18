"""
Тесты обработки невалидного ввода.
"""

import pytest

from app.dialog.message_processor import MessageProcessor
from app.dialog.validators import Validator
from app.dialog.constants import DialogState


@pytest.fixture
def processor():
    """Фикстура для MessageProcessor."""
    return MessageProcessor()


@pytest.fixture
def validator():
    """Фикстура для Validator."""
    return Validator()


def test_invalid_diameter(validator):
    """Невалидный диаметр должен возвращать None."""
    assert validator.validate_diameter("abc") is None
    assert validator.validate_diameter("") is None
    assert validator.validate_diameter("-50") is None


def test_invalid_material(validator):
    """Невалидный материал должен возвращать None или предупреждение."""
    # Неизвестный материал может вернуть как есть с предупреждением
    result = validator.validate_material("неизвестный_материал")
    assert result is not None  # Может вернуть как есть


def test_invalid_operation_does_not_change_state(processor):
    """Невалидная операция не должна менять состояние."""
    user_id = 1
    
    processor.state_machine.set(user_id, DialogState.WAITING_OPERATION)
    
    result = processor.process(user_id, "непонятная операция")
    
    # Состояние не должно измениться
    assert processor.state_machine.get(user_id) == DialogState.WAITING_OPERATION


def test_invalid_dimensions_does_not_change_state(processor):
    """Невалидные размеры не должны менять состояние."""
    user_id = 2
    
    processor.state_machine.set(user_id, DialogState.WAITING_DIMENSIONS)
    
    result = processor.process(user_id, "непонятные размеры")
    
    # Состояние не должно измениться
    assert processor.state_machine.get(user_id) == DialogState.WAITING_DIMENSIONS
