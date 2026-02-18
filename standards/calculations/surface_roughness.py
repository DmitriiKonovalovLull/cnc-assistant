"""
Математические вычисления связи шероховатости с параметрами обработки.
"""

import math
from typing import Dict, Optional


def calculate_feed_from_roughness(ra_um: float, tool_radius_mm: float) -> float:
    """
    Вычислить максимальную подачу для достижения требуемой шероховатости.
    
    Формула для точения: Ra ≈ (f²) / (32 * r)
    Откуда: f = √(Ra * 32 * r)
    
    Args:
        ra_um: Требуемая шероховатость Ra в мкм
        tool_radius_mm: Радиус при вершине инструмента в мм
        
    Returns:
        Максимальная подача в мм/об
    """
    if ra_um <= 0 or tool_radius_mm <= 0:
        return 0.0
    
    # Переводим Ra из мкм в мм
    ra_mm = ra_um / 1000.0
    
    # Формула: f = √(Ra * 32 * r)
    feed_mm_rev = math.sqrt(ra_mm * 32.0 * tool_radius_mm)
    
    return feed_mm_rev


def calculate_roughness_from_feed(feed_mm_rev: float, tool_radius_mm: float) -> float:
    """
    Вычислить ожидаемую шероховатость при заданной подаче.
    
    Формула: Ra ≈ (f²) / (32 * r)
    
    Args:
        feed_mm_rev: Подача в мм/об
        tool_radius_mm: Радиус при вершине инструмента в мм
        
    Returns:
        Ожидаемая шероховатость Ra в мкм
    """
    if feed_mm_rev <= 0 or tool_radius_mm <= 0:
        return float('inf')
    
    # Формула: Ra = (f²) / (32 * r)
    ra_mm = (feed_mm_rev ** 2) / (32.0 * tool_radius_mm)
    
    # Переводим в мкм
    ra_um = ra_mm * 1000.0
    
    return ra_um


def get_manufacturing_requirements_from_roughness(ra_um: float) -> Dict[str, any]:
    """
    Определить производственные требования на основе шероховатости.
    
    Args:
        ra_um: Требуемая шероховатость Ra в мкм
        
    Returns:
        Словарь с требованиями:
        - requires_finish_pass: требуется ли чистовой проход
        - max_feed_reduction: коэффициент снижения подачи
        - requires_low_feed: требуется ли низкая подача
        - surface_quality: качество поверхности
    """
    requirements = {
        "requires_finish_pass": False,
        "max_feed_reduction": 1.0,
        "requires_low_feed": False,
        "surface_quality": "standard",
    }
    
    if ra_um <= 0.4:
        requirements["requires_finish_pass"] = True
        requirements["max_feed_reduction"] = 0.3
        requirements["requires_low_feed"] = True
        requirements["surface_quality"] = "super_finish"
    elif ra_um <= 0.8:
        requirements["requires_finish_pass"] = True
        requirements["max_feed_reduction"] = 0.4
        requirements["requires_low_feed"] = True
        requirements["surface_quality"] = "high_finish"
    elif ra_um <= 1.6:
        requirements["requires_finish_pass"] = True
        requirements["max_feed_reduction"] = 0.6
        requirements["requires_low_feed"] = True
        requirements["surface_quality"] = "fine_finish"
    elif ra_um <= 3.2:
        requirements["requires_finish_pass"] = True
        requirements["max_feed_reduction"] = 0.8
        requirements["surface_quality"] = "semi_finish"
    else:
        requirements["surface_quality"] = "rough"
    
    return requirements


def calculate_required_tool_radius(ra_um: float, feed_mm_rev: float) -> float:
    """
    Вычислить требуемый радиус инструмента для достижения шероховатости при заданной подаче.
    
    Формула: r = (f²) / (32 * Ra)
    
    Args:
        ra_um: Требуемая шероховатость Ra в мкм
        feed_mm_rev: Подача в мм/об
        
    Returns:
        Требуемый радиус при вершине в мм
    """
    if ra_um <= 0 or feed_mm_rev <= 0:
        return 0.0
    
    # Переводим Ra из мкм в мм
    ra_mm = ra_um / 1000.0
    
    # Формула: r = (f²) / (32 * Ra)
    radius_mm = (feed_mm_rev ** 2) / (32.0 * ra_mm)
    
    return radius_mm
