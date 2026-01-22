"""
Модель материалов с физическими свойствами.
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class MaterialProperties:
    """Свойства материала для расчёта режимов."""
    name: str
    density: float  # кг/м³
    hardness_hb: float  # Твёрдость по Бринеллю
    thermal_conductivity: float  # Вт/(м·К)
    recommended_vc_range: tuple  # диапазон скоростей резания (м/мин)

    # Коэффициенты для разных операций
    operation_factors: Dict[str, float]

    # Коэффициенты для разных режимов
    mode_factors: Dict[str, float]


# База материалов
MATERIALS_DB = {
    "сталь": MaterialProperties(
        name="сталь",
        density=7850,
        hardness_hb=200,
        thermal_conductivity=50,
        recommended_vc_range=(100, 250),
        operation_factors={
            "токарка": 1.0,
            "фрезерование": 0.8,
            "сверление": 0.6,
            "растачивание": 0.9,
        },
        mode_factors={
            "черновой": 1.2,
            "получистовой": 1.0,
            "чистовой": 0.8,
        }
    ),

    "алюминий": MaterialProperties(
        name="алюминий",
        density=2700,
        hardness_hb=60,
        thermal_conductivity=200,
        recommended_vc_range=(200, 500),
        operation_factors={
            "токарка": 1.0,
            "фрезерование": 0.7,
            "сверление": 0.5,
            "растачивание": 0.8,
        },
        mode_factors={
            "черновой": 1.3,
            "получистовой": 1.0,
            "чистовой": 0.7,
        }
    ),

    "титан": MaterialProperties(
        name="титан",
        density=4500,
        hardness_hb=350,
        thermal_conductivity=20,
        recommended_vc_range=(30, 80),
        operation_factors={
            "токарка": 1.0,
            "фрезерование": 0.6,
            "сверление": 0.4,
            "растачивание": 0.8,
        },
        mode_factors={
            "черновой": 1.1,
            "получистовой": 1.0,
            "чистовой": 0.9,
        }
    ),

    "нержавейка": MaterialProperties(
        name="нержавейка",
        density=7900,
        hardness_hb=250,
        thermal_conductivity=15,
        recommended_vc_range=(50, 120),
        operation_factors={
            "токарка": 1.0,
            "фрезерование": 0.7,
            "сверление": 0.5,
            "растачивание": 0.8,
        },
        mode_factors={
            "черновой": 1.1,
            "получистовой": 1.0,
            "чистовой": 0.9,
        }
    ),
}


def get_material_properties(material_name: str) -> Optional[MaterialProperties]:
    """Получить свойства материала по имени."""
    return MATERIALS_DB.get(material_name.lower())


def get_recommended_vc(
        material: str,
        operation: str,
        mode: str
) -> float:
    """
    Получить рекомендуемую скорость резания для комбинации.
    """
    props = get_material_properties(material)
    if not props:
        raise ValueError(f"Материал '{material}' не найден в базе")

    # Базовое значение (середина диапазона)
    vc_min, vc_max = props.recommended_vc_range
    base_vc = (vc_min + vc_max) / 2

    # Применяем коэффициенты
    op_factor = props.operation_factors.get(operation, 1.0)
    mode_factor = props.mode_factors.get(mode, 1.0)

    return base_vc * op_factor * mode_factor


def get_material_difficulty(material: str) -> float:
    """
    Коэффициент сложности обработки материала.
    От 0.5 (лёгкий) до 2.0 (сложный).
    """
    difficulty_map = {
        "алюминий": 0.5,
        "латунь": 0.6,
        "медь": 0.7,
        "сталь": 1.0,
        "чугун": 1.2,
        "нержавейка": 1.5,
        "титан": 1.8,
        "жаропрочные сплавы": 2.0,
    }

    return difficulty_map.get(material.lower(), 1.0)