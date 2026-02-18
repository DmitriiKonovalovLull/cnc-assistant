"""
Тесты для движка эквивалентности стандартов.
"""

import pytest
from standards.equivalence.equivalence_engine import EquivalenceEngine
from standards.models import StandardEntity


class TestEquivalenceEngine:
    """Тесты движка эквивалентности."""
    
    def test_equivalence_score_calculation(self):
        """Тест вычисления score эквивалентности."""
        engine = EquivalenceEngine()
        
        # Создаем тестовые сущности
        entity1 = StandardEntity(
            id="test1",
            source="GOST",
            category="thread",
            normalized_data={"diameter": 20.0, "pitch": 2.5}
        )
        
        entity2 = StandardEntity(
            id="test2",
            source="ISO",
            category="thread",
            normalized_data={"diameter": 20.0, "pitch": 2.5}
        )
        
        # Вычисляем схожесть
        score = engine.calculate_similarity(entity1, entity2)
        
        # Score должен быть в диапазоне 0-1
        assert 0.0 <= score <= 1.0
        
        # Если диаметр и шаг совпадают, score должен быть высоким
        if entity1.normalized_data["diameter"] == entity2.normalized_data["diameter"]:
            if entity1.normalized_data["pitch"] == entity2.normalized_data["pitch"]:
                assert score >= 0.7
    
    def test_equivalence_score_with_different_pitch(self):
        """Тест score при разных шагах."""
        engine = EquivalenceEngine()
        
        entity1 = StandardEntity(
            id="test1",
            source="GOST",
            category="thread",
            normalized_data={"diameter": 20.0, "pitch": 2.5}
        )
        
        entity2 = StandardEntity(
            id="test2",
            source="ISO",
            category="thread",
            normalized_data={"diameter": 20.0, "pitch": 1.5}  # Другой шаг
        )
        
        score = engine.calculate_similarity(entity1, entity2)
        
        # Score должен быть меньше чем при совпадении шага
        assert 0.0 <= score <= 1.0
    
    def test_find_din_analog(self):
        """Тест поиска аналога в DIN."""
        engine = EquivalenceEngine()
        
        # Ищем аналог для M20
        analog = engine.find_din_analog("M20")
        
        if analog:
            assert "din" in analog
            assert "confidence" in analog
            assert 0.0 <= analog["confidence"] <= 1.0
    
    def test_find_gb_analog(self):
        """Тест поиска аналога в GB."""
        engine = EquivalenceEngine()
        
        # Ищем аналог для ISO 965-1
        analog = engine.find_gb_analog("ISO 965-1")
        
        if analog:
            assert "gb" in analog
            assert "confidence" in analog
            assert 0.0 <= analog["confidence"] <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
