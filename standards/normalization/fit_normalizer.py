"""
Нормализация обозначений посадок (H7/g6, H7/js6 и т.д.).
ЭТАП 3: после IT — реализовать посадки.
"""

from typing import Optional, Dict, Any

from standards.models import StandardEntity


def normalize_fit(hole: str, shaft: str) -> Optional[Dict[str, Any]]:
    """
    Нормализовать посадку по обозначениям отверстия и вала.
    hole: H7, shaft: g6 → { type: "fit", fit_type: "clearance", hole: "H7", shaft: "g6" }
    """
    if not hole or not shaft:
        return None
    hole = hole.strip().upper()
    shaft = shaft.strip()
    if len(shaft) >= 2:
        shaft = shaft[0].lower() + shaft[1:] if shaft[0].isalpha() else shaft
    # Упрощённо: по первой букве вала определяем тип посадки
    fit_type = "transition"
    if shaft.startswith("h") or shaft.startswith("g") or shaft.startswith("f") or shaft.startswith("e") or shaft.startswith("d") or shaft.startswith("c") or shaft.startswith("a"):
        fit_type = "clearance"
    elif shaft.startswith("p") or shaft.startswith("r") or shaft.startswith("s") or shaft.startswith("t") or shaft.startswith("u"):
        fit_type = "interference"
    return {
        "type": "fit",
        "fit_type": fit_type,
        "hole": hole,
        "shaft": shaft,
        "system": "metric",
    }


def fit_to_entity(hole: str, shaft: str, source: str = "GOST") -> Optional[StandardEntity]:
    """По паре отверстие/вал построить StandardEntity."""
    norm = normalize_fit(hole, shaft)
    if norm is None:
        return None
    raw = f"{hole}/{shaft}"
    entity_id = f"fit_{source}_{raw.replace(' ', '_')}"
    return StandardEntity(
        id=entity_id,
        source=source,
        category="fit",
        normalized_data=norm,
        raw_designation=raw,
    )
