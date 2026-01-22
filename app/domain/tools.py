"""
Модель инструмента (упрощённая, для MVP).
"""
from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class CuttingTool:
    """Режущий инструмент."""
    name: str
    material: str  # материал инструмента
    coating: str  # покрытие
    geometry: str  # геометрия

    # Коэффициенты
    material_factor: Dict[str, float]  # для разных материалов
    life_factor: float  # коэффициент стойкости


# Коэффициенты для разных комбинаций материал-инструмент
TOOL_MATERIAL_FACTORS = {
    "твердый сплав": {
        "сталь": 1.0,
        "алюминий": 1.2,
        "титан": 0.7,
        "нержавейка": 0.9,
        "чугун": 1.1,
    },
    "быстрорежущая сталь": {
        "сталь": 0.8,
        "алюминий": 1.0,
        "титан": 0.5,
        "нержавейка": 0.7,
    },
    "керамика": {
        "сталь": 1.2,
        "чугун": 1.3,
    },
    "PCBN": {
        "чугун": 1.5,
        "закалённая сталь": 1.4,
    },
}


def get_tool_factor(
        tool_material: str,
        workpiece_material: str
) -> float:
    """Получить коэффициент для комбинации инструмент-материал."""
    factors = TOOL_MATERIAL_FACTORS.get(tool_material, {})
    return factors.get(workpiece_material, 1.0)


def estimate_tool_wear(
        material: str,
        operation: str,
        vc: float,
        feed: float
) -> float:
    """
    Оценочный коэффициент износа инструмента.
    От 0 (малый износ) до 1 (быстрый износ).
    """
    # Базовый износ по материалу
    material_wear = {
        "алюминий": 0.2,
        "латунь": 0.3,
        "сталь": 0.5,
        "чугун": 0.6,
        "нержавейка": 0.7,
        "титан": 0.8,
    }.get(material, 0.5)

    # Корректировка по скорости
    vc_factor = 1.0
    if vc > 200:
        vc_factor = 1.5
    elif vc < 50:
        vc_factor = 0.8

    # Корректировка по подаче
    feed_factor = 1.0 + (feed * 2)  # Чем больше подача, тем больше износ

    return min(material_wear * vc_factor * feed_factor, 1.0)