"""
Тесты для вычислений связи шероховатости с параметрами обработки.
"""

import math
import pytest
from standards.calculations.surface_roughness import (
    calculate_feed_from_roughness,
    calculate_roughness_from_feed,
    get_manufacturing_requirements_from_roughness,
    calculate_required_tool_radius,
)


class TestSurfaceRoughness:
    """Тесты вычислений шероховатости."""
    
    def test_feed_from_roughness_formula(self):
        """Тест формулы: f = √(Ra * 32 * r)."""
        ra_um = 1.6
        tool_radius_mm = 0.8
        
        feed = calculate_feed_from_roughness(ra_um, tool_radius_mm)
        
        # Проверяем формулу: f = √(Ra * 32 * r)
        ra_mm = ra_um / 1000.0
        expected_feed = math.sqrt(ra_mm * 32.0 * tool_radius_mm)
        
        assert abs(feed - expected_feed) < 0.0001
    
    def test_roughness_from_feed_formula(self):
        """Тест формулы: Ra = (f²) / (32 * r)."""
        feed_mm_rev = 0.2
        tool_radius_mm = 0.8
        
        ra_um = calculate_roughness_from_feed(feed_mm_rev, tool_radius_mm)
        
        # Проверяем формулу: Ra = (f²) / (32 * r)
        expected_ra_mm = (feed_mm_rev ** 2) / (32.0 * tool_radius_mm)
        expected_ra_um = expected_ra_mm * 1000.0
        
        assert abs(ra_um - expected_ra_um) < 0.0001
    
    def test_feed_roughness_reciprocity(self):
        """Тест взаимной обратимости формул."""
        ra_um = 1.6
        tool_radius_mm = 0.8
        
        feed = calculate_feed_from_roughness(ra_um, tool_radius_mm)
        calculated_ra = calculate_roughness_from_feed(feed, tool_radius_mm)
        
        # Должны получить примерно исходную шероховатость
        assert abs(calculated_ra - ra_um) < 0.1
    
    def test_manufacturing_requirements_fine_roughness(self):
        """Тест производственных требований для малой шероховатости."""
        # Ra ≤ 1.6 → требуется чистовой проход и низкая подача
        requirements = get_manufacturing_requirements_from_roughness(1.6)
        
        assert requirements["requires_finish_pass"] is True
        assert requirements["requires_low_feed"] is True
        assert requirements["max_feed_reduction"] < 1.0
        assert requirements["surface_quality"] in ["fine_finish", "high_finish", "super_finish"]
    
    def test_manufacturing_requirements_very_fine_roughness(self):
        """Тест производственных требований для очень малой шероховатости."""
        # Ra ≤ 0.4 → суперфиниш
        requirements = get_manufacturing_requirements_from_roughness(0.4)
        
        assert requirements["requires_finish_pass"] is True
        assert requirements["max_feed_reduction"] < 0.5
        assert requirements["surface_quality"] == "super_finish"
    
    def test_required_tool_radius_calculation(self):
        """Тест вычисления требуемого радиуса инструмента."""
        ra_um = 1.6
        feed_mm_rev = 0.2
        
        radius = calculate_required_tool_radius(ra_um, feed_mm_rev)
        
        # Проверяем формулу: r = (f²) / (32 * Ra)
        ra_mm = ra_um / 1000.0
        expected_radius = (feed_mm_rev ** 2) / (32.0 * ra_mm)
        
        assert abs(radius - expected_radius) < 0.0001


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
