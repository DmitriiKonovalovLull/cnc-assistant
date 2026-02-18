"""
Парсер американских стандартов: ANSI, ASME, ASTM, SAE.
Дюймовая система, UNF/UNC резьбы, ANSI допуски (ANSI B4.1).
"""

import re
import logging
from typing import Dict, Any, Optional, List

from standards.ingestion.multi_format_parser import USStandardsParser as BaseUSParser

logger = logging.getLogger(__name__)


class USAStandardsParser(BaseUSParser):
    """
    Специализированный парсер для американских стандартов ANSI, ASME, ASTM, SAE.
    Расширяет USStandardsParser с дополнительной логикой для американских стандартов.
    """

    # Паттерны обозначений американских стандартов
    ANSI_PATTERNS = [
        re.compile(r"ANSI\s+([A-Z]\d+(?:[-.]\d+)?)", re.IGNORECASE),  # ANSI B1.1
        re.compile(r"ASME\s+([A-Z]\d+(?:[-.]\d+)?)", re.IGNORECASE),  # ASME B1.1
        re.compile(r"ASTM\s+([A-Z]\d+(?:[-.]\d+)?)", re.IGNORECASE),  # ASTM A36
        re.compile(r"SAE\s+([A-Z]?\d+(?:[-.]\d+)?)", re.IGNORECASE),  # SAE J429
    ]

    # Обозначения дюймовых резьб
    INCH_THREAD_PATTERNS = [
        re.compile(r"(\d+)\s*/\s*(\d+)\s*-?\s*(\d+)\s*(UNC|UNF|UNEF|UN)", re.IGNORECASE),  # 1/4-20 UNC
        re.compile(r"(\d+)\s*/\s*(\d+)\s*-?\s*(\d+)\s*(NPT|NPTF)", re.IGNORECASE),  # 1/4-18 NPT
        re.compile(r"(\d+)\s*/\s*(\d+)\s*-?\s*(\d+)\s*(BSP|BSPT)", re.IGNORECASE),  # 1/4-19 BSP
    ]

    def __init__(self):
        super().__init__()

    def parse_ansi_designation(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг обозначения ANSI/ASME/ASTM/SAE стандарта.
        Примеры: ANSI B1.1, ASME B1.1, ASTM A36, SAE J429
        
        Args:
            text: Текст с обозначением стандарта
            
        Returns:
            Словарь с распарсенными данными или None
        """
        for pattern in self.ANSI_PATTERNS:
            match = pattern.search(text)
            if match:
                standard_type = match.group(0).split()[0].upper()
                number = match.group(1)
                
                return {
                    "standard_type": standard_type,
                    "number": number,
                    "full_designation": match.group(0).strip(),
                }
        return None

    def parse_inch_thread(self, designation: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг обозначения дюймовой резьбы.
        Примеры: 1/4-20 UNC, 3/8-16 UNF, 1/2-14 NPT
        
        Args:
            designation: Обозначение резьбы
            
        Returns:
            Словарь с распарсенными данными или None
        """
        for pattern in self.INCH_THREAD_PATTERNS:
            match = pattern.match(designation.strip())
            if match:
                numerator = int(match.group(1))
                denominator = int(match.group(2))
                tpi = int(match.group(3))
                series = match.group(4).upper()
                
                diameter_inch = numerator / denominator
                pitch_mm = 25.4 / tpi
                
                return {
                    "diameter_inch": diameter_inch,
                    "diameter_mm": diameter_inch * 25.4,
                    "tpi": tpi,
                    "pitch_mm": pitch_mm,
                    "series": series,
                    "nominal_size": f"{numerator}/{denominator}-{tpi}",
                    "system": "imperial",
                }
        
        return None

    def parse_ansi_tolerance(self, designation: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг обозначения допуска по ANSI B4.1.
        Примеры: 0.500 +0.001/-0.000, 0.500 ±0.001
        
        Args:
            designation: Обозначение допуска
            
        Returns:
            Словарь с распарсенными данными или None
        """
        # Паттерн для ANSI допусков: размер + допуски
        pattern = re.compile(
            r"(\d+\.?\d*)\s*([+-]?\d+\.?\d*)\s*/?\s*([+-]?\d+\.?\d*)?",
            re.IGNORECASE
        )
        match = pattern.match(designation.strip())
        
        if match:
            nominal = float(match.group(1))
            upper = float(match.group(2))
            lower = float(match.group(3)) if match.group(3) else upper
            
            # Конвертируем из дюймов в мм если нужно
            if nominal < 10:  # Вероятно дюймы
                nominal_mm = nominal * 25.4
                upper_mm = upper * 25.4
                lower_mm = lower * 25.4
            else:
                nominal_mm = nominal
                upper_mm = upper
                lower_mm = lower
            
            tolerance_value = abs(upper_mm - lower_mm)
            
            return {
                "nominal_mm": nominal_mm,
                "upper_deviation_mm": upper_mm,
                "lower_deviation_mm": lower_mm,
                "tolerance_value_mm": tolerance_value,
                "system": "ANSI",
            }
        
        return None

    def _normalize_inch_units(self, text: str) -> str:
        """Нормализовать дюймовые единицы в метрические (расширенная версия)."""
        normalized = super()._normalize_inch_units(text)
        
        # Дополнительные замены для американских стандартов
        replacements = [
            (r"(\d+\.?\d*)\s*inches?", r"\1 in"),
            (r"(\d+\.?\d*)\s*in\.", r"\1 in"),
            (r"(\d+)\s*/\s*(\d+)\s*inch", r"\1/\2 in"),
        ]
        
        for pattern, replacement in replacements:
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
        
        return normalized

    def extract_equivalence_info(self, text: str) -> List[Dict[str, Any]]:
        """Извлечь информацию об аналогах с учётом американских стандартов."""
        equivalences = super().extract_equivalence_info(text)
        
        # ANSI/ASME стандарты часто указывают соответствие ISO
        us_patterns = [
            (r"ANSI\s+([A-Z]\d+(?:[-.]\d+)?)\s+equivalent\s+to\s+ISO\s*(\d+(?:[-.]\d+)?)", "equivalent"),
            (r"ASME\s+([A-Z]\d+(?:[-.]\d+)?)\s+based\s+on\s+ISO\s*(\d+(?:[-.]\d+)?)", "based_on"),
            (r"ANSI\s+([A-Z]\d+(?:[-.]\d+)?)\s+corresponds\s+to\s+ISO\s*(\d+(?:[-.]\d+)?)", "equivalent"),
        ]
        
        for pattern, relation_type in us_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                equivalences.append({
                    "source": "ISO",
                    "number": match.group(2),
                    "us_standard": match.group(1),
                    "relation": relation_type,
                    "confidence": 0.8,
                })
        
        return equivalences
