"""
Константы для системы диалога.
Определяет состояния, интенты, режимы и правила переходов.
"""

from enum import Enum


class DialogMode(Enum):
    """Режимы работы бота."""
    IDLE = "idle"  # Начальное состояние, ожидание команды
    STANDARD_MODE = "standard_mode"  # Режим работы со стандартами (ГОСТ, ОСТ)
    CNC_CALC_MODE = "cnc_calc_mode"  # Режим расчета режимов резания
    SIMPLE_CALCULATOR_MODE = "simple_calculator_mode"  # Обычный математический калькулятор
    PROJECT_MODE = "project_mode"  # Режим работы с проектами (требует номер работы)


class DialogState(Enum):
    """Состояния диалога."""
    IDLE = "idle"  # Начальное состояние, ожидание команды
    WAITING_MATERIAL = "waiting_material"  # Ожидание материала
    WAITING_DIMENSIONS = "waiting_dimensions"  # Ожидание размеров
    WAITING_OPERATION = "waiting_operation"  # Ожидание операции
    WAITING_STANDARD = "waiting_standard"  # Ожидание стандарта
    CALCULATION_READY = "calculation_ready"  # Готов к расчету
    STANDARD_LOOKUP = "standard_lookup"  # Поиск стандарта
    UPLOAD_MODE = "upload_mode"  # Режим загрузки
    ERROR_STATE = "error_state"  # Ошибка


class Intent(Enum):
    """Интенты пользователя."""
    GREETING = "greeting"  # Приветствие
    CALCULATION_REQUEST = "calculation_request"  # Запрос расчета
    STANDARD_REQUEST = "standard_request"  # Запрос стандарта
    UPLOAD_STANDARD = "upload_standard"  # Загрузка стандарта
    RESET = "reset"  # Сброс состояния
    HELP = "help"  # Помощь
    UNKNOWN = "unknown"  # Неизвестный интент


# Приоритеты интентов (чем меньше число, тем выше приоритет)
INTENT_PRIORITY = {
    Intent.RESET: 1,
    Intent.STANDARD_REQUEST: 2,
    Intent.CALCULATION_REQUEST: 3,
    Intent.GREETING: 4,
    Intent.HELP: 5,
    Intent.UPLOAD_STANDARD: 6,
    Intent.UNKNOWN: 99,
}


# Допустимые переходы состояний
# Ключ: текущее состояние, Значение: список допустимых следующих состояний
ALLOWED_TRANSITIONS = {
    DialogState.IDLE: [
        DialogState.WAITING_OPERATION,
        DialogState.WAITING_MATERIAL,
        DialogState.STANDARD_LOOKUP,
        DialogState.UPLOAD_MODE,
        DialogState.ERROR_STATE,
    ],
    DialogState.WAITING_OPERATION: [
        DialogState.WAITING_MATERIAL,
        DialogState.IDLE,
        DialogState.ERROR_STATE,
    ],
    DialogState.WAITING_MATERIAL: [
        DialogState.WAITING_DIMENSIONS,
        DialogState.WAITING_OPERATION,
        DialogState.IDLE,
        DialogState.ERROR_STATE,
    ],
    DialogState.WAITING_DIMENSIONS: [
        DialogState.CALCULATION_READY,
        DialogState.WAITING_MATERIAL,
        DialogState.IDLE,
        DialogState.ERROR_STATE,
    ],
    DialogState.WAITING_STANDARD: [
        DialogState.CALCULATION_READY,
        DialogState.IDLE,
        DialogState.ERROR_STATE,
    ],
    DialogState.CALCULATION_READY: [
        DialogState.IDLE,
        DialogState.ERROR_STATE,
    ],
    DialogState.STANDARD_LOOKUP: [
        DialogState.IDLE,
        DialogState.ERROR_STATE,
    ],
    DialogState.UPLOAD_MODE: [
        DialogState.IDLE,
        DialogState.ERROR_STATE,
    ],
    DialogState.ERROR_STATE: [
        DialogState.IDLE,
    ],
}


# Состояния, которые можно сбросить командой RESET
RESETTABLE_STATES = [
    DialogState.WAITING_MATERIAL,
    DialogState.WAITING_DIMENSIONS,
    DialogState.WAITING_OPERATION,
    DialogState.WAITING_STANDARD,
    DialogState.CALCULATION_READY,
    DialogState.STANDARD_LOOKUP,
    DialogState.UPLOAD_MODE,
    DialogState.ERROR_STATE,
]
