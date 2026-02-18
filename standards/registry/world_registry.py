"""
WorldStandardRegistry — расширенный реестр стандартов всех мировых систем.
Поиск, сравнение, поиск аналогов, кэширование по системам.
"""

import logging
from typing import Optional, Dict, Any, List, Tuple

from standards.models import StandardEntity, StandardSource, get_region_for_source, normalize_source_string
from standards.registry.standard_registry import StandardRegistry
from standards.equivalence.equivalence_engine import EquivalenceEngine
from standards.normalization.thread_normalizer import thread_to_entity
from standards.normalization.tolerance_normalizer import tolerance_to_entity
from standards.normalization.fit_normalizer import fit_to_entity
from standards.normalization.surface_normalizer import surface_to_entity

logger = logging.getLogger(__name__)


class WorldStandardRegistry(StandardRegistry):
    """
    Расширенный реестр стандартов с поддержкой всех мировых систем.
    Кэширование с разделением по системам, поиск аналогов, сравнение.
    """

    # Предпочтительные системы по регионам
    REGIONAL_PREFERENCES = {
        "CIS": ["GOST", "OST", "ISO"],
        "EU": ["ISO", "DIN", "EN", "BS"],
        "ASIA": ["ISO", "GB", "JIS", "KS"],
        "US": ["ANSI", "ASME", "ISO"],
        "GLOBAL": ["ISO"],
    }

    def __init__(self):
        super().__init__()
        # Кэш с разделением по системам
        self._cache_by_system: Dict[str, Dict[str, StandardEntity]] = {
            "GOST": {},
            "OST": {},
            "ISO": {},
            "DIN": {},
            "GB": {},
            "JIS": {},
            "ANSI": {},
            "ASME": {},
            "BS": {},
            "NF": {},
            "UNI": {},
            "KS": {},
            "IS": {},
            "SIS": {},
            "PN": {},
            "CSN": {},
        }
        self.equivalence_engine = EquivalenceEngine()

    def search_by_designation(self, designation: str, system: Optional[str] = None) -> List[StandardEntity]:
        """
        Поиск по обозначению в конкретной системе или во всех системах.
        
        Args:
            designation: Обозначение стандарта (например "M20", "Ø50 H7")
            system: Система стандартов (GOST, ISO, GB, etc.) или None для поиска во всех
            
        Returns:
            Список найденных сущностей
        """
        if not designation or not designation.strip():
            return []
        
        designation = designation.strip()
        results = []
        
        if system:
            # Поиск в конкретной системе
            system_upper = system.upper()
            entity = self._get_entity_in_system(designation, system_upper)
            if entity:
                results.append(entity)
        else:
            # Поиск во всех системах
            for system_name in self._cache_by_system.keys():
                entity = self._get_entity_in_system(designation, system_name)
                if entity:
                    results.append(entity)
        
        return results

    def _get_entity_in_system(self, designation: str, system: str) -> Optional[StandardEntity]:
        """Получить сущность в конкретной системе (с кэшированием)."""
        # Проверяем кэш
        cache = self._cache_by_system.get(system, {})
        key = f"{designation}_{system}"
        if key in cache:
            return cache[key]
        
        # Пробуем создать через нормализаторы
        entity = None
        
        # Пробуем разные категории
        entity = (
            thread_to_entity(designation, source=system) or
            tolerance_to_entity(designation, source=system) or
            surface_to_entity(designation, source=system)
        )
        
        if entity:
            cache[key] = entity
            self._cache_by_system[system] = cache
            # Также добавляем в общий кэш
            self._cache[entity.id] = entity
        
        return entity

    def find_equivalents(self, designation: str, from_system: str) -> List[Dict[str, Any]]:
        """
        Найти аналоги стандарта в других системах.
        Например: ГОСТ 24705 → ISO 965-1, DIN 13, GB/T 192
        
        Args:
            designation: Обозначение стандарта
            from_system: Исходная система (GOST, ISO, etc.)
            
        Returns:
            Список словарей с информацией об аналогах:
            [
                {"system": "ISO", "designation": "965-1", "score": 0.95, "confidence": 0.9},
                ...
            ]
        """
        if not designation or not from_system:
            return []
        
        # Получаем исходную сущность
        source_entity = self._get_entity_in_system(designation, from_system.upper())
        if not source_entity:
            logger.warning(f"Source entity not found: {designation} in {from_system}")
            return []
        
        # Ищем аналоги в других системах
        equivalents = []
        
        # Используем информацию из regional_specific если есть
        if source_entity.regional_specific:
            for eq_info in source_entity.regional_specific.equivalent_to:
                equivalents.append({
                    "system": eq_info.get("source", "").upper(),
                    "designation": eq_info.get("designation", ""),
                    "score": eq_info.get("confidence", 0.8),
                    "confidence": eq_info.get("confidence", 0.8),
                    "relation": eq_info.get("relation", "equivalent"),
                })
        
        # Ищем через EquivalenceEngine
        for target_system in self._cache_by_system.keys():
            if target_system.upper() == from_system.upper():
                continue
            
            # Пробуем найти аналогичную сущность
            target_entity = self._get_entity_in_system(designation, target_system)
            if target_entity:
                score = self.equivalence_engine.equivalence_score(source_entity, target_entity)
                if score > 0.5:  # Минимальный порог схожести
                    equivalents.append({
                        "system": target_system,
                        "designation": target_entity.raw_designation or designation,
                        "score": score,
                        "confidence": score,
                        "relation": "equivalent",
                    })
        
        # Сортируем по score (убывание)
        equivalents.sort(key=lambda x: x["score"], reverse=True)
        
        return equivalents

    def compare_standards(
        self,
        designation1: str,
        system1: str,
        designation2: str,
        system2: str
    ) -> Dict[str, Any]:
        """
        Сравнить два стандарта из разных систем.
        Возвращает коэффициент схожести (0-100%).
        
        Args:
            designation1: Обозначение первого стандарта
            system1: Система первого стандарта
            designation2: Обозначение второго стандарта
            system2: Система второго стандарта
            
        Returns:
            Словарь с результатами сравнения:
            {
                "similarity_percent": 85.5,
                "score": 0.855,
                "matches": ["diameter", "pitch"],
                "differences": ["tolerance_class"],
                "entity1": {...},
                "entity2": {...},
            }
        """
        entity1 = self._get_entity_in_system(designation1, system1.upper())
        entity2 = self._get_entity_in_system(designation2, system2.upper())
        
        if not entity1 or not entity2:
            return {
                "similarity_percent": 0.0,
                "score": 0.0,
                "error": "One or both entities not found",
            }
        
        # Сравниваем через EquivalenceEngine
        score = self.equivalence_engine.equivalence_score(entity1, entity2)
        similarity_percent = score * 100
        
        # Детальное сравнение
        matches = []
        differences = []
        
        if entity1.category == entity2.category:
            data1 = entity1.normalized_data
            data2 = entity2.normalized_data
            
            # Проверяем совпадения полей
            common_keys = set(data1.keys()) & set(data2.keys())
            for key in common_keys:
                val1 = data1.get(key)
                val2 = data2.get(key)
                if val1 == val2:
                    matches.append(key)
                else:
                    differences.append(key)
        
        return {
            "similarity_percent": round(similarity_percent, 2),
            "score": round(score, 4),
            "matches": matches,
            "differences": differences,
            "entity1": {
                "id": entity1.id,
                "source": entity1.source,
                "category": entity1.category,
                "designation": entity1.raw_designation,
            },
            "entity2": {
                "id": entity2.id,
                "source": entity2.source,
                "category": entity2.category,
                "designation": entity2.raw_designation,
            },
        }

    def get_preferred_system(self, region: str) -> List[str]:
        """
        Получить предпочтительные системы стандартов для региона.
        
        Args:
            region: Регион (CIS, EU, ASIA, US, GLOBAL)
            
        Returns:
            Список систем в порядке предпочтения
        """
        region_upper = region.upper()
        return self.REGIONAL_PREFERENCES.get(region_upper, self.REGIONAL_PREFERENCES["GLOBAL"])

    def get_preferred_system_by_country(self, country: str) -> List[str]:
        """
        Получить предпочтительные системы по стране.
        
        Args:
            country: Название страны (Russia, China, Germany, USA, etc.)
            
        Returns:
            Список систем в порядке предпочтения
        """
        country_lower = country.lower()
        
        # Маппинг стран на регионы и системы
        country_mapping = {
            "russia": ["GOST", "OST", "ISO"],
            "россия": ["GOST", "OST", "ISO"],
            "china": ["GB", "ISO"],
            "китай": ["GB", "ISO"],
            "germany": ["DIN", "ISO", "EN"],
            "германия": ["DIN", "ISO", "EN"],
            "usa": ["ANSI", "ASME", "ISO"],
            "united states": ["ANSI", "ASME", "ISO"],
            "japan": ["JIS", "ISO"],
            "япония": ["JIS", "ISO"],
            "uk": ["BS", "ISO", "EN"],
            "britain": ["BS", "ISO", "EN"],
            "france": ["NF", "ISO", "EN"],
            "франция": ["NF", "ISO", "EN"],
            "italy": ["UNI", "ISO", "EN"],
            "италия": ["UNI", "ISO", "EN"],
        }
        
        return country_mapping.get(country_lower, self.REGIONAL_PREFERENCES["GLOBAL"])

    def add_equivalence(
        self,
        designation1: str,
        system1: str,
        designation2: str,
        system2: str,
        confidence: float = 0.9,
        relation: str = "equivalent"
    ) -> None:
        """
        Добавить информацию об эквивалентности двух стандартов.
        
        Args:
            designation1: Обозначение первого стандарта
            system1: Система первого стандарта
            designation2: Обозначение второго стандарта
            system2: Система второго стандарта
            confidence: Уверенность (0-1)
            relation: Тип связи (equivalent, modified, based_on, etc.)
        """
        entity1 = self._get_entity_in_system(designation1, system1.upper())
        entity2 = self._get_entity_in_system(designation2, system2.upper())
        
        if entity1:
            entity1.add_equivalent(
                source=system2.upper(),
                designation=designation2,
                confidence=confidence,
                notes=f"{relation} to {system2} {designation2}"
            )
        
        if entity2:
            entity2.add_equivalent(
                source=system1.upper(),
                designation=designation1,
                confidence=confidence,
                notes=f"{relation} to {system1} {designation1}"
            )

    def get_statistics(self) -> Dict[str, Any]:
        """
        Получить статистику по кэшу.
        
        Returns:
            Словарь со статистикой:
            {
                "total_entities": 150,
                "by_system": {"GOST": 50, "ISO": 30, ...},
                "by_category": {"thread": 80, "tolerance": 40, ...},
            }
        """
        stats = {
            "total_entities": len(self._cache),
            "by_system": {},
            "by_category": {},
        }
        
        # Статистика по системам
        for system, cache in self._cache_by_system.items():
            stats["by_system"][system] = len(cache)
        
        # Статистика по категориям
        for entity in self._cache.values():
            category = entity.category
            stats["by_category"][category] = stats["by_category"].get(category, 0) + 1
        
        return stats
