"""
Парсер японских стандартов: JIS.
Японские технические термины, особые обозначения допусков (JIS B 0401).
"""

import re
import logging
from typing import Dict, Any, Optional, List

from standards.ingestion.multi_format_parser import JapaneseStandardsParser as BaseJapaneseParser

logger = logging.getLogger(__name__)


class JapanStandardsParser(BaseJapaneseParser):
    """
    Специализированный парсер для японских стандартов JIS.
    Расширяет JapaneseStandardsParser с дополнительной логикой для JIS стандартов.
    """

    # Паттерны обозначений JIS стандартов
    JIS_PATTERNS = [
        re.compile(r"JIS\s+([A-Z])\s+(\d+(?:[-.]\d+)?)", re.IGNORECASE),  # JIS B 0205
        re.compile(r"JIS\s+([A-Z])\s+(\d+(?:[-.]\d+)?)\s*-?\s*(\d{4})?", re.IGNORECASE),  # JIS B 0205-2009
    ]

    # Дополнительные японские технические термины для JIS стандартов
    JIS_TERMS = {
        "日本工業規格": "Japanese Industrial Standard",
        "規格": "standard",
        "ねじ": "thread",
        "公差": "tolerance",
        "はめあい": "fit",
        "表面粗さ": "surface roughness",
        "ミリメートル": "mm",
        "インチ": "inch",
    }

    # Специфические обозначения допусков JIS B 0401
    JIS_TOLERANCE_FIELDS = {
        "h": "hole_basic",
        "js": "symmetric",
        "k": "transition",
        "m": "interference",
        "n": "transition",
        "p": "interference",
        "r": "interference",
        "s": "interference",
        "t": "interference",
        "u": "interference",
        "v": "interference",
        "x": "interference",
        "y": "interference",
        "z": "interference",
    }

    def __init__(self):
        super().__init__()
        # Расширяем словарь терминов
        self.JAPANESE_TERMS.update(self.JIS_TERMS)

    def parse_jis_designation(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг обозначения JIS стандарта.
        Примеры: JIS B 0205, JIS B 0401-2009
        
        Args:
            text: Текст с обозначением JIS стандарта
            
        Returns:
            Словарь с распарсенными данными или None
        """
        for pattern in self.JIS_PATTERNS:
            match = pattern.search(text)
            if match:
                category = match.group(1).upper()
                number = match.group(2)
                year = match.group(3) if len(match.groups()) > 2 and match.group(3) else None
                
                return {
                    "standard_type": "JIS",
                    "category": category,
                    "number": number,
                    "year": year,
                    "full_designation": match.group(0).strip(),
                }
        return None

    def parse_jis_tolerance(self, designation: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг обозначения допуска по JIS B 0401.
        Примеры: 50H7, 50g6, 50js6
        
        Args:
            designation: Обозначение допуска
            
        Returns:
            Словарь с распарсенными данными или None
        """
        # Паттерн: число + поле допуска (H7, g6, js6)
        pattern = re.compile(r"(\d+(?:[.,]\d+)?)\s*([A-Za-z]{1,3})\s*(\d+)", re.IGNORECASE)
        match = pattern.match(designation.strip())
        
        if match:
            nominal = float(match.group(1).replace(",", "."))
            field_letter = match.group(2).lower()
            grade = int(match.group(3))
            
            field_type = self.JIS_TOLERANCE_FIELDS.get(field_letter, "unknown")
            
            return {
                "nominal_mm": nominal,
                "tolerance_field": f"{field_letter.upper()}{grade}",
                "tolerance_grade": grade,
                "field_type": field_type,
                "system": "JIS",
            }
        
        return None

    def extract_equivalence_info(self, text: str) -> List[Dict[str, Any]]:
        """Извлечь информацию об аналогах с учётом JIS стандартов."""
        equivalences = super().extract_equivalence_info(text)
        
        # JIS стандарты часто указывают базовый ISO
        jis_patterns = [
            (r"JIS\s+[A-Z]\s+(\d+)\s*は\s*ISO\s*(\d+(?:[-.]\d+)?)\s*に相当", "equivalent"),
            (r"JIS\s+[A-Z]\s+(\d+)\s*は\s*ISO\s*(\d+(?:[-.]\d+)?)\s*に基づく", "based_on"),
            (r"JIS\s+[A-Z]\s+(\d+)\s*equivalent\s+to\s+ISO\s*(\d+(?:[-.]\d+)?)", "equivalent"),
        ]
        
        for pattern, relation_type in jis_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                equivalences.append({
                    "source": "ISO",
                    "number": match.group(2),
                    "jis_number": match.group(1),
                    "relation": relation_type,
                    "confidence": 0.9,
                })
        
        return equivalences
