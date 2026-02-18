"""
Тесты контекстной валидации чисел.
Проверка что числа из стандартов не распознаются как диаметры.
"""

import pytest

from app.dialog.intent_detector import IntentDetector
from app.dialog.validators import Validator
from app.dialog.message_processor import MessageProcessor
from app.dialog.constants import DialogState, Intent


@pytest.fixture
def detector():
    """Фикстура для IntentDetector."""
    return IntentDetector()


@pytest.fixture
def validator():
    """Фикстура для Validator."""
    return Validator()


@pytest.fixture
def processor():
    """Фикстура для MessageProcessor."""
    return MessageProcessor()


def test_standard_number_not_dimension(detector, validator):
    """Числа из стандартов НЕ должны распознаваться как диаметры."""
    message = "ОСТ 33079-80"
    
    # Проверяем интент
    result = detector.detect(message)
    assert result['intent'] == Intent.STANDARD_REQUEST
    
    # Проверяем что размеры НЕ извлекаются
    extracted = validator.extract_data_from_message(message, allow_dimensions=False, has_standard=True)
    assert 'diameter_from' not in extracted
    assert 'diameter_to' not in extracted


def test_large_number_rejected(validator):
    """Большие числа (>2000) должны отклоняться как диаметры."""
    # Число больше 2000
    diameter = validator.validate_diameter("33079")
    assert diameter is None
    
    # Нормальное число
    diameter = validator.validate_diameter("200")
    assert diameter == 200.0


def test_dimension_only_in_correct_state(processor):
    """Размеры извлекаются ТОЛЬКО в состоянии WAITING_DIMENSIONS."""
    user_id = 1
    
    # Устанавливаем состояние IDLE
    processor.state_machine.set(user_id, DialogState.IDLE)
    
    # Пытаемся извлечь размеры из сообщения
    result = processor.process(user_id, "200 до 50")
    
    # Размеры НЕ должны быть извлечены в состоянии IDLE
    context = processor.context_manager.get(user_id)
    assert context.diameter_from is None
    assert context.diameter_to is None


def test_dimension_extracted_in_waiting_dimensions_state(processor):
    """Размеры извлекаются в состоянии WAITING_DIMENSIONS."""
    user_id = 2
    
    # Устанавливаем состояние WAITING_DIMENSIONS
    processor.state_machine.set(user_id, DialogState.WAITING_DIMENSIONS)
    
    # Извлекаем размеры
    result = processor.process(user_id, "с 200 до 50")
    
    # Размеры должны быть извлечены
    context = processor.context_manager.get(user_id)
    assert context.diameter_from is not None
    assert context.diameter_to is not None


def test_standard_overrides_dimensions(processor):
    """Стандарт должен запрещать извлечение размеров."""
    user_id = 3
    
    # Устанавливаем состояние WAITING_DIMENSIONS
    processor.state_machine.set(user_id, DialogState.WAITING_DIMENSIONS)
    
    # Запрашиваем стандарт
    result = processor.process(user_id, "ОСТ 33079-80")
    
    # Проверяем что интент - STANDARD_REQUEST
    assert result['intent'] == Intent.STANDARD_REQUEST
    
    # Размеры НЕ должны быть извлечены
    context = processor.context_manager.get(user_id)
    assert context.diameter_from is None
    assert context.diameter_to is None


def test_dimension_with_context_marker(validator):
    """Размеры извлекаются ТОЛЬКО с контекстным маркером."""
    # С контекстным маркером - должно работать
    range1 = validator.validate_dimension_range("с 200 до 50")
    assert range1 is not None
    
    range2 = validator.validate_dimension_range("200-50")
    assert range2 is not None
    
    range3 = validator.validate_dimension_range("200→50")
    assert range3 is not None
    
    # Без контекстного маркера - НЕ должно работать
    range4 = validator.validate_dimension_range("200 50")
    assert range4 is None


def test_calculation_request_without_dimensions(processor):
    """Запрос расчета без размеров должен запрашивать недостающие поля."""
    user_id = 4
    
    # Устанавливаем состояние IDLE
    processor.state_machine.set(user_id, DialogState.IDLE)
    
    # Запрашиваем расчет без параметров
    result = processor.process(user_id, "рассчитать режимы")
    
    # Должен запросить недостающие поля
    assert result['intent'] == Intent.CALCULATION_REQUEST
    assert "операция" in result['response'].lower() or "материал" in result['response'].lower()
    
    # НЕ должен создавать деталь автоматически
    context = processor.context_manager.get(user_id)
    assert context.diameter_from is None
    assert context.diameter_to is None


def test_required_fields_check(processor):
    """Проверка required fields перед расчетом."""
    user_id = 5
    
    # Устанавливаем состояние CALCULATION_READY без всех полей
    processor.state_machine.set(user_id, DialogState.CALCULATION_READY)
    processor.context_manager.update(user_id, operation="токарка")
    # Нет материала и размеров
    
    # Пытаемся выполнить расчет
    result = processor.process(user_id, "рассчитать")
    
    # Должен запросить недостающие поля
    assert "материал" in result['response'].lower() or "размеры" in result['response'].lower()


def test_standard_pattern_with_hyphen(detector):
    """Паттерн стандарта с дефисом должен распознаваться."""
    test_cases = [
        "ОСТ 33079-80",
        "ГОСТ 7798-70",
        "ISO 965-1",
        "DIN 912-88",
    ]
    
    for message in test_cases:
        result = detector.detect(message)
        assert result['intent'] == Intent.STANDARD_REQUEST, f"Failed for: {message}"


def test_dimension_range_validation(validator):
    """Валидация диапазона размеров."""
    # Валидный диапазон
    range1 = validator.validate_dimension_range("с 200 до 50")
    assert range1 == (50.0, 200.0)  # Меньшее значение первым
    
    # Невалидный диапазон (слишком большой)
    range2 = validator.validate_dimension_range("с 5000 до 10000")
    assert range2 is None
    
    # Невалидный диапазон (отрицательный)
    range3 = validator.validate_dimension_range("с -10 до 50")
    assert range3 is None
