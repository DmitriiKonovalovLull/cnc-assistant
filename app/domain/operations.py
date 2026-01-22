"""
Модель операций обработки.
"""
from typing import Dict, Any
from dataclasses import dataclass
from enum import Enum


class OperationType(Enum):
    """Типы операций."""
    TURNING = "токарка"
    MILLING = "фрезерование"
    DRILLING = "сверление"
    BORING = "растачивание"
    GRINDING = "шлифование"


@dataclass
class Operation:
    """Параметры операции."""
    name: str
    type: OperationType
    default_feed_range: tuple  # диапазон подач (мм/об)
    tool_types: list  # типы инструментов

    # Коэффициенты сложности
    complexity_factor: float = 1.0


# База операций
OPERATIONS_DB = {
    "токарка": Operation(
        name="токарка",
        type=OperationType.TURNING,
        default_feed_range=(0.1, 0.5),
        tool_types=["резец токарный"],
        complexity_factor=1.0
    ),

    "фрезерование": Operation(
        name="фрезерование",
        type=OperationType.MILLING,
        default_feed_range=(0.05, 0.3),
        tool_types=["фреза концевая", "фреза торцевая"],
        complexity_factor=1.2
    ),

    "сверление": Operation(
        name="сверление",
        type=OperationType.DRILLING,
        default_feed_range=(0.05, 0.2),
        tool_types=["сверло спиральное"],
        complexity_factor=0.8
    ),

    "растачивание": Operation(
        name="растачивание",
        type=OperationType.BORING,
        default_feed_range=(0.05, 0.15),
        tool_types=["расточной резец"],
        complexity_factor=1.3
    ),
}


def get_operation(name: str) -> Operation:
    """Получить операцию по имени."""
    op = OPERATIONS_DB.get(name.lower())
    if not op:
        raise ValueError(f"Операция '{name}' не найдена")
    return op


def get_recommended_feed(
        operation: str,
        mode: str,
        diameter: float
) -> float:
    """
    Получить рекомендуемую подачу.
    """
    op = get_operation(operation)
    feed_min, feed_max = op.default_feed_range

    # Корректировка по режиму
    mode_factors = {
        "черновой": feed_max,
        "получистовой": (feed_min + feed_max) / 2,
        "чистовой": feed_min * 0.8,
    }

    base_feed = mode_factors.get(mode, (feed_min + feed_max) / 2)

    # Корректировка по диаметру
    if diameter > 100:  # большие диаметры - меньшая подача
        base_feed *= 0.8
    elif diameter < 10:  # малые диаметры - осторожнее
        base_feed *= 0.7

    return round(base_feed, 3)