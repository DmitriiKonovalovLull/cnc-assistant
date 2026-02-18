"""
Нормализация обозначений резьбы (метрическая резьба ГОСТ/ISO).
Преобразование строки обозначения в единую внутреннюю модель.
"""

import re
from typing import Optional, Dict, Any

from standards.models import StandardEntity


# Регулярки для метрической резьбы: M42, M42x1.5, M42x1.5-6g, M42-6g
_METRIC_THREAD = re.compile(
    r"^\s*M\s*(\d+(?:[.,]\d+)?)\s*(?:[xX×]\s*(\d+(?:[.,]\d+)?))?\s*(?:[-–—]\s*(\d+[gGhH])?\s*(\d+[gGhH])?)?\s*$"
)
_NUM = re.compile(r"(\d+(?:[.,]\d+)?)")


def _to_float(s: Optional[str]) -> Optional[float]:
    if s is None:
        return None
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def normalize_metric_thread(designation: str) -> Optional[Dict[str, Any]]:
    """
    Нормализовать обозначение метрической резьбы в словарь.
    Пример: M42x1.5-6g → {
      "type": "metric_thread",
      "diameter": 42,
      "pitch": 1.5,
      "tolerance_class": "6g",
      "profile_angle": 60,
      "system": "metric"
    }
    """
    if not designation or not designation.strip():
        return None
    raw = designation.strip()
    # Убираем лишние пробелы вокруг x и -
    raw = re.sub(r"\s*[xX×]\s*", "x", raw)
    raw = re.sub(r"\s*[-–—]\s*", "-", raw)
    m = _METRIC_THREAD.match(raw)
    if not m:
        # Попытка упрощённо: M и числа
        nums = _NUM.findall(raw)
        if raw.upper().startswith("M") and len(nums) >= 1:
            diameter = _to_float(nums[0])
            pitch = _to_float(nums[1]) if len(nums) > 1 else None
            # Стандартный шаг для метрической резьбы по ГОСТ (крупный если не указан)
            if diameter is not None and pitch is None:
                pitch = _default_metric_pitch(diameter)
            tolerance = None
            for part in raw.split("-"):
                part = part.strip()
                if re.match(r"^\d+[gGhH]$", part):
                    tolerance = part
                    break
            return {
                "type": "metric_thread",
                "diameter": diameter,
                "pitch": pitch,
                "tolerance_class": tolerance,
                "profile_angle": 60,
                "system": "metric",
            }
        return None
    diameter = _to_float(m.group(1))
    pitch = _to_float(m.group(2))
    tol1, tol2 = m.group(3), m.group(4)
    tolerance_class = tol1 or tol2 or None
    if diameter is None:
        return None
    if pitch is None:
        pitch = _default_metric_pitch(diameter)
    return {
        "type": "metric_thread",
        "diameter": diameter,
        "pitch": pitch,
        "tolerance_class": tolerance_class,
        "profile_angle": 60,
        "system": "metric",
    }


def _default_metric_pitch(diameter: float) -> float:
    """Крупный шаг по ГОСТ 8724 для распространённых диаметров (мм)."""
    defaults = {
        1: 0.25, 1.2: 0.25, 1.4: 0.3, 1.6: 0.35, 2: 0.4, 2.5: 0.45, 3: 0.5,
        4: 0.7, 5: 0.8, 6: 1.0, 8: 1.25, 10: 1.5, 12: 1.75, 16: 2.0, 20: 2.5,
        24: 3.0, 30: 3.5, 36: 4.0, 42: 4.5, 48: 5.0, 56: 5.5, 64: 6.0,
    }
    d = int(diameter) if diameter == int(diameter) else diameter
    return defaults.get(d, 2.0)  # fallback


def thread_to_entity(designation: str, source: str = "GOST") -> Optional[StandardEntity]:
    """По обозначению резьбы построить StandardEntity."""
    norm = normalize_metric_thread(designation)
    if norm is None:
        return None
    entity_id = f"thread_{source}_{designation.strip().replace(' ', '_')}"
    return StandardEntity(
        id=entity_id,
        source=source,
        category="thread",
        normalized_data=norm,
        raw_designation=designation.strip(),
    )
