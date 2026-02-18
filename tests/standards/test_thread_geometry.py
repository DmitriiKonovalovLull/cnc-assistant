"""
Тесты для математических вычислений геометрии резьбы.
Проверка всех формул ISO 965-1, ISO 68-1.
"""

import math
import pytest
from standards.calculations.thread_geometry import (
    ThreadGeometry,
    calculate_thread_geometry,
    calculate_thread_passes,
    get_thread_tolerance_requirements,
)


class TestThreadGeometry:
    """Тесты геометрии метрической резьбы."""
    
    def test_metric_thread_m42x15_geometry(self):
        """Тест геометрии резьбы M42x1.5-6g."""
        thread = calculate_thread_geometry(diameter=42.0, pitch=1.5)
        
        # Проверка высоты теоретического профиля: H = (√3 / 2) * P
        expected_H = (math.sqrt(3) / 2) * 1.5
        assert abs(thread.theoretical_profile_height - expected_H) < 0.0001
        
        # Проверка рабочей высоты: H1 = 5/8 * H
        expected_H1 = (5.0 / 8.0) * expected_H
        assert abs(thread.working_height - expected_H1) < 0.0001
        
        # Проверка глубины резьбы: h = 0.61343 * P
        expected_h = 0.61343 * 1.5
        assert abs(thread.thread_depth - expected_h) < 0.0001
        
        # Проверка среднего диаметра: d2 = d - 0.64952 * P
        expected_d2 = 42.0 - 0.64952 * 1.5
        assert abs(thread.pitch_diameter - expected_d2) < 0.0001
        
        # Проверка малого диаметра: d3 = d - 1.22687 * P
        expected_d3 = 42.0 - 1.22687 * 1.5
        assert abs(thread.minor_diameter - expected_d3) < 0.0001
    
    def test_metric_thread_m20_geometry(self):
        """Тест геометрии резьбы M20 (стандартный шаг 2.5)."""
        thread = calculate_thread_geometry(diameter=20.0, pitch=2.5)
        
        expected_H = (math.sqrt(3) / 2) * 2.5
        assert abs(thread.theoretical_profile_height - expected_H) < 0.0001
        
        expected_h = 0.61343 * 2.5
        assert abs(thread.thread_depth - expected_h) < 0.0001
        
        expected_d2 = 20.0 - 0.64952 * 2.5
        assert abs(thread.pitch_diameter - expected_d2) < 0.0001
    
    def test_thread_area_calculation(self):
        """Тест вычисления площади поперечного сечения резьбы."""
        thread = calculate_thread_geometry(diameter=20.0, pitch=2.5)
        area = thread.get_thread_area()
        
        # Площадь должна быть положительной
        assert area > 0
        # Площадь должна быть меньше площади номинального диаметра
        nominal_area = math.pi * (20.0 ** 2) / 4
        assert area < nominal_area
    
    def test_thread_volume_calculation(self):
        """Тест вычисления объема материала резьбы."""
        thread = calculate_thread_geometry(diameter=20.0, pitch=2.5)
        volume = thread.get_thread_volume_per_length(100.0)
        
        # Объем должен быть положительным
        assert volume > 0
        # Объем должен быть меньше объема цилиндра номинального диаметра
        cylinder_volume = math.pi * (20.0 ** 2) / 4 * 100.0
        assert volume < cylinder_volume
    
    def test_thread_passes_calculation(self):
        """Тест вычисления количества проходов для нарезки резьбы."""
        thread = calculate_thread_geometry(diameter=20.0, pitch=2.5)
        thread_depth = thread.thread_depth
        
        # Для глубины ~1.5 мм и max_pass_depth=0.5 должно быть минимум 3 прохода
        passes = calculate_thread_passes(thread_depth, max_pass_depth=0.5)
        assert passes >= 3
        
        # Для большей глубины за проход должно быть меньше проходов
        passes_large = calculate_thread_passes(thread_depth, max_pass_depth=1.0)
        assert passes_large < passes
    
    def test_thread_tolerance_requirements_fine_pitch(self):
        """Тест требований к точности для мелкого шага."""
        # Шаг < 2 мм и класс ≤ 6 → требуется чистовой проход
        requirements = get_thread_tolerance_requirements(pitch=1.5, tolerance_class="6g")
        
        assert requirements["requires_finish_pass"] is True
        assert requirements["min_passes"] >= 2
        assert requirements["max_feed_mm_rev"] is not None
    
    def test_thread_tolerance_requirements_coarse_pitch(self):
        """Тест требований к точности для крупного шага."""
        # Шаг ≥ 2 мм → менее строгие требования
        requirements = get_thread_tolerance_requirements(pitch=3.0, tolerance_class="6g")
        
        # Для крупного шага может не требоваться чистовой проход
        assert requirements["max_feed_mm_rev"] is not None
    
    def test_thread_tolerance_requirements_very_fine_pitch(self):
        """Тест требований для очень мелкого шага."""
        requirements = get_thread_tolerance_requirements(pitch=0.5, tolerance_class="6g")
        
        # Очень мелкий шаг → строгое ограничение подачи
        assert requirements["max_feed_mm_rev"] is not None
        assert requirements["max_feed_mm_rev"] < 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
