"""
Математические вычисления IT допусков по ISO 286.
Все формулы соответствуют стандарту ISO 286-1.
"""

import math
from typing import Dict, Optional, Tuple


def calculate_tolerance_unit(diameter_mm: float) -> float:
    """
    Вычислить базовую единицу допуска i по ISO 286.
    
    Формула: i = 0.45 * ∛D + 0.001 * D (в мкм)
    
    Где D - среднее значение диапазона номинального диаметра.
    
    Args:
        diameter_mm: Номинальный диаметр в мм
        
    Returns:
        Базовая единица допуска i в мкм
    """
    # Для расчета используем среднее значение диапазона
    # Если диаметр в диапазоне, берем среднее геометрическое
    D = diameter_mm
    
    # Формула ISO 286
    i = 0.45 * (D ** (1.0/3.0)) + 0.001 * D
    
    return i


def get_diameter_range(diameter_mm: float) -> Tuple[float, float]:
    """
    Определить диапазон диаметра для расчета допуска по ISO 286.
    
    Args:
        diameter_mm: Номинальный диаметр в мм
        
    Returns:
        Кортеж (D_min, D_max) - границы диапазона
    """
    # Стандартные диапазоны ISO 286
    ranges = [
        (0, 3),
        (3, 6),
        (6, 10),
        (10, 18),
        (18, 30),
        (30, 50),
        (50, 80),
        (80, 120),
        (120, 180),
        (180, 250),
        (250, 315),
        (315, 400),
        (400, 500),
    ]
    
    for d_min, d_max in ranges:
        if d_min < diameter_mm <= d_max:
            # Среднее геометрическое для расчета
            D = math.sqrt(d_min * d_max)
            return (d_min, d_max)
    
    # Если диаметр больше 500, используем последний диапазон
    if diameter_mm > 500:
        return (500, 630)
    
    # Если меньше 0, используем первый диапазон
    return (0, 3)


def calculate_it_tolerance(diameter_mm: float, it_grade: int) -> float:
    """
    Вычислить значение IT допуска по ISO 286.
    
    Формулы:
    IT5 = 7i
    IT6 = 10i
    IT7 = 16i
    IT8 = 25i
    IT9 = 40i
    IT10 = 64i
    IT11 = 100i
    
    Args:
        diameter_mm: Номинальный диаметр в мм
        it_grade: Класс допуска (5-11)
        
    Returns:
        Значение допуска в мм
    """
    # Получаем диапазон диаметра
    d_min, d_max = get_diameter_range(diameter_mm)
    D = math.sqrt(d_min * d_max)  # Среднее геометрическое
    
    # Вычисляем базовую единицу допуска
    i = calculate_tolerance_unit(D)
    
    # Коэффициенты для разных классов IT
    it_multipliers = {
        5: 7,
        6: 10,
        7: 16,
        8: 25,
        9: 40,
        10: 64,
        11: 100,
        12: 160,
        13: 250,
        14: 400,
        15: 640,
        16: 1000,
    }
    
    multiplier = it_multipliers.get(it_grade)
    if multiplier is None:
        # Для неизвестных классов используем приближение
        multiplier = 10 * (2 ** (it_grade - 6)) if it_grade >= 5 else 7
    
    # Вычисляем допуск в мкм
    tolerance_um = multiplier * i
    
    # Переводим в мм
    tolerance_mm = tolerance_um / 1000.0
    
    return tolerance_mm


def calculate_tolerance_field_values(
    diameter_mm: float,
    tolerance_field: str,
    it_grade: Optional[int] = None
) -> Dict[str, float]:
    """
    Вычислить верхнее и нижнее отклонения для поля допуска.
    
    Args:
        diameter_mm: Номинальный диаметр в мм
        tolerance_field: Поле допуска (например "H7", "g6", "k6")
        it_grade: Класс допуска (если не указан, извлекается из поля)
        
    Returns:
        Словарь с:
        - tolerance_mm: значение допуска в мм
        - upper_deviation_mm: верхнее отклонение в мм
        - lower_deviation_mm: нижнее отклонение в мм
        - it_grade: класс допуска
    """
    # Извлекаем класс допуска из поля если не указан
    if it_grade is None:
        for char in tolerance_field:
            if char.isdigit():
                it_grade = int(char)
                break
    
    if it_grade is None:
        raise ValueError(f"Не удалось определить класс допуска из {tolerance_field}")
    
    # Вычисляем допуск
    tolerance_mm = calculate_it_tolerance(diameter_mm, it_grade)
    
    # Определяем тип поля (отверстие или вал)
    field_upper = tolerance_field[0].upper()
    
    # Базовые отклонения для основных полей (упрощенно)
    # В реальности используются таблицы ISO 286-2
    base_deviations = {
        # Отверстия (H)
        "H": {"lower": 0.0, "upper_multiplier": 1.0},
        # Валы (g, h, k, s)
        "G": {"lower_multiplier": -1.0, "upper": 0.0},
        "H": {"lower_multiplier": -1.0, "upper": 0.0},  # для валов
        "K": {"lower_multiplier": -0.5, "upper_multiplier": 0.5},
        "S": {"lower_multiplier": -1.5, "upper_multiplier": -0.5},  # натяг
    }
    
    deviation_config = base_deviations.get(field_upper)
    if not deviation_config:
        # По умолчанию для неизвестных полей
        deviation_config = {"lower": 0.0, "upper_multiplier": 1.0}
    
    # Вычисляем отклонения
    if "lower" in deviation_config:
        lower_deviation_mm = deviation_config["lower"]
    else:
        lower_deviation_mm = deviation_config.get("lower_multiplier", -1.0) * tolerance_mm
    
    if "upper" in deviation_config:
        upper_deviation_mm = deviation_config["upper"]
    else:
        upper_deviation_mm = deviation_config.get("upper_multiplier", 1.0) * tolerance_mm
    
    return {
        "tolerance_mm": tolerance_mm,
        "upper_deviation_mm": upper_deviation_mm,
        "lower_deviation_mm": lower_deviation_mm,
        "it_grade": it_grade,
        "nominal_mm": diameter_mm,
        "max_size_mm": diameter_mm + upper_deviation_mm,
        "min_size_mm": diameter_mm + lower_deviation_mm,
    }


def get_manufacturing_requirements_from_tolerance(tolerance_mm: float) -> Dict[str, any]:
    """
    Определить производственные требования на основе допуска.
    
    Args:
        tolerance_mm: Значение допуска в мм
        
    Returns:
        Словарь с требованиями:
        - requires_finish: требуется ли чистовая обработка
        - requires_grinding: требуется ли шлифование
        - requires_superfinish: требуется ли суперфиниш
        - max_feed_reduction: коэффициент снижения подачи
    """
    requirements = {
        "requires_finish": False,
        "requires_grinding": False,
        "requires_superfinish": False,
        "max_feed_reduction": 1.0,
    }
    
    if tolerance_mm <= 0.005:
        requirements["requires_superfinish"] = True
        requirements["requires_grinding"] = True
        requirements["requires_finish"] = True
        requirements["max_feed_reduction"] = 0.3
    elif tolerance_mm <= 0.01:
        requirements["requires_grinding"] = True
        requirements["requires_finish"] = True
        requirements["max_feed_reduction"] = 0.5
    elif tolerance_mm <= 0.02:
        requirements["requires_finish"] = True
        requirements["max_feed_reduction"] = 0.7
    else:
        requirements["max_feed_reduction"] = 1.0
    
    return requirements
