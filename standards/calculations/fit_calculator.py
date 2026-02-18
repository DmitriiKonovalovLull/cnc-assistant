"""
Математические вычисления посадок (зазоры, натяги) по ISO 286.
"""

from typing import Dict, Optional, Tuple
from standards.calculations.tolerance_calculator import calculate_tolerance_field_values


def calculate_fit(
    nominal_diameter_mm: float,
    hole_field: str,
    shaft_field: str
) -> Dict[str, any]:
    """
    Вычислить параметры посадки (зазор/натяг).
    
    Args:
        nominal_diameter_mm: Номинальный диаметр в мм
        hole_field: Поле допуска отверстия (например "H7")
        shaft_field: Поле допуска вала (например "k6")
        
    Returns:
        Словарь с параметрами посадки:
        - fit_type: тип посадки ("clearance", "interference", "transition")
        - min_clearance_mm: минимальный зазор (положительный) или натяг (отрицательный)
        - max_clearance_mm: максимальный зазор (положительный) или натяг (отрицательный)
        - hole_tolerance: допуск отверстия
        - shaft_tolerance: допуск вала
    """
    # Вычисляем параметры отверстия
    hole_values = calculate_tolerance_field_values(nominal_diameter_mm, hole_field)
    hole_min = hole_values["min_size_mm"]
    hole_max = hole_values["max_size_mm"]
    hole_tolerance = hole_values["tolerance_mm"]
    
    # Вычисляем параметры вала
    shaft_values = calculate_tolerance_field_values(nominal_diameter_mm, shaft_field)
    shaft_min = shaft_values["min_size_mm"]
    shaft_max = shaft_values["max_size_mm"]
    shaft_tolerance = shaft_values["tolerance_mm"]
    
    # Вычисляем минимальный и максимальный зазоры/натяги
    min_clearance = hole_min - shaft_max  # Минимальный зазор (может быть отрицательным = натяг)
    max_clearance = hole_max - shaft_min  # Максимальный зазор (может быть отрицательным = натяг)
    
    # Определяем тип посадки
    if min_clearance > 0 and max_clearance > 0:
        fit_type = "clearance"  # Зазорная
    elif min_clearance < 0 and max_clearance < 0:
        fit_type = "interference"  # Натяг
    else:
        fit_type = "transition"  # Переходная
    
    return {
        "fit_type": fit_type,
        "min_clearance_mm": min_clearance,
        "max_clearance_mm": max_clearance,
        "hole_tolerance_mm": hole_tolerance,
        "shaft_tolerance_mm": shaft_tolerance,
        "hole_min_mm": hole_min,
        "hole_max_mm": hole_max,
        "shaft_min_mm": shaft_min,
        "shaft_max_mm": shaft_max,
        "nominal_diameter_mm": nominal_diameter_mm,
    }


def get_manufacturing_requirements_from_fit(fit_data: Dict[str, any]) -> Dict[str, any]:
    """
    Определить производственные требования на основе типа посадки.
    
    Args:
        fit_data: Результат calculate_fit()
        
    Returns:
        Словарь с требованиями:
        - requires_thermal_control: требуется ли контроль температуры
        - requires_heating: требуется ли нагрев
        - requires_precision: требуется ли повышенная точность
        - assembly_method: метод сборки
    """
    fit_type = fit_data["fit_type"]
    min_clearance = fit_data["min_clearance_mm"]
    
    requirements = {
        "requires_thermal_control": False,
        "requires_heating": False,
        "requires_precision": False,
        "assembly_method": "standard",
    }
    
    if fit_type == "interference":
        # Посадка с натягом
        requirements["requires_thermal_control"] = True
        if abs(min_clearance) > 0.05:  # Натяг > 0.05 мм
            requirements["requires_heating"] = True
            requirements["assembly_method"] = "thermal_expansion"
        else:
            requirements["assembly_method"] = "press_fit"
        requirements["requires_precision"] = True
    
    elif fit_type == "transition":
        # Переходная посадка
        requirements["requires_precision"] = True
        requirements["assembly_method"] = "precision_fit"
    
    else:
        # Зазорная посадка
        requirements["assembly_method"] = "standard"
    
    return requirements
