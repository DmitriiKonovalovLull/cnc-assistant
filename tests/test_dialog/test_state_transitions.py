"""
Тесты переходов состояний.
"""

import pytest

from app.dialog.state_machine import StateMachine
from app.dialog.constants import DialogState


@pytest.fixture
def state_machine():
    """Фикстура для StateMachine."""
    return StateMachine()


def test_initial_state_is_idle(state_machine):
    """Начальное состояние должно быть IDLE."""
    state = state_machine.get(999)
    assert state == DialogState.IDLE


def test_allowed_transition(state_machine):
    """Допустимый переход должен выполняться."""
    user_id = 1
    
    # IDLE -> WAITING_OPERATION - допустимо
    result = state_machine.transition(
        user_id, DialogState.WAITING_OPERATION, "test"
    )
    assert result is True
    assert state_machine.get(user_id) == DialogState.WAITING_OPERATION


def test_invalid_transition_blocked(state_machine):
    """Недопустимый переход должен блокироваться."""
    user_id = 2
    
    # Устанавливаем состояние
    state_machine.set(user_id, DialogState.WAITING_OPERATION)
    
    # WAITING_OPERATION -> CALCULATION_READY - недопустимо напрямую
    result = state_machine.transition(
        user_id, DialogState.CALCULATION_READY, "test"
    )
    assert result is False
    assert state_machine.get(user_id) == DialogState.WAITING_OPERATION


def test_reset_transition(state_machine):
    """RESET должен сбрасывать в IDLE."""
    user_id = 3
    
    # Устанавливаем состояние
    state_machine.set(user_id, DialogState.CALCULATION_READY)
    
    # Сбрасываем
    result = state_machine.reset(user_id)
    assert result is True
    assert state_machine.get(user_id) == DialogState.IDLE


def test_state_history(state_machine):
    """История переходов должна сохраняться."""
    user_id = 4
    
    state_machine.transition(user_id, DialogState.WAITING_OPERATION, "step1")
    state_machine.transition(user_id, DialogState.WAITING_MATERIAL, "step2")
    
    history = state_machine.get_history(user_id)
    assert len(history) >= 2
    
    # Проверяем последний переход
    last_transition = history[-1]
    assert last_transition['to_state'] == DialogState.WAITING_MATERIAL.value
