"""
Выбор оптимального станка под заданные требования операции.

Критерии:
- запас мощности
- запас по крутящему моменту
- коэффициент жёсткости (K_total)
- стабильность при L/D > 4
- минимизация риска вибрации
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


@dataclass
class OperationRequirements:
    """Требования операции к станку."""
    power_kw_min: float = 0.0
    torque_nm_min: float = 0.0
    max_rpm_min: int = 0
    machine_kind: Optional[str] = None   # turning | milling | ...
    ld_ratio: Optional[float] = None     # если > 4 — важна жёсткость; для Score: Stability_index
    vibration_sensitive: bool = False    # материал/операция чувствительны к вибрации
    preferred_k_total_min: float = 0.85  # желаемый мин. K_total
    # Инженерная формула Score (если заданы — считаем Score по ТЗ):
    # Score = 0.3*(P_reserve/P_required) + 0.3*K_system + 0.2*(Tmax/M_required) + 0.2*Stability_index
    power_required_kw: float = 0.0       # Pc — требуемая мощность резания
    torque_required_nm: float = 0.0       # M_required — требуемый момент
    use_engineering_score: bool = False   # True — использовать формулу выше


def _get_instance_data(instance: Any) -> Dict[str, Any]:
    """Собрать из ORM-экземпляра словарь для скоринга."""
    model = instance.model
    mounting = instance.mounting
    rigidity = instance.rigidity_profile

    k_total = instance.get_k_total() if hasattr(instance, "get_k_total") else 1.0
    power_kw = float(model.power_kw) if model else 0.0
    max_rpm = int(model.max_rpm) if model and model.max_rpm else 0
    torque_nm = float(model.torque_nm) if model and model.torque_nm else None
    vibration_mm_s = float(rigidity.vibration_mm_per_s) if rigidity and rigidity.vibration_mm_per_s else None
    vibration_risk = (rigidity.vibration_risk or "moderate") if rigidity else "moderate"

    return {
        "instance": instance,
        "instance_id": instance.id,
        "instance_name": instance.instance_name,
        "model_name": model.name if model else "",
        "machine_kind": model.machine_kind if model else "",
        "power_kw": power_kw,
        "max_rpm": max_rpm,
        "torque_nm": torque_nm,
        "k_total": k_total,
        "vibration_mm_per_s": vibration_mm_s,
        "vibration_risk": vibration_risk,
    }


def _score_power_margin(data: Dict[str, Any], req: OperationRequirements) -> float:
    """Запас по мощности: 0..1, лучше если мощность с запасом."""
    if req.power_kw_min <= 0:
        return 1.0
    p = data["power_kw"]
    if p <= 0:
        return 0.0
    ratio = p / req.power_kw_min
    if ratio >= 1.5:
        return 1.0
    if ratio >= 1.0:
        return 0.7 + 0.3 * (ratio - 1.0) / 0.5
    return max(0.0, ratio)  # недостаток мощности — штраф


def _score_torque_margin(data: Dict[str, Any], req: OperationRequirements) -> float:
    """Запас по крутящему моменту."""
    if req.torque_nm_min <= 0 or data.get("torque_nm") is None:
        return 1.0
    t = data["torque_nm"]
    if t <= 0:
        return 0.0
    ratio = t / req.torque_nm_min
    if ratio >= 1.3:
        return 1.0
    if ratio >= 1.0:
        return 0.6 + 0.4 * (ratio - 1.0) / 0.3
    return max(0.0, ratio)


def _score_rigidity(data: Dict[str, Any], req: OperationRequirements) -> float:
    """K_total: 0.8+ хорошо, 1.0 отлично."""
    k = data["k_total"]
    if k >= 1.0:
        return 1.0
    if k >= req.preferred_k_total_min:
        return 0.8 + 0.2 * (k - req.preferred_k_total_min) / (1.0 - req.preferred_k_total_min)
    if k >= 0.5:
        return 0.3 + 0.5 * (k - 0.5) / 0.3
    return max(0.0, k / 0.5)


def _score_ld_stability(data: Dict[str, Any], req: OperationRequirements) -> float:
    """При L/D > 4 важна жёсткость и низкий vibration_risk."""
    if req.ld_ratio is None or req.ld_ratio <= 4:
        return 1.0
    k = data["k_total"]
    risk = data.get("vibration_risk", "moderate")
    risk_score = {"low": 1.0, "moderate": 0.7, "high": 0.4, "critical": 0.1}.get(risk, 0.5)
    return 0.6 * (k if k <= 1.0 else 1.0) + 0.4 * risk_score


def _score_vibration_risk(data: Dict[str, Any], req: OperationRequirements) -> float:
    """Минимизация риска вибрации: низкий vibration_risk и по возможности низкий мм/с."""
    if not req.vibration_sensitive:
        return 1.0
    risk = data.get("vibration_risk", "moderate")
    risk_score = {"low": 1.0, "moderate": 0.75, "high": 0.4, "critical": 0.1}.get(risk, 0.5)
    v = data.get("vibration_mm_per_s")
    if v is not None:
        if v <= 2.0:
            vib_score = 1.0
        elif v <= 5.0:
            vib_score = 0.8
        elif v <= 10.0:
            vib_score = 0.5
        else:
            vib_score = 0.2
        return 0.6 * risk_score + 0.4 * vib_score
    return risk_score


def _engineering_score(
    data: Dict[str, Any],
    req: OperationRequirements,
) -> Tuple[float, Dict[str, float]]:
    """
    Score по ТЗ: 0.3*(P_reserve/P_required) + 0.3*K_system + 0.2*(Tmax/M_required) + 0.2*Stability_index.
    P_reserve = P_machine - Pc; K_system берём как k_total; Stability_index = min(1, k_total * 3/max(3, L/D)).
    """
    p_machine = data.get("power_kw") or 0.0
    t_max = data.get("torque_nm") or 0.0
    k_total = data.get("k_total") or 1.0
    p_required = req.power_required_kw or 1e-6
    m_required = req.torque_required_nm or 1e-6
    ld = req.ld_ratio or 3.0

    p_reserve = max(0.0, p_machine - p_required)
    term_p = 0.3 * (p_reserve / p_required) if p_required > 0 else 0.0
    term_k = 0.3 * min(1.2, k_total)
    term_t = 0.2 * (t_max / m_required) if m_required > 0 else 0.0
    stability_index = min(1.0, k_total * (3.0 / max(3.0, ld)))
    term_s = 0.2 * stability_index

    total = term_p + term_k + term_t + term_s
    breakdown = {
        "power_reserve": round(term_p, 4),
        "k_system": round(term_k, 4),
        "torque_margin": round(term_t, 4),
        "stability": round(term_s, 4),
        "total": round(total, 4),
    }
    return total, breakdown


def select_best_machine(
    instances: Sequence[Any],
    operation_requirements: OperationRequirements,
    *,
    kind_filter: bool = True,
    top_n: int = 5,
) -> List[Tuple[Any, float, Dict[str, float]]]:
    """
    Выбрать лучшие станки по критериям операции.

    Args:
        instances: Список ORM MachineInstance (или dict с model, mounting, rigidity_profile)
        operation_requirements: Требования к мощности, моменту, типу, L/D, вибрации
        kind_filter: Отфильтровать по machine_kind, если задан
        top_n: Сколько лучших вернуть

    Returns:
        Список кортежей (instance, total_score, score_breakdown).
        score_breakdown: power, torque, rigidity, ld_stability, vibration, total.
    """
    req = operation_requirements
    scored: List[Tuple[Dict[str, Any], float, Dict[str, float]]] = []

    for inst in instances:
        if hasattr(inst, "model"):
            data = _get_instance_data(inst)
        elif isinstance(inst, dict):
            data = inst.copy()
            data["instance"] = inst
            data["k_total"] = _k_total_from_dict(inst)
        else:
            continue

        if kind_filter and req.machine_kind and data.get("machine_kind") != req.machine_kind:
            continue

        if req.max_rpm_min and (data.get("max_rpm") or 0) < req.max_rpm_min:
            continue

        if req.use_engineering_score and (req.power_required_kw > 0 or req.torque_required_nm > 0):
            total, breakdown = _engineering_score(data, req)
        else:
            s_power = _score_power_margin(data, req)
            s_torque = _score_torque_margin(data, req)
            s_rigidity = _score_rigidity(data, req)
            s_ld = _score_ld_stability(data, req)
            s_vib = _score_vibration_risk(data, req)
            total = (
                0.25 * s_power
                + 0.20 * s_torque
                + 0.25 * s_rigidity
                + 0.15 * s_ld
                + 0.15 * s_vib
            )
            breakdown = {
                "power": s_power,
                "torque": s_torque,
                "rigidity": s_rigidity,
                "ld_stability": s_ld,
                "vibration": s_vib,
                "total": round(total, 4),
            }
        scored.append((data, total, breakdown))

    scored.sort(key=lambda x: -x[1])
    result: List[Tuple[Any, float, Dict[str, float]]] = []
    for data, total, breakdown in scored[:top_n]:
        result.append((data["instance"], total, breakdown))
    return result


def _k_total_from_dict(d: Dict[str, Any]) -> float:
    model = d.get("model") or {}
    mounting = d.get("mounting") or {}
    rigidity = d.get("rigidity_profile") or {}
    k_base = float(model.get("spindle_rigidity_base", 1.0))
    k_mount = float(mounting.get("mounting_stiffness_coeff", 1.0))
    k_rig = float(rigidity.get("rigidity_coeff", 1.0))
    return round(k_base * k_mount * k_rig, 4)
