"""
EquivalenceEngine — определение аналогов между всеми мировыми системами стандартов.
Таблицы соответствия, расчет схожести, поиск аналогов, формулы пересчета.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from standards.models import StandardEntity

logger = logging.getLogger(__name__)

# Путь к файлу данных
EQUIVALENCE_DATA_FILE = Path(__file__).parent / "equivalence_data.json"


@dataclass
class EquivalenceResult:
    """Результат сравнения: сущность-аналог и оценка совпадения (0..1)."""
    entity: StandardEntity
    score: float
    details: Optional[str] = None


class EquivalenceEngine:
    """
    Поиск аналогов и оценка совпадения между всеми мировыми системами стандартов.
    Таблицы соответствия ГОСТ ↔ ISO, ГОСТ ↔ DIN, GB ↔ ISO, JIS ↔ ISO, ANSI ↔ ISO.
    """

    def __init__(self, data_file: Optional[Path] = None):
        """
        Инициализация движка эквивалентности.
        
        Args:
            data_file: Путь к файлу с данными эквивалентности (по умолчанию equivalence_data.json)
        """
        self.data_file = data_file or EQUIVALENCE_DATA_FILE
        self.equivalence_tables: Dict[str, Any] = {}
        self.thread_equivalents: Dict[str, Dict[str, str]] = {}
        self.tolerance_equivalents: Dict[str, Dict[str, str]] = {}
        self._load_equivalence_data()

    def _load_equivalence_data(self) -> None:
        """Загрузить базу знаний эквивалентности из JSON файла."""
        if not self.data_file.exists():
            logger.warning(f"Equivalence data file not found: {self.data_file}")
            self._create_default_data()
            return
        
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self.equivalence_tables = data.get("equivalence_tables", {})
            self.thread_equivalents = data.get("thread_equivalents", {})
            self.tolerance_equivalents = data.get("tolerance_equivalents", {})
            
            logger.info(f"Loaded equivalence data: {len(self.equivalence_tables)} tables, "
                       f"{len(self.thread_equivalents)} thread equivalents, "
                       f"{len(self.tolerance_equivalents)} tolerance equivalents")
        except Exception as e:
            logger.error(f"Failed to load equivalence data: {e}")
            self._create_default_data()

    def _create_default_data(self) -> None:
        """Создать данные по умолчанию если файл не найден."""
        self.equivalence_tables = {
            "GOST_ISO": {
                "mappings": [
                    {"gost": "24705", "iso": "965-1", "category": "thread", "confidence": 0.95},
                    {"gost": "25346", "iso": "286-1", "category": "tolerance", "confidence": 0.95},
                ]
            },
            "GB_ISO": {
                "mappings": [
                    {"gb": "192", "iso": "965-1", "category": "thread", "confidence": 0.90},
                ]
            },
        }
        self.thread_equivalents = {
            "M20": {"gost": "24705", "iso": "965-1", "din": "13-1", "gb": "192"},
        }
        self.tolerance_equivalents = {
            "IT7": {"gost": "25346", "iso": "286-1", "gb": "1800"},
        }

    def calculate_similarity(self, standard1: StandardEntity, standard2: StandardEntity) -> float:
        """
        Рассчитать схожесть двух стандартов на основе параметров.
        Анализирует диаметры, допуски, шаги и другие параметры.
        Возвращает процент совпадения (0.0 - 1.0).
        
        Args:
            standard1: Первая сущность стандарта
            standard2: Вторая сущность стандарта
            
        Returns:
            Коэффициент схожести (0.0 - 1.0)
        """
        if not standard1 or not standard2:
            return 0.0
        
        # Разные категории — схожесть 0
        if standard1.category != standard2.category:
            return 0.0
        
        data1 = standard1.normalized_data
        data2 = standard2.normalized_data
        category = standard1.category
        
        if category == "thread":
            return self._calculate_thread_similarity(data1, data2)
        elif category == "tolerance":
            return self._calculate_tolerance_similarity(data1, data2)
        elif category == "fit":
            return self._calculate_fit_similarity(data1, data2)
        elif category == "surface":
            return self._calculate_surface_similarity(data1, data2)
        else:
            # Для других категорий — простое сравнение полей
            return self._calculate_generic_similarity(data1, data2)

    def _calculate_thread_similarity(self, data1: Dict[str, Any], data2: Dict[str, Any]) -> float:
        """Рассчитать схожесть резьб."""
        score = 0.0
        total_weight = 0.0
        
        # Диаметр (вес 0.4)
        d1 = data1.get("diameter")
        d2 = data2.get("diameter")
        if d1 is not None and d2 is not None:
            if abs(d1 - d2) < 0.01:  # Точное совпадение
                score += 0.4
            elif abs(d1 - d2) / max(d1, d2) < 0.05:  # В пределах 5%
                score += 0.3
            total_weight += 0.4
        
        # Шаг (вес 0.4)
        p1 = data1.get("pitch")
        p2 = data2.get("pitch")
        if p1 is not None and p2 is not None:
            if abs(p1 - p2) < 0.01:
                score += 0.4
            elif abs(p1 - p2) / max(p1, p2) < 0.05:
                score += 0.3
            total_weight += 0.4
        
        # Класс допуска (вес 0.2)
        t1 = data1.get("tolerance_class")
        t2 = data2.get("tolerance_class")
        if t1 and t2:
            if t1.upper() == t2.upper():
                score += 0.2
            total_weight += 0.2
        
        return score / total_weight if total_weight > 0 else 0.0

    def _calculate_tolerance_similarity(self, data1: Dict[str, Any], data2: Dict[str, Any]) -> float:
        """Рассчитать схожесть допусков."""
        score = 0.0
        
        # Класс допуска (IT6, IT7, etc.)
        g1 = data1.get("tolerance_grade")
        g2 = data2.get("tolerance_grade")
        if g1 == g2:
            score += 0.6
        
        # Поле допуска (H7, g6, etc.)
        f1 = data1.get("tolerance_field")
        f2 = data2.get("tolerance_field")
        if f1 and f2 and f1.upper() == f2.upper():
            score += 0.4
        
        return min(score, 1.0)

    def _calculate_fit_similarity(self, data1: Dict[str, Any], data2: Dict[str, Any]) -> float:
        """Рассчитать схожесть посадок."""
        score = 0.0
        
        # Тип посадки
        t1 = data1.get("fit_type")
        t2 = data2.get("fit_type")
        if t1 == t2:
            score += 0.5
        
        # Поля отверстия и вала
        h1 = data1.get("hole")
        h2 = data2.get("hole")
        s1 = data1.get("shaft")
        s2 = data2.get("shaft")
        
        if h1 == h2:
            score += 0.25
        if s1 == s2:
            score += 0.25
        
        return min(score, 1.0)

    def _calculate_surface_similarity(self, data1: Dict[str, Any], data2: Dict[str, Any]) -> float:
        """Рассчитать схожесть шероховатости."""
        ra1 = data1.get("ra_um")
        ra2 = data2.get("ra_um")
        
        if ra1 is not None and ra2 is not None:
            # Сравниваем в пределах одного ряда (Ra 0.8, 1.6, 3.2, 6.3, ...)
            ratio = max(ra1, ra2) / min(ra1, ra2) if min(ra1, ra2) > 0 else 0
            if ratio <= 1.2:  # В пределах 20%
                return 0.9
            elif ratio <= 2.0:  # В пределах одного ряда
                return 0.7
            else:
                return 0.3
        
        return 0.0

    def _calculate_generic_similarity(self, data1: Dict[str, Any], data2: Dict[str, Any]) -> float:
        """Общий расчет схожести для неизвестных категорий."""
        common_keys = set(data1.keys()) & set(data2.keys())
        if not common_keys:
            return 0.0
        
        matches = sum(1 for k in common_keys if data1[k] == data2[k])
        return matches / len(common_keys) if common_keys else 0.0

    def find_din_analog(self, gost_designation: str) -> Optional[Dict[str, Any]]:
        """
        Найти аналог ГОСТ стандарта в DIN.
        Пример: M20 → DIN 13-1
        
        Args:
            gost_designation: Обозначение ГОСТ стандарта
            
        Returns:
            Словарь с информацией об аналоге или None
        """
        # Ищем в таблице соответствия
        gost_iso_table = self.equivalence_tables.get("GOST_DIN", {})
        mappings = gost_iso_table.get("mappings", [])
        
        for mapping in mappings:
            if mapping.get("gost") in gost_designation:
                return {
                    "din": mapping.get("din"),
                    "confidence": mapping.get("confidence", 0.8),
                    "category": mapping.get("category"),
                }
        
        # Ищем по обозначению резьбы
        if gost_designation.startswith("M"):
            thread_key = gost_designation.split()[0]  # "M20" из "M20 ГОСТ 24705"
            if thread_key in self.thread_equivalents:
                din_std = self.thread_equivalents[thread_key].get("din")
                if din_std:
                    return {
                        "din": din_std,
                        "confidence": 0.85,
                        "category": "thread",
                    }
        
        return None

    def find_gb_analog(self, iso_designation: str) -> Optional[Dict[str, Any]]:
        """
        Найти китайский аналог ISO стандарта.
        Пример: ISO 965-1 → GB/T 192-2003
        
        Args:
            iso_designation: Обозначение ISO стандарта
            
        Returns:
            Словарь с информацией об аналоге или None
        """
        # Ищем в таблице соответствия
        gb_iso_table = self.equivalence_tables.get("GB_ISO", {})
        mappings = gb_iso_table.get("mappings", [])
        
        for mapping in mappings:
            iso_num = mapping.get("iso")
            if iso_num and iso_num in iso_designation:
                return {
                    "gb": mapping.get("gb"),
                    "confidence": mapping.get("confidence", 0.9),
                    "category": mapping.get("category"),
                    "note": mapping.get("note", ""),
                }
        
        # Ищем по обозначению резьбы
        if "M" in iso_designation:
            # Извлекаем обозначение резьбы (M20, M42x1.5)
            import re
            thread_match = re.search(r"M\d+(?:x\d+\.?\d*)?", iso_designation)
            if thread_match:
                thread_key = thread_match.group(0)
                if thread_key in self.thread_equivalents:
                    gb_std = self.thread_equivalents[thread_key].get("gb")
                    if gb_std:
                        return {
                            "gb": gb_std,
                            "confidence": 0.90,
                            "category": "thread",
                        }
        
        return None

    def get_conversion_formula(self, from_system: str, to_system: str, parameter: str) -> Optional[Dict[str, Any]]:
        """
        Получить формулу пересчета параметра между системами.
        Например, дюймы ↔ мм, градусы Фаренгейта ↔ Цельсия.
        
        Args:
            from_system: Исходная система (ANSI, ISO, etc.)
            to_system: Целевая система (ISO, GOST, etc.)
            parameter: Параметр для пересчета (length, angle, temperature, etc.)
            
        Returns:
            Словарь с формулой или None:
            {
                "formula": "value_mm = value_inch * 25.4",
                "reverse": "value_inch = value_mm / 25.4",
                "description": "Дюймы в миллиметры"
            }
        """
        # Таблица формул пересчета
        conversion_formulas = {
            ("ANSI", "ISO", "length"): {
                "formula": "value_mm = value_inch * 25.4",
                "reverse": "value_inch = value_mm / 25.4",
                "description": "Дюймы в миллиметры",
                "constant": 25.4,
            },
            ("ISO", "ANSI", "length"): {
                "formula": "value_inch = value_mm / 25.4",
                "reverse": "value_mm = value_inch * 25.4",
                "description": "Миллиметры в дюймы",
                "constant": 1.0 / 25.4,
            },
            ("ANSI", "ISO", "thread_pitch"): {
                "formula": "pitch_mm = 25.4 / tpi",
                "reverse": "tpi = 25.4 / pitch_mm",
                "description": "TPI (Threads Per Inch) в шаг в мм",
                "constant": 25.4,
            },
            ("ISO", "ANSI", "thread_pitch"): {
                "formula": "tpi = 25.4 / pitch_mm",
                "reverse": "pitch_mm = 25.4 / tpi",
                "description": "Шаг в мм в TPI",
                "constant": 25.4,
            },
        }
        
        key = (from_system.upper(), to_system.upper(), parameter.lower())
        return conversion_formulas.get(key)

    def find_equivalents(self, entity: StandardEntity, target_source: str = "ISO") -> List[EquivalenceResult]:
        """
        Найти аналоги entity в другой системе (target_source).
        Использует таблицы соответствия и расчет схожести.
        
        Args:
            entity: Сущность стандарта
            target_source: Целевая система (ISO, DIN, GB, etc.)
            
        Returns:
            Список EquivalenceResult с найденными аналогами
        """
        if not entity or entity.source == target_source.upper():
            return []
        
        results = []
        
        # Ищем в таблицах соответствия
        source_upper = entity.source.upper()
        table_key = f"{source_upper}_{target_source.upper()}"
        
        if table_key in self.equivalence_tables:
            table = self.equivalence_tables[table_key]
            mappings = table.get("mappings", [])
            
            for mapping in mappings:
                source_key = source_upper.lower()
                target_key = target_source.lower()
                
                if source_key in mapping and target_key in mapping:
                    # Создаем результат на основе таблицы
                    confidence = mapping.get("confidence", 0.8)
                    results.append(EquivalenceResult(
                        entity=None,  # TODO: создать entity из mapping
                        score=confidence,
                        details=f"From equivalence table: {mapping.get(source_key)} → {mapping.get(target_key)}"
                    ))
        
        return results

    def equivalence_score(self, entity_a: StandardEntity, entity_b: StandardEntity) -> float:
        """
        Оценка совпадения двух сущностей (0..1).
        Использует calculate_similarity для детального анализа.
        
        Args:
            entity_a: Первая сущность
            entity_b: Вторая сущность
            
        Returns:
            Коэффициент схожести (0.0 - 1.0)
        """
        return self.calculate_similarity(entity_a, entity_b)
