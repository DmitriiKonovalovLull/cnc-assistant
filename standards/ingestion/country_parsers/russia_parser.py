"""
Парсер российских стандартов: ГОСТ, ГОСТ Р, ОСТ, ТУ.
Советские и российские стандарты, особенности обозначений.
"""

import re
import logging
from typing import Dict, Any, Optional, List

from standards.ingestion.multi_format_parser import StandardsParser

logger = logging.getLogger(__name__)


class RussiaStandardsParser(StandardsParser):
    """
    Специализированный парсер для российских стандартов ГОСТ, ГОСТ Р, ОСТ, ТУ.
    Особенности советских и российских обозначений.
    """

    # Паттерны обозначений российских стандартов
    GOST_PATTERNS = [
        re.compile(r"ГОСТ\s+Р\s+(\d+(?:[-.]\d+)?)", re.IGNORECASE),  # ГОСТ Р 12345
        re.compile(r"ГОСТ\s+(\d+(?:[-.]\d+)?)", re.IGNORECASE),  # ГОСТ 24705
        re.compile(r"ОСТ\s+(\d+(?:[-.]\d+)?)", re.IGNORECASE),  # ОСТ 1 33056
        re.compile(r"ТУ\s+(\d+(?:[-.]\d+)?)", re.IGNORECASE),  # ТУ 12345
    ]

    # Особенности обозначений советских стандартов
    SOVIET_PATTERNS = [
        re.compile(r"(\d+)\s+ГОСТ\s+(\d+(?:[-.]\d+)?)", re.IGNORECASE),  # 1 ГОСТ 24705 (старый формат)
        re.compile(r"ГОСТ\s+(\d+(?:[-.]\d+)?)\s*-?\s*(\d{2})", re.IGNORECASE),  # ГОСТ 24705-81 (с годом)
    ]

    # Российские технические термины
    RUSSIAN_TERMS = {
        "резьба": "thread",
        "допуск": "tolerance",
        "посадка": "fit",
        "шероховатость": "surface roughness",
        "миллиметр": "mm",
        "дюйм": "inch",
        "стандарт": "standard",
    }

    def __init__(self):
        super().__init__()

    def parse_gost_designation(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг обозначения ГОСТ/ГОСТ Р/ОСТ/ТУ стандарта.
        Примеры: ГОСТ 24705, ГОСТ Р 12345, ОСТ 1 33056, ТУ 12345
        
        Args:
            text: Текст с обозначением стандарта
            
        Returns:
            Словарь с распарсенными данными или None
        """
        # Сначала пробуем современные форматы
        for pattern in self.GOST_PATTERNS:
            match = pattern.search(text)
            if match:
                full_match = match.group(0)
                number = match.group(1)
                
                if "ГОСТ Р" in full_match.upper() or "ГОСТ Р" in text:
                    standard_type = "ГОСТ Р"
                elif "ГОСТ" in full_match.upper() or "ГОСТ" in text:
                    standard_type = "ГОСТ"
                elif "ОСТ" in full_match.upper() or "ОСТ" in text:
                    standard_type = "ОСТ"
                elif "ТУ" in full_match.upper() or "ТУ" in text:
                    standard_type = "ТУ"
                else:
                    standard_type = "ГОСТ"
                
                return {
                    "standard_type": standard_type,
                    "number": number,
                    "full_designation": full_match.strip(),
                }
        
        # Пробуем советские форматы
        for pattern in self.SOVIET_PATTERNS:
            match = pattern.search(text)
            if match:
                number = match.group(2) if len(match.groups()) > 1 else match.group(1)
                year = match.group(2) if len(match.groups()) == 2 and len(match.group(2)) == 2 else None
                
                return {
                    "standard_type": "ГОСТ",
                    "number": number,
                    "year": year,
                    "full_designation": match.group(0).strip(),
                    "format": "soviet",
                }
        
        return None

    def _translate_russian_terms(self, text: str) -> str:
        """Перевести российские технические термины в английские."""
        translated = text
        for russian, english in self.RUSSIAN_TERMS.items():
            translated = translated.replace(russian, english)
            # Также с заглавной буквы
            translated = translated.replace(russian.capitalize(), english)
        return translated

    def _parse_csv(self, file_path: str) -> Dict[str, Any]:
        """Парсинг CSV с переводом российских терминов."""
        result = super()._parse_csv(file_path)
        if "text" in result:
            result["text"] = self._translate_russian_terms(result["text"])
        return result

    def _parse_html(self, file_path: str) -> Dict[str, Any]:
        """Парсинг HTML с переводом российских терминов."""
        result = super()._parse_html(file_path)
        if "text" in result:
            result["text"] = self._translate_russian_terms(result["text"])
        return result

    def extract_equivalence_info(self, text: str) -> List[Dict[str, Any]]:
        """Извлечь информацию об аналогах с учётом российских стандартов."""
        equivalences = super().extract_equivalence_info(text)
        
        # Российские стандарты часто указывают соответствие ISO/DIN
        russian_patterns = [
            (r"ГОСТ\s+(\d+(?:[-.]\d+)?)\s*соответствует\s*ISO\s*(\d+(?:[-.]\d+)?)", "equivalent"),
            (r"ГОСТ\s+(\d+(?:[-.]\d+)?)\s*аналог\s*DIN\s*(\d+(?:[-.]\d+)?)", "equivalent"),
            (r"ГОСТ\s+(\d+(?:[-.]\d+)?)\s*модифицирован\s*ISO\s*(\d+(?:[-.]\d+)?)", "modified"),
            (r"ГОСТ\s+Р\s+(\d+(?:[-.]\d+)?)\s*идентичен\s*ISO\s*(\d+(?:[-.]\d+)?)", "identical"),
        ]
        
        for pattern, relation_type in russian_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                source = "ISO" if "ISO" in match.group(0) else "DIN"
                source_number = match.group(2)
                
                equivalences.append({
                    "source": source,
                    "number": source_number,
                    "gost_number": match.group(1),
                    "relation": relation_type,
                    "confidence": 0.9 if relation_type == "identical" else 0.85,
                })
        
        return equivalences
