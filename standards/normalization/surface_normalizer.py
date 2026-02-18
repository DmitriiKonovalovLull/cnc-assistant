"""
Нормализация обозначений шероховатости (Ra 1.6, Ra0.8, Rz 6.3 и т.д.).
ЭТАП 4: после посадок — реализовать шероховатость.
"""

import re
from typing import Optional, Dict, Any

from standards.models import StandardEntity


_RA = re.compile(r"^\s*Ra\s*(\d+(?:[.,]\d+)?)\s*$", re.IGNORECASE)
_RZ = re.compile(r"^\s*Rz\s*(\d+(?:[.,]\d+)?)\s*$", re.IGNORECASE)
_NUM = re.compile(r"(\d+(?:[.,]\d+)?)")


def _to_float(s: str) -> Optional[float]:
    if not s:
        return None
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def normalize_surface(designation: str) -> Optional[Dict[str, Any]]:
    """
    Нормализовать обозначение шероховатости.
    Ra 1.6 → { type: "surface_roughness", ra_um: 1.6, rz_um: None, system: "metric" }
    """
    if not designation or not designation.strip():
        return None
    raw = designation.strip()
    m_ra = _RA.match(raw)
    if m_ra:
        ra = _to_float(m_ra.group(1))
        if ra is not None and ra > 0:
            return {"type": "surface_roughness", "ra_um": ra, "rz_um": None, "system": "metric"}
        return None
    m_rz = _RZ.match(raw)
    if m_rz:
        rz = _to_float(m_rz.group(1))
        if rz is not None and rz > 0:
            return {"type": "surface_roughness", "ra_um": None, "rz_um": rz, "system": "metric"}
        return None
    # Только число — трактуем как Ra
    nums = _NUM.findall(raw)
    if len(nums) == 1:
        ra = _to_float(nums[0])
        if ra is not None and ra > 0:
            return {"type": "surface_roughness", "ra_um": ra, "rz_um": None, "system": "metric"}
    return None


def surface_to_entity(designation: str, source: str = "GOST") -> Optional[StandardEntity]:
    """По обозначению шероховатости построить StandardEntity."""
    norm = normalize_surface(designation)
    if norm is None:
        return None
    raw = designation.strip()
    entity_id = f"surface_{source}_{raw.replace(' ', '_')}"
    return StandardEntity(
        id=entity_id,
        source=source,
        category="surface",
        normalized_data=norm,
        raw_designation=raw,
    )
