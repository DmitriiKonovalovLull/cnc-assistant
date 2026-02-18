"""
Нормализация обозначений допусков (IT, поля H7, g6 и т.д.).
ЭТАП 2: после Thread — реализовать IT-допуски.
"""

import re
from typing import Optional, Dict, Any

from standards.models import StandardEntity


# Поле допуска: буква + число (H7, g6, js6, Js7, ...)
_TOLERANCE_FIELD = re.compile(r"^\s*([A-Za-z]{1,3})\s*(\d+)\s*$")
_IT_GRADE = re.compile(r"^\s*IT\s*(\d+)\s*$", re.IGNORECASE)
# Номинальный размер + поле: 50 H7, 50h7, Ø50 H7
_NOMINAL_AND_FIELD = re.compile(r"^\s*(?:Ø|D)?\s*(\d+(?:[.,]\d+)?)\s*([A-Za-z]{1,3})\s*(\d+)\s*$", re.IGNORECASE)


def _to_float(s: str) -> Optional[float]:
    if not s:
        return None
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def normalize_tolerance_field(designation: str) -> Optional[Dict[str, Any]]:
    """
    Нормализовать поле допуска (H7, g6) или IT7.
    Возвращает словарь для внутренней модели или None.
    """
    if not designation or not designation.strip():
        return None
    raw = designation.strip()
    # IT6, IT7, ...
    m_it = _IT_GRADE.match(raw)
    if m_it:
        grade = int(m_it.group(1))
        if 1 <= grade <= 18:
            return {
                "type": "it_tolerance",
                "tolerance_grade": grade,
                "tolerance_field": None,
                "nominal_mm": None,
                "system": "metric",
            }
        return None
    # H7, g6
    m = _TOLERANCE_FIELD.match(raw)
    if m:
        letter, num = m.group(1), int(m.group(2))
        if 1 <= num <= 18:
            return {
                "type": "tolerance_field",
                "tolerance_grade": num,
                "tolerance_field": f"{letter.upper()}{num}",
                "nominal_mm": None,
                "system": "metric",
            }
    return None


def normalize_nominal_and_tolerance(nominal_mm: float, field: str) -> Optional[Dict[str, Any]]:
    """Номинальный размер + поле допуска (50, H7) → нормализованный словарь."""
    norm_field = normalize_tolerance_field(field)
    if norm_field is None:
        return None
    norm_field["nominal_mm"] = nominal_mm
    return norm_field


def tolerance_to_entity(designation: str, source: str = "GOST") -> Optional[StandardEntity]:
    """По обозначению допуска (Ø50 H7 или H7) построить StandardEntity."""
    raw = designation.strip()
    # Попытка "число + поле"
    m = _NOMINAL_AND_FIELD.match(raw)
    if m:
        nominal = _to_float(m.group(1))
        letter, num = m.group(2), m.group(3)
        field = f"{letter}{num}"
        norm = normalize_nominal_and_tolerance(nominal, field) if nominal is not None else normalize_tolerance_field(field)
    else:
        norm = normalize_tolerance_field(raw)
    if norm is None:
        return None
    entity_id = f"tolerance_{source}_{raw.replace(' ', '_')}"
    return StandardEntity(
        id=entity_id,
        source=source,
        category="tolerance",
        normalized_data=norm,
        raw_designation=raw,
    )
