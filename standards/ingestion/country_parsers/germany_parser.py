"""
Парсер немецких стандартов: DIN, DIN EN, DIN ISO.
Немецкие технические термины.
"""

import re
import logging
from typing import Dict, Any, Optional, List

from standards.ingestion.multi_format_parser import EuropeanStandardsParser as BaseEuropeanParser

logger = logging.getLogger(__name__)


class GermanyStandardsParser(BaseEuropeanParser):
    """
    Специализированный парсер для немецких стандартов DIN, DIN EN, DIN ISO.
    Расширяет EuropeanStandardsParser с дополнительной логикой для DIN стандартов.
    """

    # Паттерны обозначений DIN стандартов
    DIN_PATTERNS = [
        re.compile(r"DIN\s+EN\s+ISO\s+(\d+(?:[-.]\d+)?)", re.IGNORECASE),  # DIN EN ISO 965-1
        re.compile(r"DIN\s+EN\s+(\d+(?:[-.]\d+)?)", re.IGNORECASE),  # DIN EN 12345
        re.compile(r"DIN\s+(\d+(?:[-.]\d+)?)", re.IGNORECASE),  # DIN 13
    ]

    # Немецкие технические термины
    GERMAN_TERMS = {
        "Gewinde": "thread",
        "Toleranz": "tolerance",
        "Passung": "fit",
        "Oberflächenrauheit": "surface roughness",
        "Millimeter": "mm",
        "Zoll": "inch",
        "Norm": "standard",
        "Deutsche Industrienorm": "German Industrial Standard",
    }

    def __init__(self):
        super().__init__()

    def parse_din_designation(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг обозначения DIN стандарта.
        Примеры: DIN 13, DIN EN ISO 965-1, DIN EN 12345
        
        Args:
            text: Текст с обозначением DIN стандарта
            
        Returns:
            Словарь с распарсенными данными или None
        """
        for pattern in self.DIN_PATTERNS:
            match = pattern.search(text)
            if match:
                full_match = match.group(0)
                number = match.group(1)
                
                if "DIN EN ISO" in full_match.upper():
                    standard_type = "DIN EN ISO"
                    base_standard = "ISO"
                elif "DIN EN" in full_match.upper():
                    standard_type = "DIN EN"
                    base_standard = "EN"
                else:
                    standard_type = "DIN"
                    base_standard = None
                
                return {
                    "standard_type": standard_type,
                    "number": number,
                    "base_standard": base_standard,
                    "full_designation": full_match.strip(),
                }
        return None

    def _translate_german_terms(self, text: str) -> str:
        """Перевести немецкие технические термины в английские."""
        translated = text
        for german, english in self.GERMAN_TERMS.items():
            translated = translated.replace(german, english)
            # Также с заглавной буквы
            translated = translated.replace(german.capitalize(), english)
        return translated

    def _parse_csv(self, file_path: str) -> Dict[str, Any]:
        """Парсинг CSV с переводом немецких терминов."""
        result = super()._parse_csv(file_path)
        if "text" in result:
            result["text"] = self._translate_german_terms(result["text"])
        return result

    def _parse_html(self, file_path: str) -> Dict[str, Any]:
        """Парсинг HTML с переводом немецких терминов."""
        result = super()._parse_html(file_path)
        if "text" in result:
            result["text"] = self._translate_german_terms(result["text"])
        return result

    def extract_equivalence_info(self, text: str) -> List[Dict[str, Any]]:
        """Извлечь информацию об аналогах с учётом DIN стандартов."""
        equivalences = super().extract_equivalence_info(text)
        
        # DIN EN ISO стандарты напрямую указывают ISO
        din_patterns = [
            (r"DIN\s+EN\s+ISO\s+(\d+(?:[-.]\d+)?)", "harmonized"),
            (r"DIN\s+(\d+)\s*entspricht\s*ISO\s*(\d+(?:[-.]\d+)?)", "equivalent"),
            (r"DIN\s+(\d+)\s*equivalent\s+to\s+ISO\s*(\d+(?:[-.]\d+)?)", "equivalent"),
        ]
        
        for pattern, relation_type in din_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match.groups()) == 1:
                    # DIN EN ISO
                    iso_number = match.group(1)
                else:
                    # DIN X entspricht ISO Y
                    iso_number = match.group(2)
                
                equivalences.append({
                    "source": "ISO",
                    "number": iso_number,
                    "relation": relation_type,
                    "confidence": 0.95 if relation_type == "harmonized" else 0.85,
                })
        
        return equivalences
