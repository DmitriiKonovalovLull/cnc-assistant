"""
Тесты разделения режимов и исправления логики.
"""

import pytest

from app.dialog.message_processor import MessageProcessor
from app.dialog.constants import DialogState, DialogMode, Intent


@pytest.fixture
def processor():
    """Фикстура для MessageProcessor."""
    return MessageProcessor()


def test_start_full_reset(processor):
    """Команда /start должна делать полный reset."""
    user_id = 1
    
    # Устанавливаем состояние и режим
    processor.state_machine.set(user_id, DialogState.CALCULATION_READY)
    processor.mode_manager.set(user_id, DialogMode.CNC_CALC_MODE)
    processor.context_manager.update(user_id, material="алюминий", diameter_from=100.0)
    
    # Выполняем /start
    result = processor.process(user_id, "/start", is_start_command=True)
    
    # Проверяем полный reset
    assert result['state'] == DialogState.IDLE
    assert result['mode'] == DialogMode.IDLE
    assert processor.mode_manager.get(user_id) == DialogMode.IDLE
    assert processor.state_machine.get(user_id) == DialogState.IDLE
    
    # Контекст должен быть очищен
    context = processor.context_manager.get(user_id)
    assert context.material is None
    assert context.diameter_from is None


def test_standard_does_not_parse_numbers(processor):
    """Стандарт не должен парсить числа как диаметры."""
    user_id = 2
    
    # Запрашиваем стандарт
    result = processor.process(user_id, "ОСТ 33079-80")
    
    assert result['intent'] == Intent.STANDARD_REQUEST
    assert result['mode'] == DialogMode.STANDARD_MODE
    
    # Размеры НЕ должны быть извлечены
    context = processor.context_manager.get(user_id)
    assert context.diameter_from is None
    assert context.diameter_to is None


def test_simple_calculator_expression(processor):
    """Математические выражения должны обрабатываться как калькулятор."""
    user_id = 3
    
    # Простое выражение
    result = processor.process(user_id, "2+2")
    
    assert result['mode'] == DialogMode.SIMPLE_CALCULATOR_MODE
    assert "4" in result['response']
    
    # Сложное выражение
    result2 = processor.process(user_id, "120*3.14")
    assert result2['mode'] == DialogMode.SIMPLE_CALCULATOR_MODE
    assert "376.8" in result2['response'] or "376" in result2['response']


def test_switch_from_standard_to_calc(processor):
    """Переключение из STANDARD_MODE в CNC_CALC_MODE."""
    user_id = 4
    
    # Сначала стандарт
    result1 = processor.process(user_id, "ОСТ 33079-80")
    assert result1['mode'] == DialogMode.STANDARD_MODE
    
    # Затем запрос расчета
    result2 = processor.process(user_id, "просто посчитать режимы")
    assert result2['mode'] == DialogMode.CNC_CALC_MODE
    assert processor.mode_manager.get(user_id) == DialogMode.CNC_CALC_MODE
    
    # Расчетный контекст должен быть очищен
    context = processor.context_manager.get(user_id)
    assert context.standard_code is None or context.standard_family is None


def test_no_work_number_required(processor):
    """Номер работы не требуется для простого расчета."""
    user_id = 5
    
    # Запрос расчета
    result = processor.process(user_id, "рассчитать режимы")
    
    # Проверяем что в metadata есть флаг
    assert result.get('metadata', {}).get('no_work_number_required', False) is True
    
    # Или проверяем что нет требования номера работы в ответе
    assert "номер работы" not in result['response'].lower()
    assert "работа" not in result['response'].lower() or "работа" in result['response'].lower() and "не требуется" in result['response'].lower()


def test_large_number_rejected(processor):
    """Большие числа (>2000) должны отклоняться."""
    user_id = 6
    
    # Устанавливаем режим расчета и состояние ожидания размеров
    processor.mode_manager.set(user_id, DialogMode.CNC_CALC_MODE)
    processor.state_machine.set(user_id, DialogState.WAITING_DIMENSIONS)
    
    # Пытаемся ввести большое число
    result = processor.process(user_id, "33079")
    
    # Размеры НЕ должны быть извлечены
    context = processor.context_manager.get(user_id)
    assert context.diameter_from is None
    assert context.diameter_to is None


def test_calculator_does_not_change_cnc_context(processor):
    """Калькулятор не должен менять CNC контекст."""
    user_id = 7
    
    # Устанавливаем CNC контекст
    processor.mode_manager.set(user_id, DialogMode.CNC_CALC_MODE)
    processor.context_manager.update(user_id, material="сталь", operation="токарка")
    
    # Используем калькулятор
    result = processor.process(user_id, "2+2")
    
    # Контекст не должен измениться
    context = processor.context_manager.get(user_id)
    assert context.material == "сталь"
    assert context.operation == "токарка"
    
    # Но режим должен быть калькулятор
    assert result['mode'] == DialogMode.SIMPLE_CALCULATOR_MODE


def test_dimensions_only_in_cnc_calc_mode(processor):
    """Размеры извлекаются только в CNC_CALC_MODE и WAITING_DIMENSIONS."""
    user_id = 8
    
    # IDLE режим - размеры не извлекаются
    processor.mode_manager.set(user_id, DialogMode.IDLE)
    processor.state_machine.set(user_id, DialogState.IDLE)
    
    result = processor.process(user_id, "с 200 до 50")
    context = processor.context_manager.get(user_id)
    assert context.diameter_from is None
    
    # CNC_CALC_MODE но не WAITING_DIMENSIONS - размеры не извлекаются
    processor.mode_manager.set(user_id, DialogMode.CNC_CALC_MODE)
    processor.state_machine.set(user_id, DialogState.IDLE)
    
    result = processor.process(user_id, "с 200 до 50")
    context = processor.context_manager.get(user_id)
    assert context.diameter_from is None
    
    # CNC_CALC_MODE и WAITING_DIMENSIONS - размеры извлекаются
    processor.state_machine.set(user_id, DialogState.WAITING_DIMENSIONS)
    
    result = processor.process(user_id, "с 200 до 50")
    context = processor.context_manager.get(user_id)
    assert context.diameter_from is not None
    assert context.diameter_to is not None
