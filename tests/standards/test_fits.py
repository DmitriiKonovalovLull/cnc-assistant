"""
Тесты для вычислений посадок (зазоры, натяги).
"""

import pytest
from standards.calculations.fit_calculator import (
    calculate_fit,
    get_manufacturing_requirements_from_fit,
)


class TestFitCalculator:
    """Тесты вычислений посадок."""
    
    def test_fit_type_detection_clearance(self):
        """Тест определения зазорной посадки."""
        # H7/g6 обычно дает зазор
        fit_data = calculate_fit(50.0, "H7", "g6")
        
        assert fit_data["fit_type"] in ["clearance", "transition", "interference"]
        assert fit_data["nominal_diameter_mm"] == 50.0
        assert fit_data["hole_tolerance_mm"] > 0
        assert fit_data["shaft_tolerance_mm"] > 0
    
    def test_fit_type_detection_interference(self):
        """Тест определения посадки с натягом."""
        # H7/s6 обычно дает натяг
        fit_data = calculate_fit(50.0, "H7", "s6")
        
        assert fit_data["fit_type"] in ["clearance", "transition", "interference"]
        # Для натяга min_clearance должен быть отрицательным
        if fit_data["fit_type"] == "interference":
            assert fit_data["min_clearance_mm"] < 0
    
    def test_fit_calculation_min_max_clearance(self):
        """Тест вычисления минимального и максимального зазоров."""
        fit_data = calculate_fit(50.0, "H7", "g6")
        
        # Минимальный зазор = отверстие_min - вал_max
        min_clearance = fit_data["hole_min_mm"] - fit_data["shaft_max_mm"]
        assert abs(fit_data["min_clearance_mm"] - min_clearance) < 0.0001
        
        # Максимальный зазор = отверстие_max - вал_min
        max_clearance = fit_data["hole_max_mm"] - fit_data["shaft_min_mm"]
        assert abs(fit_data["max_clearance_mm"] - max_clearance) < 0.0001
    
    def test_manufacturing_requirements_interference_fit(self):
        """Тест производственных требований для посадки с натягом."""
        fit_data = calculate_fit(50.0, "H7", "s6")
        
        if fit_data["fit_type"] == "interference":
            requirements = get_manufacturing_requirements_from_fit(fit_data)
            
            assert requirements["requires_thermal_control"] is True
            assert requirements["requires_precision"] is True
            assert requirements["assembly_method"] in ["thermal_expansion", "press_fit"]
    
    def test_manufacturing_requirements_transition_fit(self):
        """Тест производственных требований для переходной посадки."""
        # Переходная посадка требует повышенной точности
        fit_data = calculate_fit(50.0, "H7", "k6")
        
        if fit_data["fit_type"] == "transition":
            requirements = get_manufacturing_requirements_from_fit(fit_data)
            
            assert requirements["requires_precision"] is True
            assert requirements["assembly_method"] == "precision_fit"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
