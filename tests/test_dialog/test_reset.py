"""
Тесты механизма сброса.
"""

import pytest

from app.dialog.message_processor import MessageProcessor
from app.dialog.constants import DialogState, Intent


@pytest.fixture
def processor():
    """Фикстура для MessageProcessor."""
    return MessageProcessor()


def test_reset_command(processor):
    """Команда сброса должна очищать состояние и контекст."""
    user_id = 1
    
    # Устанавливаем состояние
    processor.state_machine.set(user_id, DialogState.CALCULATION_READY)
    processor.context_manager.update(user_id, material="алюминий", operation="токарка")
    
    # Выполняем сброс
    result = processor.process(user_id, "сброс")
    
    assert result['intent'] == Intent.RESET
    assert result['state'] == DialogState.IDLE
    
    # Проверяем что контекст очищен
    context = processor.context_manager.get(user_id)
    assert context.material is None
    assert context.operation is None


def test_reset_variants(processor):
    """Различные варианты команд сброса должны работать."""
    user_id = 2
    
    reset_commands = ["сброс", "reset", "начать заново", "отмена"]
    
    for cmd in reset_commands:
        processor.state_machine.set(user_id, DialogState.WAITING_MATERIAL)
        result = processor.process(user_id, cmd)
        
        assert result['intent'] == Intent.RESET
        assert result['state'] == DialogState.IDLE
