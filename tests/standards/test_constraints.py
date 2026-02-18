"""
Тесты для генерации технологических ограничений.
"""

import pytest
from standards.models import ManufacturingRequirement, ProcessConstraint
from standards.business_logic.constraint_engine import ConstraintEngine


class TestConstraintEngine:
    """Тесты генерации ограничений."""
    
    def test_constraint_generation_it7(self):
        """Тест генерации ограничений для IT7."""
        req = ManufacturingRequirement(
            tolerance_grade=7,
            dimensional_tolerance=0.015,
            source_entity_id="test1"
        )
        
        engine = ConstraintEngine()
        constraints = engine.generate_constraints(req)
        
        # Должно быть ограничение на чистую обработку
        finish_constraints = [c for c in constraints if "finish" in c.constraint_id.lower()]
        assert len(finish_constraints) > 0
    
    def test_constraint_generation_low_roughness(self):
        """Тест генерации ограничений для малой шероховатости."""
        req = ManufacturingRequirement(
            surface_roughness=1.6,
            source_entity_id="test2"
        )
        
        engine = ConstraintEngine()
        constraints = engine.generate_constraints(req)
        
        # Должно быть ограничение на низкую подачу
        feed_constraints = [c for c in constraints if "feed" in c.constraint_id.lower()]
        assert len(feed_constraints) > 0
    
    def test_constraint_generation_interference_fit(self):
        """Тест генерации ограничений для посадки с натягом."""
        req = ManufacturingRequirement(
            fit_type="interference",
            source_entity_id="test3"
        )
        
        engine = ConstraintEngine()
        constraints = engine.generate_constraints(req)
        
        # Должно быть ограничение на контроль температуры
        thermal_constraints = [c for c in constraints if "thermal" in c.constraint_id.lower()]
        assert len(thermal_constraints) > 0
    
    def test_constraint_generation_thread(self):
        """Тест генерации ограничений для резьбы."""
        req = ManufacturingRequirement(
            thread_pitch=1.5,
            thread_tolerance_class="6g",
            source_entity_id="test4"
        )
        
        engine = ConstraintEngine()
        constraints = engine.generate_constraints(req)
        
        # Должно быть ограничение на операцию резьбы
        thread_constraints = [c for c in constraints if "thread" in c.constraint_id.lower()]
        assert len(thread_constraints) > 0
    
    def test_constraint_parameters(self):
        """Тест наличия параметров в ограничениях."""
        req = ManufacturingRequirement(
            tolerance_grade=7,
            surface_roughness=1.6,
            source_entity_id="test5"
        )
        
        engine = ConstraintEngine()
        constraints = engine.generate_constraints(req)
        
        # Все ограничения должны иметь параметры или описание
        for constraint in constraints:
            assert constraint.constraint_id
            assert constraint.description or constraint.parameters


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
