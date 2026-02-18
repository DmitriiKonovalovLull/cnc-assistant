"""
Тесты переопределения стандартом.
"""

import pytest

from app.dialog.message_processor import MessageProcessor
from app.dialog.constants import DialogState, Intent


@pytest.fixture
def processor():
    """Фикстура для MessageProcessor."""
    return MessageProcessor()


def test_standard_overrides_calculation_context(processor):
    """Запрос стандарта должен сбрасывать расчетный контекст."""
    user_id = 1
    
    # Устанавливаем расчетный контекст
    processor.state_machine.set(user_id, DialogState.WAITING_MATERIAL)
    processor.context_manager.update(user_id, operation="токарка", material="алюминий")
    
    # Запрашиваем стандарт
    result = processor.process(user_id, "ОСТ 33056-80")
    
    assert result['intent'] == Intent.STANDARD_REQUEST
    assert result['state'] == DialogState.STANDARD_LOOKUP
    
    # Проверяем что расчетный контекст очищен
    context = processor.context_manager.get(user_id)
    assert context.operation is None
    assert context.material is None
    
    # Но стандарт сохранен
    assert context.standard_code is not None


def test_standard_ignores_current_state(processor):
    """Запрос стандарта должен игнорировать текущее состояние."""
    user_id = 2
    
    # Устанавливаем любое состояние
    processor.state_machine.set(user_id, DialogState.CALCULATION_READY)
    
    # Запрашиваем стандарт
    result = processor.process(user_id, "ГОСТ 7798-70")
    
    # Должно перейти в STANDARD_LOOKUP независимо от предыдущего состояния
    assert result['state'] == DialogState.STANDARD_LOOKUP
