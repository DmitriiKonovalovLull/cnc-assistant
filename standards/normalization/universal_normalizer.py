"""
UniversalNormalizer — универсальный нормализатор для всех мировых систем стандартов.
Приводит стандарты всех систем к единому формату (ThreadData, ToleranceData).
"""

import re
import logging
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field

from standards.models.models import ThreadData
from standards.normalization.thread_normalizer import normalize_metric_thread
from standards.normalization.tolerance_normalizer import normalize_tolerance_field
from standards.ingestion.country_parsers.usa_parser import USAStandardsParser

logger = logging.getLogger(__name__)


@dataclass
class ToleranceData:
    """Нормализованные данные допуска в мм."""
    tolerance_grade: Optional[int] = None  # IT6, IT7, etc.
    tolerance_field: Optional[str] = None  # H7, g6, etc.
    nominal_mm: Optional[float] = None  # Номинальный размер в мм
    upper_deviation_mm: Optional[float] = None  # Верхнее отклонение в мм
    lower_deviation_mm: Optional[float] = None  # Нижнее отклонение в мм
    tolerance_value_mm: Optional[float] = None  # Значение допуска в мм
    system: str = "metric"  # metric, imperial


class UniversalNormalizer:
    """
    Универсальный нормализатор стандартов всех систем.
    Приводит к единому формату независимо от исходной системы.
    """

    # Константы конвертации
    INCH_TO_MM = 25.4
    MM_TO_INCH = 1.0 / 25.4
    CM_TO_MM = 10.0
    M_TO_MM = 1000.0

    # Маппинг систем на региональные парсеры
    SYSTEM_PARSERS = {
        "ANSI": USAStandardsParser,
        "ASME": USAStandardsParser,
        "ASTM": USAStandardsParser,
        "SAE": USAStandardsParser,
    }

    def convert_to_metric(self, value: float, from_unit: str) -> float:
        """
        Конвертировать значение в миллиметры.
        Точное преобразование: 1 дюйм = 25.4 мм.
        
        Args:
            value: Значение для конвертации
            from_unit: Исходная единица (inch, mm, m, cm)
            
        Returns:
            Значение в миллиметрах
        """
        from_unit_lower = from_unit.lower().strip()
        
        if from_unit_lower in ["mm", "millimeter", "миллиметр"]:
            return value
        elif from_unit_lower in ["inch", "in", "дюйм", "inches"]:
            return value * self.INCH_TO_MM
        elif from_unit_lower in ["cm", "centimeter", "сантиметр"]:
            return value * self.CM_TO_MM
        elif from_unit_lower in ["m", "meter", "метр", "metre"]:
            return value * self.M_TO_MM
        else:
            logger.warning(f"Unknown unit: {from_unit}, assuming mm")
            return value

    def normalize_thread(self, designation: str, system: str) -> Optional[ThreadData]:
        """
        Нормализовать обозначение резьбы любой системы в единый ThreadData.
        Конвертирует дюймовые резьбы в мм.
        
        Args:
            designation: Обозначение резьбы (M20, 1/4-20 UNC, etc.)
            system: Система стандартов (GOST, ISO, DIN, GB, JIS, ANSI, ASME)
            
        Returns:
            ThreadData с нормализованными данными или None
        """
        if not designation or not system:
            return None
        
        system_upper = system.upper()
        designation = designation.strip()
        
        # Метрические резьбы (GOST, ISO, DIN, GB, JIS)
        if system_upper in ["GOST", "ISO", "DIN", "GB", "JIS"]:
            return self._normalize_metric_thread(designation, system_upper)
        
        # Дюймовые резьбы (ANSI, ASME, SAE)
        elif system_upper in ["ANSI", "ASME", "SAE", "ASTM"]:
            return self._normalize_inch_thread(designation, system_upper)
        
        else:
            logger.warning(f"Unknown system for thread normalization: {system}")
            # Пробуем как метрическую
            return self._normalize_metric_thread(designation, system_upper)

    def _normalize_metric_thread(self, designation: str, system: str) -> Optional[ThreadData]:
        """Нормализовать метрическую резьбу."""
        norm_data = normalize_metric_thread(designation)
        if not norm_data:
            return None
        
        return ThreadData(
            thread_type="metric",
            diameter=norm_data.get("diameter"),
            diameter_unit="mm",
            pitch=norm_data.get("pitch"),
            tolerance_class=norm_data.get("tolerance_class"),
            profile_angle=norm_data.get("profile_angle", 60.0),
            system="metric",
        )

    def _normalize_inch_thread(self, designation: str, system: str) -> Optional[ThreadData]:
        """Нормализовать дюймовую резьбу (ANSI/ASME)."""
        # Используем USAStandardsParser для парсинга
        parser = USAStandardsParser()
        inch_data = parser.parse_inch_thread(designation)
        
        if not inch_data:
            return None
        
        return ThreadData(
            thread_type=inch_data.get("series", "unified").lower(),
            diameter=inch_data.get("diameter_mm"),  # Уже в мм
            diameter_unit="mm",
            pitch=inch_data.get("pitch_mm"),  # Уже в мм
            tpi=inch_data.get("tpi"),
            thread_series=inch_data.get("series"),
            nominal_size=inch_data.get("nominal_size"),
            system="imperial",
        )

    def normalize_tolerance(self, tolerance: str, system: str) -> Optional[ToleranceData]:
        """
        Нормализовать обозначение допуска любой системы в единый ToleranceData в мм.
        Примеры: "H7" (ISO), "H7" (GB), "2A" (ANSI), "h6" (JIS)
        
        Args:
            tolerance: Обозначение допуска
            system: Система стандартов (GOST, ISO, DIN, GB, JIS, ANSI)
            
        Returns:
            ToleranceData с нормализованными данными в мм или None
        """
        if not tolerance or not system:
            return None
        
        system_upper = system.upper()
        tolerance = tolerance.strip()
        
        # Метрические допуски (GOST, ISO, DIN, GB, JIS)
        if system_upper in ["GOST", "ISO", "DIN", "GB", "JIS"]:
            return self._normalize_metric_tolerance(tolerance, system_upper)
        
        # Американские допуски (ANSI)
        elif system_upper in ["ANSI", "ASME"]:
            return self._normalize_ansi_tolerance(tolerance, system_upper)
        
        else:
            logger.warning(f"Unknown system for tolerance normalization: {system}")
            return self._normalize_metric_tolerance(tolerance, system_upper)

    def _normalize_metric_tolerance(self, tolerance: str, system: str) -> Optional[ToleranceData]:
        """Нормализовать метрический допуск."""
        norm_data = normalize_tolerance_field(tolerance)
        if not norm_data:
            return None
        
        return ToleranceData(
            tolerance_grade=norm_data.get("tolerance_grade"),
            tolerance_field=norm_data.get("tolerance_field"),
            nominal_mm=norm_data.get("nominal_mm"),
            system="metric",
        )

    def _normalize_ansi_tolerance(self, tolerance: str, system: str) -> Optional[ToleranceData]:
        """Нормализовать ANSI допуск."""
        # ANSI допуски могут быть в формате "2A", "3B" или "0.500 +0.001/-0.000"
        parser = USAStandardsParser()
        
        # Пробуем как ANSI B4.1 формат
        ansi_data = parser.parse_ansi_tolerance(tolerance)
        if ansi_data:
            return ToleranceData(
                nominal_mm=ansi_data.get("nominal_mm"),
                upper_deviation_mm=ansi_data.get("upper_deviation_mm"),
                lower_deviation_mm=ansi_data.get("lower_deviation_mm"),
                tolerance_value_mm=ansi_data.get("tolerance_value_mm"),
                system="imperial",
            )
        
        # Пробуем как класс допуска (2A, 3B)
        ansi_class_pattern = re.compile(r"(\d+)([A-Z])", re.IGNORECASE)
        match = ansi_class_pattern.match(tolerance)
        if match:
            grade = int(match.group(1))
            letter = match.group(2).upper()
            # ANSI классы приблизительно соответствуют IT классам
            # 2A ≈ IT6, 3A ≈ IT7, etc.
            it_grade = grade + 4  # Приблизительное соответствие
            
            return ToleranceData(
                tolerance_grade=it_grade,
                tolerance_field=f"{letter}{grade}",
                system="imperial",
            )
        
        return None

    def get_standard_family(self, designation: str) -> Optional[Dict[str, Any]]:
        """
        Определить семейство стандарта и родительский стандарт.
        Например: "GB/T 192" → family="thread", parent="ISO 965"
        
        Args:
            designation: Обозначение стандарта
            
        Returns:
            Словарь с информацией о семействе:
            {
                "family": "thread",
                "parent": "ISO 965-1",
                "confidence": 0.9,
                "system": "GB"
            }
        """
        if not designation:
            return None
        
        designation = designation.strip()
        
        # Определяем систему по обозначению
        system = self._detect_system(designation)
        if not system:
            return None
        
        # Определяем категорию по ключевым словам
        category = self._detect_category(designation)
        
        # Ищем родительский стандарт через equivalence_engine
        parent = self._find_parent_standard(designation, system, category)
        
        return {
            "family": category,
            "parent": parent,
            "confidence": 0.9 if parent else 0.5,
            "system": system,
        }

    def _detect_system(self, designation: str) -> Optional[str]:
        """Определить систему стандарта по обозначению."""
        designation_upper = designation.upper()
        
        if re.search(r"ГОСТ\s*Р?", designation_upper):
            return "GOST"
        elif re.search(r"ОСТ", designation_upper):
            return "OST"
        elif re.search(r"GB[/-]?T?", designation_upper):
            return "GB"
        elif re.search(r"JIS", designation_upper):
            return "JIS"
        elif re.search(r"DIN", designation_upper):
            return "DIN"
        elif re.search(r"ANSI", designation_upper):
            return "ANSI"
        elif re.search(r"ASME", designation_upper):
            return "ASME"
        elif re.search(r"ISO", designation_upper):
            return "ISO"
        elif re.search(r"BS", designation_upper):
            return "BS"
        elif re.search(r"NF", designation_upper):
            return "NF"
        elif re.search(r"UNI", designation_upper):
            return "UNI"
        else:
            # Пробуем определить по контексту
            if re.search(r"M\d+", designation_upper):
                return "ISO"  # Метрическая резьба обычно ISO/GOST
            elif re.search(r"\d+/\d+-\d+\s*(UNC|UNF|NPT)", designation_upper):
                return "ANSI"  # Дюймовая резьба обычно ANSI
        
        return None

    def _detect_category(self, designation: str) -> str:
        """Определить категорию стандарта по обозначению."""
        designation_upper = designation.upper()
        designation_lower = designation.lower()
        
        # Резьбы
        if (re.search(r"M\d+", designation_upper) or
            re.search(r"\d+/\d+-\d+\s*(UNC|UNF|NPT|BSP)", designation_upper) or
            re.search(r"thread|резьб", designation_lower)):
            return "thread"
        
        # Допуски
        if (re.search(r"[Hh]\d+|g\d+|IT\d+", designation_upper) or
            re.search(r"tolerance|допуск", designation_lower)):
            return "tolerance"
        
        # Посадки
        if (re.search(r"[Hh]\d+/[a-z]\d+", designation_lower) or
            re.search(r"fit|посад", designation_lower)):
            return "fit"
        
        # Шероховатость
        if (re.search(r"Ra\s*\d+|Rz\s*\d+", designation_upper) or
            re.search(r"roughness|шероховат", designation_lower)):
            return "surface"
        
        return "unknown"

    def _find_parent_standard(self, designation: str, system: str, category: str) -> Optional[str]:
        """
        Найти родительский стандарт через equivalence_engine.
        Например, GB/T 192 → ISO 965-1
        """
        try:
            from standards.equivalence.equivalence_engine import EquivalenceEngine
            engine = EquivalenceEngine()
            
            # Ищем в таблицах соответствия
            if system == "GB":
                parent_info = engine.find_gb_analog(f"ISO {designation}")
                if parent_info:
                    return f"ISO {parent_info.get('iso', '')}"
            
            # Ищем через таблицы соответствия
            equivalence_tables = engine.equivalence_tables
            
            for table_name, table_data in equivalence_tables.items():
                mappings = table_data.get("mappings", [])
                for mapping in mappings:
                    # Проверяем соответствие
                    system_lower = system.lower()
                    if system_lower in mapping:
                        mapping_value = mapping.get(system_lower)
                        if mapping_value and mapping_value in designation:
                            # Находим родительский стандарт
                            if "iso" in mapping:
                                return f"ISO {mapping.get('iso')}"
                            elif "gost" in mapping:
                                return f"GOST {mapping.get('gost')}"
                            elif "din" in mapping:
                                return f"DIN {mapping.get('din')}"
            
        except Exception as e:
            logger.debug(f"Error finding parent standard: {e}")
        
        return None

    def normalize_all(self, designation: str, system: str, category: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Универсальная нормализация стандарта любого типа.
        
        Args:
            designation: Обозначение стандарта
            system: Система стандартов
            category: Категория (thread, tolerance, fit, surface) или None для автоопределения
            
        Returns:
            Словарь с нормализованными данными или None
        """
        if not designation or not system:
            return None
        
        if category is None:
            category = self._detect_category(designation)
        
        if category == "thread":
            thread_data = self.normalize_thread(designation, system)
            if thread_data:
                return {
                    "category": "thread",
                    "data": thread_data,
                    "normalized": True,
                }
        
        elif category == "tolerance":
            tolerance_data = self.normalize_tolerance(designation, system)
            if tolerance_data:
                return {
                    "category": "tolerance",
                    "data": tolerance_data,
                    "normalized": True,
                }
        
        return None
