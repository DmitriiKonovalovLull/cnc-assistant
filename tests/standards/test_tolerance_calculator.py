"""
Тесты для математических вычислений IT допусков по ISO 286.
Проверка всех формул ISO 286-1.
"""

import math
import pytest
from standards.calculations.tolerance_calculator import (
    calculate_tolerance_unit,
    calculate_it_tolerance,
    calculate_tolerance_field_values,
    get_manufacturing_requirements_from_tolerance,
    get_diameter_range,
)


class TestToleranceCalculator:
    """Тесты вычислений допусков."""
    
    def test_tolerance_unit_formula(self):
        """Тест формулы базовой единицы допуска: i = 0.45 * ∛D + 0.001 * D."""
        D = 50.0
        i = calculate_tolerance_unit(D)
        
        expected_i = 0.45 * (D ** (1.0/3.0)) + 0.001 * D
        assert abs(i - expected_i) < 0.0001
    
    def test_it7_tolerance_calculation(self):
        """Тест вычисления IT7 допуска для диаметра 50 мм."""
        D = 50.0
        it_grade = 7
        
        # Вычисляем базовую единицу
        i = calculate_tolerance_unit(D)
        
        # IT7 = 16i
        expected_T_um = 16 * i
        expected_T_mm = expected_T_um / 1000.0
        
        # Вычисляем допуск через функцию
        tolerance_mm = calculate_it_tolerance(D, it_grade)
        
        assert abs(tolerance_mm - expected_T_mm) < 0.0001
    
    def test_it6_tolerance_calculation(self):
        """Тест вычисления IT6 допуска."""
        D = 50.0
        it_grade = 6
        
        i = calculate_tolerance_unit(D)
        expected_T_mm = (10 * i) / 1000.0
        
        tolerance_mm = calculate_it_tolerance(D, it_grade)
        
        assert abs(tolerance_mm - expected_T_mm) < 0.0001
    
    def test_it8_tolerance_calculation(self):
        """Тест вычисления IT8 допуска."""
        D = 50.0
        it_grade = 8
        
        i = calculate_tolerance_unit(D)
        expected_T_mm = (25 * i) / 1000.0
        
        tolerance_mm = calculate_it_tolerance(D, it_grade)
        
        assert abs(tolerance_mm - expected_T_mm) < 0.0001
    
    def test_tolerance_field_h7_values(self):
        """Тест вычисления значений поля допуска H7."""
        diameter = 50.0
        field_values = calculate_tolerance_field_values(diameter, "H7")
        
        assert field_values["it_grade"] == 7
        assert field_values["tolerance_mm"] > 0
        assert field_values["nominal_mm"] == diameter
        # Для H7 нижнее отклонение должно быть 0
        assert abs(field_values["lower_deviation_mm"]) < 0.0001
        # Верхнее отклонение должно быть положительным
        assert field_values["upper_deviation_mm"] > 0
    
    def test_tolerance_field_g6_values(self):
        """Тест вычисления значений поля допуска g6."""
        diameter = 50.0
        field_values = calculate_tolerance_field_values(diameter, "g6")
        
        assert field_values["it_grade"] == 6
        assert field_values["tolerance_mm"] > 0
        # Для g6 отклонения должны быть отрицательными
        assert field_values["upper_deviation_mm"] <= 0
        assert field_values["lower_deviation_mm"] < 0
    
    def test_diameter_range_detection(self):
        """Тест определения диапазона диаметра."""
        # Диаметр 50 мм должен попадать в диапазон 30-50
        d_min, d_max = get_diameter_range(50.0)
        assert d_min <= 50.0 <= d_max
        
        # Диаметр 10 мм должен попадать в диапазон 6-10
        d_min, d_max = get_diameter_range(10.0)
        assert d_min <= 10.0 <= d_max
    
    def test_manufacturing_requirements_tight_tolerance(self):
        """Тест производственных требований для малого допуска."""
        # Допуск ≤ 0.01 мм → требуется шлифование
        requirements = get_manufacturing_requirements_from_tolerance(0.005)
        
        assert requirements["requires_superfinish"] is True
        assert requirements["requires_grinding"] is True
        assert requirements["requires_finish"] is True
        assert requirements["max_feed_reduction"] < 0.5
    
    def test_manufacturing_requirements_medium_tolerance(self):
        """Тест производственных требований для среднего допуска."""
        # Допуск 0.02 мм → требуется чистовая обработка
        requirements = get_manufacturing_requirements_from_tolerance(0.02)
        
        assert requirements["requires_finish"] is True
        assert requirements["requires_grinding"] is False
        assert requirements["max_feed_reduction"] < 1.0
    
    def test_manufacturing_requirements_loose_tolerance(self):
        """Тест производственных требований для большого допуска."""
        # Допуск > 0.02 мм → стандартная обработка
        requirements = get_manufacturing_requirements_from_tolerance(0.1)
        
        assert requirements["requires_finish"] is False
        assert requirements["requires_grinding"] is False
        assert requirements["max_feed_reduction"] == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
