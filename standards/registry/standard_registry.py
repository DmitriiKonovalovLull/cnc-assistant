"""
StandardRegistry — единая точка доступа к стандартам.
Вся система работает только через registry.
"""

from typing import Optional, Dict, Any, List

from standards.models import StandardEntity
from standards.normalization.thread_normalizer import thread_to_entity
from standards.normalization.tolerance_normalizer import tolerance_to_entity
from standards.normalization.fit_normalizer import fit_to_entity
from standards.normalization.surface_normalizer import surface_to_entity


class StandardRegistry:
    """
    Реестр стандартов: получение сущностей по обозначению.
    Пока без персистентной БД — создаём сущности на лету через нормализаторы.
    """

    def __init__(self):
        self._cache: Dict[str, StandardEntity] = {}

    def get_thread(self, designation: str, source: str = "GOST") -> Optional[StandardEntity]:
        """Найти/построить сущность резьбы по обозначению (например M42x1.5-6g)."""
        key = f"thread_{designation.strip()}"
        if key in self._cache:
            return self._cache[key]
        entity = thread_to_entity(designation, source=source)
        if entity:
            self._cache[entity.id] = entity
        return entity

    def get_tolerance(self, designation: str = None, nominal_mm: float = None, grade: int = None, field: str = None, source: str = "GOST") -> Optional[StandardEntity]:
        """
        Найти/построить сущность допуска.
        Варианты вызова:
          get_tolerance(designation="Ø50 H7")
          get_tolerance(nominal_mm=50, field="H7")
          get_tolerance(grade=7)  # IT7
        """
        if designation:
            key = f"tolerance_{designation.strip()}"
            if key in self._cache:
                return self._cache[key]
            entity = tolerance_to_entity(designation, source=source)
        elif nominal_mm is not None and field:
            designation = f"{nominal_mm} {field}"
            entity = tolerance_to_entity(designation, source=source)
        elif grade is not None:
            designation = f"IT{grade}"
            entity = tolerance_to_entity(designation, source=source)
        else:
            return None
        if entity:
            self._cache[entity.id] = entity
        return entity

    def get_fit(self, hole: str, shaft: str, source: str = "GOST") -> Optional[StandardEntity]:
        """Найти/построить сущность посадки по паре отверстие/вал."""
        key = f"fit_{hole}_{shaft}"
        if key in self._cache:
            return self._cache[key]
        entity = fit_to_entity(hole, shaft, source=source)
        if entity:
            self._cache[entity.id] = entity
        return entity

    def get_surface(self, designation: str, source: str = "GOST") -> Optional[StandardEntity]:
        """Найти/построить сущность шероховатости (Ra 1.6, Rz 6.3)."""
        key = f"surface_{designation.strip()}"
        if key in self._cache:
            return self._cache[key]
        entity = surface_to_entity(designation, source=source)
        if entity:
            self._cache[entity.id] = entity
        return entity

    def get_by_designation(self, designation: str, source: str = "GOST") -> Optional[StandardEntity]:
        """
        Универсальный поиск по обозначению: пробуем thread → tolerance → surface.
        Для посадки нужен отдельный вызов get_fit(hole, shaft).
        """
        entity = self.get_thread(designation, source) or self.get_tolerance(designation, source=source) or self.get_surface(designation, source)
        return entity
