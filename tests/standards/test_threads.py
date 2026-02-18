"""
Тесты для резьб (ГОСТ / ISO).
Проверка геометрии профиля и производственных требований.
"""

import pytest
import math
from standards.calculations.thread_calculator import ThreadCalculator, ThreadGeometry


class TestThreadGeometry:
    """Тесты геометрии метрической резьбы."""
    
    def test_metric_thread_geometry_m42x15(self):
        """Проверка геометрии резьбы M42x1.5-6g."""
        calculator = ThreadCalculator()
        geometry = calculator.calculate_geometry(
            diameter=42.0,
            pitch=1.5,
            tolerance_class="6g"
        )
        
        # Проверка высоты теоретического профиля: H = (√3 / 2) * P
        expected_H = (math.sqrt(3) / 2) * 1.5
        assert abs(geometry.theoretical_height - expected_H) < 0.0001, \
            f"H: ожидалось {expected_H}, получено {geometry.theoretical_height}"
        
        # Проверка рабочей высоты: H1 = 5/8 * H
        expected_H1 = (5 / 8) * expected_H
        assert abs(geometry.working_height - expected_H1) < 0.0001, \
            f"H1: ожидалось {expected_H1}, получено {geometry.working_height}"
        
        # Проверка глубины резьбы: h = 0.61343 * P
        expected_h = 0.61343 * 1.5
        assert abs(geometry.thread_depth - expected_h) < 0.0001, \
            f"h: ожидалось {expected_h}, получено {geometry.thread_depth}"
        
        # Проверка среднего диаметра: d2 = d - 0.64952 * P
        expected_d2 = 42.0 - 0.64952 * 1.5
        assert abs(geometry.mean_diameter - expected_d2) < 0.0001, \
            f"d2: ожидалось {expected_d2}, получено {geometry.mean_diameter}"
        
        # Проверка малого диаметра: d3 = d - 1.22687 * P
        expected_d3 = 42.0 - 1.22687 * 1.5
        assert abs(geometry.minor_diameter - expected_d3) < 0.0001, \
            f"d3: ожидалось {expected_d3}, получено {geometry.minor_diameter}"
    
    def test_metric_thread_geometry_m20x25(self):
        """Проверка геометрии резьбы M20x2.5."""
        calculator = ThreadCalculator()
        geometry = calculator.calculate_geometry(
            diameter=20.0,
            pitch=2.5,
            tolerance_class=None
        )
        
        # Проверка всех параметров
        expected_H = (math.sqrt(3) / 2) * 2.5
        expected_h = 0.61343 * 2.5
        expected_d2 = 20.0 - 0.64952 * 2.5
        expected_d3 = 20.0 - 1.22687 * 2.5
        
        assert abs(geometry.theoretical_height - expected_H) < 0.0001
        assert abs(geometry.thread_depth - expected_h) < 0.0001
        assert abs(geometry.mean_diameter - expected_d2) < 0.0001
        assert abs(geometry.minor_diameter - expected_d3) < 0.0001
    
    def test_thread_parsing(self):
        """Проверка парсинга обозначений резьбы."""
        calculator = ThreadCalculator()
        
        # Тест 1: M42x1.5-6g
        result = calculator.parse_thread_designation("M42x1.5-6g")
        assert result is not None
        assert result["diameter"] == 42.0
        assert result["pitch"] == 1.5
        assert result["tolerance_class"] == "6g"
        
        # Тест 2: M20 (без шага)
        result = calculator.parse_thread_designation("M20")
        assert result is not None
        assert result["diameter"] == 20.0
        
        # Тест 3: M10x1.25
        result = calculator.parse_thread_designation("M10x1.25")
        assert result is not None
        assert result["diameter"] == 10.0
        assert result["pitch"] == 1.25
    
    def test_manufacturing_requirements(self):
        """Проверка производственных требований для резьбы."""
        calculator = ThreadCalculator()
        
        # Тест 1: Мелкий шаг и высокий класс → чистовой проход
        geometry = calculator.calculate_geometry(42.0, 1.5, "6g")
        requirements = calculator.get_manufacturing_requirements(geometry, material=None)
        
        assert requirements["finish_pass_required"] is True
        assert requirements["number_of_passes"] >= 1
        
        # Тест 2: Большой диаметр → ограничение подачи
        geometry = calculator.calculate_geometry(50.0, 2.0, "6g")
        requirements = calculator.get_manufacturing_requirements(geometry, material=None)
        
        assert requirements["feed_limit"] == 0.3
        
        # Тест 3: Титан → ограничение скорости
        geometry = calculator.calculate_geometry(30.0, 2.0, "6g")
        requirements = calculator.get_manufacturing_requirements(geometry, material="титан")
        
        assert requirements["speed_limit"] == 35.0
    
    def test_tolerance_calculation(self):
        """Проверка расчета допуска для резьбы."""
        calculator = ThreadCalculator()
        
        geometry = calculator.calculate_geometry(42.0, 1.5, "6g")
        
        # Допуск должен быть вычислен
        assert geometry.tolerance_value is not None
        assert geometry.tolerance_value > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
