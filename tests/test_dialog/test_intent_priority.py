"""
Тесты приоритетов интентов.
"""

import pytest

from app.dialog.intent_detector import IntentDetector
from app.dialog.constants import Intent


@pytest.fixture
def detector():
    """Фикстура для IntentDetector."""
    return IntentDetector()


def test_reset_has_highest_priority(detector):
    """RESET должен иметь наивысший приоритет."""
    # Даже если есть другие ключевые слова
    result = detector.detect("сброс ОСТ 33056-80")
    assert result['intent'] == Intent.RESET


def test_standard_request_priority(detector):
    """STANDARD_REQUEST имеет высокий приоритет."""
    result = detector.detect("ОСТ 33056-80")
    assert result['intent'] == Intent.STANDARD_REQUEST
    
    result = detector.detect("ГОСТ 7798-70")
    assert result['intent'] == Intent.STANDARD_REQUEST


def test_calculation_request_priority(detector):
    """CALCULATION_REQUEST обрабатывается после стандартов."""
    result = detector.detect("рассчитать токарка алюминий")
    assert result['intent'] == Intent.CALCULATION_REQUEST


def test_greeting_priority(detector):
    """GREETING имеет низкий приоритет."""
    result = detector.detect("привет")
    assert result['intent'] == Intent.GREETING


def test_standard_overrides_calculation(detector):
    """Стандарт должен переопределять расчетный запрос."""
    result = detector.detect("рассчитать ОСТ 33056-80")
    assert result['intent'] == Intent.STANDARD_REQUEST
