"""
Интеграционные тесты полного пути от стандарта до planner.
"""

import pytest
from standards.api.designation_handler import process_designation
from standards.business_logic.requirement_engine import RequirementEngine
from standards.business_logic.constraint_engine import ConstraintEngine
from standards.registry.standard_registry import StandardRegistry


class TestStandardToPlannerIntegration:
    """Интеграционные тесты."""
    
    def test_tolerance_designation_pipeline(self):
        """Тест полного пути для обозначения допуска Ø50 H7."""
        # Обрабатываем обозначение
        result = process_designation("Ø50 H7")
        
        if result:
            assert result.get("entity") is not None
            assert result.get("requirement") is not None
            assert result.get("constraints") is not None
            
            # Проверяем что constraints содержат ограничения
            constraints = result.get("constraints", [])
            assert len(constraints) > 0
    
    def test_thread_designation_pipeline(self):
        """Тест полного пути для обозначения резьбы M42x1.5-6g."""
        result = process_designation("M42x1.5-6g")
        
        if result:
            assert result.get("entity") is not None
            assert result.get("requirement") is not None
            
            entity = result.get("entity")
            if entity:
                assert entity.category == "thread"
    
    def test_surface_roughness_pipeline(self):
        """Тест полного пути для обозначения шероховатости Ra 1.6."""
        result = process_designation("Ra 1.6")
        
        if result:
            assert result.get("entity") is not None
            assert result.get("requirement") is not None
            
            requirement = result.get("requirement")
            if requirement:
                assert requirement.surface_roughness is not None
    
    def test_requirement_to_constraint_pipeline(self):
        """Тест преобразования requirement → constraints."""
        from standards.models import ManufacturingRequirement
        
        req = ManufacturingRequirement(
            tolerance_grade=7,
            dimensional_tolerance=0.015,
            surface_roughness=1.6,
            source_entity_id="test1"
        )
        
        engine = ConstraintEngine()
        constraints = engine.generate_constraints(req)
        
        assert len(constraints) > 0
        
        # Должны быть constraints для допуска и шероховатости
        constraint_ids = [c.constraint_id for c in constraints]
        assert any("finish" in cid.lower() for cid in constraint_ids)
        assert any("feed" in cid.lower() for cid in constraint_ids)
    
    def test_registry_to_requirement_pipeline(self):
        """Тест преобразования registry → requirement."""
        registry = StandardRegistry()
        entity = registry.get_tolerance(designation="H7")
        
        if entity:
            engine = RequirementEngine()
            requirement = engine.build_requirement(entity)
            
            assert requirement is not None
            assert requirement.tolerance_grade is not None
            assert requirement.tolerance_field == "H7"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
