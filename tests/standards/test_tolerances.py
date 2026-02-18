"""
Тесты для IT допусков ISO 286.
Проверка формул базовой единицы допуска и расчетов допусков.
"""

import pytest
import math
from standards.calculations.tolerance_calculator import ToleranceCalculator, ToleranceResult


class TestITTolerance:
    """Тесты для IT допусков."""
    
    def test_base_unit_calculation(self):
        """Проверка расчета базовой единицы допуска: i = 0.45 * ∛D + 0.001 * D."""
        calculator = ToleranceCalculator()
        
        # Тест для D = 50 мм
        D = 50.0
        i = calculator.calculate_base_unit(D)
        
        expected_i = 0.45 * (D ** (1/3)) + 0.001 * D
        assert abs(i - expected_i) < 0.01, \
            f"Базовая единица: ожидалось {expected_i:.4f}, получено {i:.4f}"
        
        # Тест для D = 100 мм
        D = 100.0
        i = calculator.calculate_base_unit(D)
        expected_i = 0.45 * (D ** (1/3)) + 0.001 * D
        assert abs(i - expected_i) < 0.01
    
    def test_it7_tolerance(self):
        """Проверка расчета допуска IT7 для D = 50 мм."""
        calculator = ToleranceCalculator()
        
        result = calculator.calculate_tolerance(
            nominal_size=50.0,
            it_grade=7,
            tolerance_field=None
        )
        
        # Базовая единица
        expected_i = 0.45 * (50 ** (1/3)) + 0.001 * 50
        
        # IT7 = 16i (множитель 4.0, но в мкм это 16i)
        # В нашем калькуляторе IT7 использует множитель 4.0 от базовой единицы
        # Но формула: T = multiplier * i, где multiplier для IT7 = 4.0
        # Однако стандарт ISO 286 говорит IT7 = 16i, где i в мкм
        # Проверим что результат корректен
        
        assert result.base_unit > 0
        assert result.tolerance_value > 0
        assert result.tolerance_value_microns > 0
        
        # Проверка что допуск вычислен правильно
        expected_T_microns = expected_i * 16  # IT7 = 16i
        assert abs(result.tolerance_value_microns - expected_T_microns) < 0.1
    
    def test_it6_tolerance(self):
        """Проверка расчета допуска IT6."""
        calculator = ToleranceCalculator()
        
        result = calculator.calculate_tolerance(
            nominal_size=50.0,
            it_grade=6,
            tolerance_field=None
        )
        
        expected_i = 0.45 * (50 ** (1/3)) + 0.001 * 50
        expected_T_microns = expected_i * 10  # IT6 = 10i
        
        assert abs(result.tolerance_value_microns - expected_T_microns) < 0.1
    
    def test_h7_field_tolerance(self):
        """Проверка расчета допуска для поля H7."""
        calculator = ToleranceCalculator()
        
        result = calculator.calculate_tolerance(
            nominal_size=50.0,
            it_grade=7,
            tolerance_field="H7"
        )
        
        # H7 - отверстие, нижнее отклонение = 0
        assert result.lower_deviation == 0.0
        
        # Верхнее отклонение = допуск
        assert abs(result.upper_deviation - result.tolerance_value) < 0.0001
        
        # Предельные размеры
        assert result.max_size == 50.0 + result.tolerance_value
        assert result.min_size == 50.0
    
    def test_g6_field_tolerance(self):
        """Проверка расчета допуска для поля g6."""
        calculator = ToleranceCalculator()
        
        result = calculator.calculate_tolerance(
            nominal_size=50.0,
            it_grade=6,
            tolerance_field="g6"
        )
        
        # g6 - вал, верхнее отклонение отрицательное
        assert result.upper_deviation < 0
        
        # Нижнее отклонение = верхнее - допуск
        assert abs(result.lower_deviation - (result.upper_deviation - result.tolerance_value)) < 0.0001
    
    def test_tolerance_parsing(self):
        """Проверка парсинга обозначений допусков."""
        calculator = ToleranceCalculator()
        
        # Тест 1: H7
        result = calculator.parse_tolerance_designation("H7")
        assert result is not None
        assert result["it_grade"] == 7
        assert result["tolerance_field"] == "H7"
        
        # Тест 2: 50 H7
        result = calculator.parse_tolerance_designation("50 H7")
        assert result is not None
        assert result["nominal_size"] == 50.0
        assert result["tolerance_field"] == "H7"
        
        # Тест 3: Ø50 H7
        result = calculator.parse_tolerance_designation("Ø50 H7")
        assert result is not None
        assert result["nominal_size"] == 50.0
        
        # Тест 4: IT7
        result = calculator.parse_tolerance_designation("IT7")
        assert result is not None
        assert result["it_grade"] == 7
    
    def test_manufacturing_requirements(self):
        """Проверка производственных требований на основе допуска."""
        calculator = ToleranceCalculator()
        
        # Тест 1: Допуск ≤ 0.02 мм → чистовая обработка
        result = calculator.calculate_tolerance(50.0, 7, "H7")
        requirements = calculator.get_manufacturing_requirements(result)
        
        if result.tolerance_value <= 0.02:
            assert requirements["finish_turning_required"] is True
        
        # Тест 2: Допуск ≤ 0.01 мм → шлифование
        # Создадим результат с очень малым допуском
        result_small = ToleranceResult(
            nominal_size=50.0,
            it_grade=5,
            tolerance_value=0.008,  # Малый допуск
            tolerance_value_microns=8.0,
            base_unit=1.0,
        )
        requirements = calculator.get_manufacturing_requirements(result_small)
        
        assert requirements["grinding_required"] is True
        
        # Тест 3: Допуск ≤ 0.005 мм → суперфиниш
        result_tiny = ToleranceResult(
            nominal_size=50.0,
            it_grade=4,
            tolerance_value=0.003,
            tolerance_value_microns=3.0,
            base_unit=1.0,
        )
        requirements = calculator.get_manufacturing_requirements(result_tiny)
        
        assert requirements["superfinish_required"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
