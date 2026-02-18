"""
Парсер китайских стандартов: GB, GB/T, GB/Z.
Работа с иероглифами, конвертация единиц измерения (Китай использует мм).
"""

import re
import logging
from typing import Dict, Any, Optional, List

from standards.ingestion.multi_format_parser import ChineseStandardsParser as BaseChineseParser

logger = logging.getLogger(__name__)


class ChinaStandardsParser(BaseChineseParser):
    """
    Специализированный парсер для китайских стандартов GB, GB/T, GB/Z.
    Расширяет ChineseStandardsParser с дополнительной логикой для GB стандартов.
    """

    # Паттерны обозначений GB стандартов
    GB_PATTERNS = [
        re.compile(r"GB\s*[/-]?T\s*(\d+(?:[-.]\d+)?)\s*-?\s*(\d{4})?", re.IGNORECASE),  # GB/T 192-2003
        re.compile(r"GB\s*[/-]?Z\s*(\d+(?:[-.]\d+)?)\s*-?\s*(\d{4})?", re.IGNORECASE),  # GB/Z (руководящие)
        re.compile(r"GB\s+(\d+(?:[-.]\d+)?)\s*-?\s*(\d{4})?", re.IGNORECASE),  # GB 192-2003
    ]

    # Дополнительные китайские технические термины для GB стандартов
    GB_TERMS = {
        "国家标准": "National Standard",
        "推荐标准": "Recommended Standard",
        "指导性技术文件": "Guidance Technical Document",
        "螺纹": "thread",
        "公差": "tolerance",
        "配合": "fit",
        "表面粗糙度": "surface roughness",
        "毫米": "mm",
        "毫米": "millimeter",
    }

    def __init__(self):
        super().__init__()
        # Расширяем словарь терминов
        self.CHINESE_TERMS.update(self.GB_TERMS)

    def parse_gb_designation(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг обозначения GB стандарта.
        Примеры: GB/T 192-2003, GB 1800-2009, GB/Z 12345
        
        Args:
            text: Текст с обозначением GB стандарта
            
        Returns:
            Словарь с распарсенными данными или None
        """
        for pattern in self.GB_PATTERNS:
            match = pattern.search(text)
            if match:
                standard_type = "GB/T" if "/T" in match.group(0).upper() or "/T" in text else \
                               "GB/Z" if "/Z" in match.group(0).upper() or "/Z" in text else "GB"
                number = match.group(1)
                year = match.group(2) if len(match.groups()) > 1 and match.group(2) else None
                
                return {
                    "standard_type": standard_type,
                    "number": number,
                    "year": year,
                    "full_designation": match.group(0).strip(),
                }
        return None

    def _normalize_units(self, text: str) -> str:
        """
        Нормализация единиц измерения.
        Китай использует мм, но могут быть указаны в разных форматах.
        """
        # Заменяем китайские обозначения единиц
        replacements = {
            "毫米": "mm",
            "毫米": "mm",
            "厘米": "cm",
            "米": "m",
            "英寸": "inch",
        }
        
        normalized = text
        for chinese, english in replacements.items():
            normalized = normalized.replace(chinese, english)
        
        return normalized

    def extract_equivalence_info(self, text: str) -> List[Dict[str, Any]]:
        """Извлечь информацию об аналогах с учётом GB стандартов."""
        equivalences = super().extract_equivalence_info(text)
        
        # GB стандарты часто указывают базовый ISO
        gb_patterns = [
            (r"GB[/-]T\s*(\d+)\s*修改\s*ISO\s*(\d+(?:[-.]\d+)?)", "modified"),
            (r"GB[/-]T\s*(\d+)\s*等同\s*ISO\s*(\d+(?:[-.]\d+)?)", "equivalent"),
            (r"GB[/-]T\s*(\d+)\s*采用\s*ISO\s*(\d+(?:[-.]\d+)?)", "adopted"),
        ]
        
        for pattern, relation_type in gb_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                equivalences.append({
                    "source": "ISO",
                    "number": match.group(2),
                    "gb_number": match.group(1),
                    "relation": relation_type,
                    "confidence": 0.9,
                })
        
        return equivalences

    def _parse_csv(self, file_path: str) -> Dict[str, Any]:
        """Парсинг CSV с нормализацией единиц измерения."""
        result = super()._parse_csv(file_path)
        if "text" in result:
            result["text"] = self._normalize_units(result["text"])
        if "translated_text" in result:
            result["translated_text"] = self._normalize_units(result["translated_text"])
        return result
