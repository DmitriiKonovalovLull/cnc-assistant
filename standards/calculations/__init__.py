"""
Модуль математических вычислений для стандартов.
Все вычисления выполняются строго по формулам ISO/GOST без LLM-угадываний.
"""

from standards.calculations.thread_geometry import (
    ThreadGeometry,
    calculate_thread_geometry,
    calculate_thread_passes,
    get_thread_tolerance_requirements,
)

from standards.calculations.tolerance_calculator import (
    calculate_tolerance_unit,
    calculate_it_tolerance,
    calculate_tolerance_field_values,
    get_manufacturing_requirements_from_tolerance,
)

from standards.calculations.fit_calculator import (
    calculate_fit,
    get_manufacturing_requirements_from_fit,
)

from standards.calculations.surface_roughness import (
    calculate_feed_from_roughness,
    calculate_roughness_from_feed,
    get_manufacturing_requirements_from_roughness,
    calculate_required_tool_radius,
)

__all__ = [
    # Thread geometry
    "ThreadGeometry",
    "calculate_thread_geometry",
    "calculate_thread_passes",
    "get_thread_tolerance_requirements",
    # Tolerance calculations
    "calculate_tolerance_unit",
    "calculate_it_tolerance",
    "calculate_tolerance_field_values",
    "get_manufacturing_requirements_from_tolerance",
    # Fit calculations
    "calculate_fit",
    "get_manufacturing_requirements_from_fit",
    # Surface roughness
    "calculate_feed_from_roughness",
    "calculate_roughness_from_feed",
    "get_manufacturing_requirements_from_roughness",
    "calculate_required_tool_radius",
]
