"""
Расчёт оптимальных режимов обработки с учётом установки станка и жёсткости.

K_total = K_machine_base × K_mounting × K_rigidity

При K_total < 0.8: снижаем ap, ae и корректируем Vc для минимизации вибрации.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List, Union

logger = logging.getLogger(__name__)


@dataclass
class ToolParams:
    """Параметры инструмента для расчёта."""
    vc_m_min: float = 0.0      # базовая скорость резания, м/мин
    feed: float = 0.0         # подача (мм/об для точения, мм/зуб для фрез)
    ap_mm: float = 0.0       # глубина резания, мм
    ae_mm: Optional[float] = None  # радиальное зацепление (фрезерование), мм
    tool_overhang_mm: Optional[float] = None
    tool_diameter_mm: Optional[float] = None
    operation: str = "turning"  # turning | milling


@dataclass
class MaterialParams:
    """Минимальные данные о материале заготовки."""
    name: str = ""
    vibration_tendency: str = "medium"  # low | medium | high | very_high


@dataclass
class OptimalModesResult:
    """Результат расчёта оптимальных режимов."""
    vc_m_min: float = 0.0
    feed: float = 0.0
    ap_mm: float = 0.0
    ae_mm: Optional[float] = None
    rpm: Optional[float] = None
    k_total: float = 1.0
    corrections_applied: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _get_k_total_from_instance(machine_instance: Any) -> float:
    """
    Получить K_total из ORM-объекта MachineInstance или из словаря.
    K_total = K_machine_base × K_mounting × K_rigidity
    """
    if hasattr(machine_instance, "get_k_total"):
        return machine_instance.get_k_total()
    if isinstance(machine_instance, dict):
        model = machine_instance.get("model") or {}
        mounting = machine_instance.get("mounting") or {}
        rigidity = machine_instance.get("rigidity_profile") or {}
        k_base = float(model.get("spindle_rigidity_base", 1.0))
        k_mount = float(mounting.get("mounting_stiffness_coeff", 1.0))
        k_rig = float(rigidity.get("rigidity_coeff", 1.0))
        return round(k_base * k_mount * k_rig, 4)
    return 1.0


def _material_vibration_factor(tendency: str) -> float:
    """Доп. коэффициент по склонности материала к вибрации."""
    return {"low": 1.0, "medium": 0.95, "high": 0.85, "very_high": 0.75}.get(
        tendency.lower(), 0.95
    )


def calculate_optimal_modes(
    machine_instance: Any,
    tool: Union[ToolParams, Dict[str, Any]],
    material: Union[MaterialParams, Dict[str, Any]],
    diameter_mm: Optional[float] = None,
) -> OptimalModesResult:
    """
    Рассчитать оптимальные режимы с учётом жёсткости установки станка.

    Если K_total < 0.8:
      - уменьшаем ap
      - уменьшаем ae (для фрезерования)
      - корректируем Vc (снижаем для стабильности)

    Args:
        machine_instance: ORM MachineInstance или dict с model, mounting, rigidity_profile
        tool: ToolParams или dict (vc_m_min, feed, ap_mm, ae_mm, operation, ...)
        material: MaterialParams или dict (name, vibration_tendency)
        diameter_mm: диаметр обработки (опционально, для расчёта rpm)

    Returns:
        OptimalModesResult с скорректированными режимами и списком применённых коррекций.
    """
    if isinstance(tool, dict):
        t = ToolParams(
            vc_m_min=float(tool.get("vc_m_min", 0) or tool.get("vc", 0)),
            feed=float(tool.get("feed", 0) or tool.get("feed_mm_rev", 0)),
            ap_mm=float(tool.get("ap_mm", 0) or tool.get("ap", 0)),
            ae_mm=tool.get("ae_mm") and float(tool["ae_mm"]),
            tool_overhang_mm=tool.get("tool_overhang_mm"),
            tool_diameter_mm=tool.get("tool_diameter_mm"),
            operation=str(tool.get("operation", "turning")),
        )
    else:
        t = tool

    if isinstance(material, dict):
        mat = MaterialParams(
            name=material.get("name", ""),
            vibration_tendency=str(material.get("vibration_tendency", "medium")),
        )
    else:
        mat = material

    k_total = _get_k_total_from_instance(machine_instance)
    mat_factor = _material_vibration_factor(mat.vibration_tendency)

    vc = t.vc_m_min
    feed = t.feed
    ap = t.ap_mm
    ae = t.ae_mm
    corrections: List[str] = []
    warnings: List[str] = []

    if k_total < 0.8:
        # Снижаем режимы для уменьшения риска вибрации
        k_correction = max(0.5, k_total)
        vc = vc * k_correction * mat_factor
        feed = feed * k_correction
        ap = ap * k_correction
        if ae is not None:
            ae = ae * k_correction
        corrections.append(
            f"K_total={k_total:.2f} < 0.8: снижены Vc, подача, ap" + (" и ae" if ae is not None else "")
        )
        warnings.append(
            "Жёсткость установки ниже нормы. Рекомендуется проверить анкеровку и виброизоляцию."
        )
    else:
        # Лёгкая коррекция по материалу
        vc = vc * mat_factor
        if k_total < 1.0:
            corrections.append(f"Учтён коэффициент жёсткости установки K_total={k_total:.2f}")

    # Ограничение по максимальным оборотам станка (если передан экземпляр с моделью)
    max_rpm = None
    if hasattr(machine_instance, "model") and machine_instance.model is not None:
        max_rpm = getattr(machine_instance.model, "max_rpm", None)
    elif isinstance(machine_instance, dict):
        max_rpm = (machine_instance.get("model") or {}).get("max_rpm")

    rpm = None
    if diameter_mm and diameter_mm > 0 and vc > 0:
        from math import pi
        rpm = vc * 1000 / (pi * diameter_mm)
        if max_rpm is not None and rpm > max_rpm:
            rpm = float(max_rpm)
            vc = rpm * pi * diameter_mm / 1000
            corrections.append(f"Обороты ограничены макс. {max_rpm} об/мин станка")

    return OptimalModesResult(
        vc_m_min=round(vc, 2),
        feed=round(feed, 4),
        ap_mm=round(ap, 3),
        ae_mm=round(ae, 3) if ae is not None else None,
        rpm=round(rpm, 0) if rpm is not None else None,
        k_total=k_total,
        corrections_applied=corrections,
        warnings=warnings,
    )
