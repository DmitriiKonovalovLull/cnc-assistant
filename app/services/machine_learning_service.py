"""Авто-адаптация станка по истории: StabilityIndex, K_machine_real, SAFE_ZONES, predict_stability."""

import json
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Пороги StabilityIndex
STABILITY_INDEX_STABLE = 0.8   # > 0.8 → режим стабильный, можно повысить K
STABILITY_INDEX_UNSTABLE = 0.5  # < 0.5 → нестабильный, снижаем K
K_MACHINE_MIN = 0.6
K_MACHINE_MAX = 1.2
# Коррекция за одну итерацию обучения
K_DECREASE_UNSTABLE = 0.97
K_INCREASE_STABLE = 1.02   # переопределяется из БД (k_increase_stable, по ТЗ 1.01)
K_DECREASE_CHATTER = 0.95
AP_CRIT_DECREASE_FACTOR = 0.9
# Размер окна оборотов для SAFE_ZONE (об/мин)
RPM_BUCKET_SIZE = 200
# Минимум записей в диапазоне, чтобы считать зону безопасной
MIN_RECORDS_FOR_SAFE_ZONE = 3


@dataclass
class OperationRecord:
    """Одна запись для сохранения в историю."""
    machine_instance_id: int
    tool: str = ""
    material: str = ""
    diameter_mm: Optional[float] = None
    overhang_mm: Optional[float] = None
    teeth_count: Optional[int] = None
    rpm: float = 0.0
    vc_m_min: Optional[float] = None
    feed_mm_rev: float = 0.0
    ap_mm: float = 0.0
    ae_mm: Optional[float] = None
    vibration_rms: Optional[float] = None
    peak_frequency_hz: Optional[float] = None
    power_kw: Optional[float] = None
    result: str = "stable"  # stable, chatter, failure, tool_wear
    operator_level: Optional[str] = None


@dataclass
class StabilityPrediction:
    """Результат predict_stability."""
    predicted_stable: bool
    stability_index_estimate: float
    in_safe_zone: bool
    k_machine_used: float
    safe_zones: List[Dict[str, int]]
    recommendations: List[str] = field(default_factory=list)


def stability_index(v_rms: float, v_limit: float) -> float:
    """1 - (V_rms / V_limit), в диапазоне [0, 1]."""
    if v_limit <= 0:
        return 1.0
    if v_rms < 0:
        v_rms = 0.0
    si = 1.0 - (v_rms / v_limit)
    return max(0.0, min(1.0, si))


def _get_v_limit(session: Any, learned: Any) -> float:
    """V_limit из machine_learned_params или calculation_coefficients."""
    if learned and learned.vibration_limit_mm_s is not None and float(learned.vibration_limit_mm_s) > 0:
        return float(learned.vibration_limit_mm_s)
    try:
        from app.storage.machine_library import CalculationCoefficient
        row = session.query(CalculationCoefficient).filter_by(key="vibration_limit_mm_s").first()
        return float(row.value) if row else 5.0
    except Exception:
        return 5.0


def record_operation(session: Any, record: OperationRecord) -> int:
    """Записывает операцию в machine_operation_history. Возвращает id записи."""
    from app.storage.machine_library import MachineOperationHistory

    row = MachineOperationHistory(
        machine_instance_id=record.machine_instance_id,
        tool=record.tool or None,
        material=record.material or None,
        diameter_mm=Decimal(str(record.diameter_mm)) if record.diameter_mm is not None else None,
        overhang_mm=Decimal(str(record.overhang_mm)) if record.overhang_mm is not None else None,
        teeth_count=record.teeth_count,
        rpm=Decimal(str(record.rpm)),
        vc_m_min=Decimal(str(record.vc_m_min)) if record.vc_m_min is not None else None,
        feed_mm_rev=Decimal(str(record.feed_mm_rev)),
        ap_mm=Decimal(str(record.ap_mm)),
        ae_mm=Decimal(str(record.ae_mm)) if record.ae_mm is not None else None,
        vibration_rms=Decimal(str(record.vibration_rms)) if record.vibration_rms is not None else None,
        peak_frequency_hz=Decimal(str(record.peak_frequency_hz)) if record.peak_frequency_hz is not None else None,
        power_kw=Decimal(str(record.power_kw)) if record.power_kw is not None else None,
        result=record.result,
        operator_level=record.operator_level,
    )
    session.add(row)
    session.flush()
    return row.id


def _get_or_create_learned(session: Any, machine_instance_id: int) -> Any:
    from app.storage.machine_library import MachineLearnedParams, MachineInstance

    learned = session.query(MachineLearnedParams).filter_by(machine_instance_id=machine_instance_id).first()
    if learned:
        return learned
    instance = session.query(MachineInstance).get(machine_instance_id)
    if not instance:
        return None
    k_base = float(instance.model.spindle_rigidity_base)
    learned = MachineLearnedParams(
        machine_instance_id=machine_instance_id,
        k_machine_real=Decimal(str(min(K_MACHINE_MAX, max(K_MACHINE_MIN, k_base)))),
    )
    session.add(learned)
    session.flush()
    return learned


def _build_safe_zones(rows: List[Any], v_limit: float) -> List[Dict[str, int]]:
    """
    Группируем по диапазонам оборотов (RPM_BUCKET_SIZE). Если в диапазоне все stable и SI > 0.7 — SAFE_ZONE.
    """
    if not rows:
        return []
    buckets: Dict[int, List[Tuple[float, str]]] = {}
    for r in rows:
        rpm = float(r.rpm) if r.rpm else 0
        if rpm <= 0:
            continue
        v_rms = float(r.vibration_rms) if r.vibration_rms is not None else 0.0
        res = (r.result or "stable").lower()
        si = stability_index(v_rms, v_limit)
        bucket_key = int(rpm // RPM_BUCKET_SIZE) * RPM_BUCKET_SIZE
        if bucket_key not in buckets:
            buckets[bucket_key] = []
        buckets[bucket_key].append((si, res))

    zones = []
    for rpm_start in sorted(buckets.keys()):
        items = buckets[rpm_start]
        if len(items) < MIN_RECORDS_FOR_SAFE_ZONE:
            continue
        all_stable = all(res == "stable" for _, res in items)
        avg_si = sum(si for si, _ in items) / len(items)
        if all_stable and avg_si >= STABILITY_INDEX_STABLE:
            zones.append({
                "rpm_min": rpm_start,
                "rpm_max": rpm_start + RPM_BUCKET_SIZE,
            })
    return zones


def update_machine_learning(session: Any, machine_instance_id: int, history_limit: int = 500) -> Dict[str, Any]:
    """
    Анализ истории станка и коррекция K_machine_real, ap_crit_real, SAFE_ZONES.

    1) Загрузить последние записи machine_operation_history.
    2) Для каждой записи: StabilityIndex. Если < 0.5 → K_machine_real *= 0.97; если > 0.8 → *= 1.02.
    3) Дополнительно: при result=chatter → K *= 0.95; при result=stable и SI > 0.8 → K *= 1.02.
    4) Ограничить K в [0.6, 1.2].
    5) Построить SAFE_ZONES по диапазонам n.
    6) При необходимости скорректировать ap_crit_real (если стабильно работала меньшая ap, чем расчётная).
    """
    from app.storage.machine_library import MachineOperationHistory, MachineLearnedParams

    learned = _get_or_create_learned(session, machine_instance_id)
    if not learned:
        return {"success": False, "error": "machine instance or learned params not found"}

    history = (
        session.query(MachineOperationHistory)
        .filter_by(machine_instance_id=machine_instance_id)
        .order_by(MachineOperationHistory.created_at.desc())
        .limit(history_limit)
        .all()
    )
    if not history:
        return {"success": True, "records_processed": 0, "k_machine_real": float(learned.k_machine_real)}

    v_limit = _get_v_limit(session, learned)
    k = float(learned.k_machine_real)
    ap_crit = float(learned.ap_crit_real) if learned.ap_crit_real else None

    stable_high_count = 0
    unstable_count = 0
    chatter_count = 0
    ap_stable_below_crit = 0

    for r in history:
        v_rms = float(r.vibration_rms) if r.vibration_rms is not None else 0.0
        si = stability_index(v_rms, v_limit)
        res = (r.result or "stable").lower()

        if res == "chatter":
            chatter_count += 1
        elif si < STABILITY_INDEX_UNSTABLE:
            unstable_count += 1
        elif si >= STABILITY_INDEX_STABLE and res == "stable":
            stable_high_count += 1

        if res == "stable" and r.ap_mm is not None and ap_crit is not None and float(r.ap_mm) < ap_crit * 0.85:
            ap_stable_below_crit += 1

    n = len(history)
    k_increase = K_INCREASE_STABLE
    try:
        from app.storage.machine_library import CalculationCoefficient
        row = session.query(CalculationCoefficient).filter_by(key="k_increase_stable").first()
        if row and float(row.value) > 0:
            k_increase = float(row.value)
    except Exception:
        pass
    if chatter_count > 0:
        k *= K_DECREASE_CHATTER
    if unstable_count > stable_high_count and n > 0:
        k *= K_DECREASE_UNSTABLE
    elif stable_high_count > unstable_count and n > 0:
        k *= k_increase
    if ap_stable_below_crit >= 3 and ap_crit is not None:
        ap_crit *= AP_CRIT_DECREASE_FACTOR

    k = max(K_MACHINE_MIN, min(K_MACHINE_MAX, k))
    learned.k_machine_real = Decimal(str(round(k, 4)))
    if ap_crit is not None and ap_crit > 0:
        learned.ap_crit_real = Decimal(str(round(ap_crit, 6)))

    safe_zones = _build_safe_zones(history, v_limit)
    learned.safe_zones_json = json.dumps(safe_zones) if safe_zones else None

    session.flush()
    return {
        "success": True,
        "records_processed": len(history),
        "k_machine_real": k,
        "ap_crit_real": ap_crit,
        "safe_zones_count": len(safe_zones),
        "stable_count": stable_high_count,
        "unstable_count": unstable_count,
        "chatter_count": chatter_count,
    }


def get_safe_zones(session: Any, machine_instance_id: int) -> List[Dict[str, int]]:
    """Вернуть список безопасных диапазонов оборотов для станка."""
    from app.storage.machine_library import MachineLearnedParams

    learned = session.query(MachineLearnedParams).filter_by(machine_instance_id=machine_instance_id).first()
    if not learned or not learned.safe_zones_json:
        return []
    try:
        return json.loads(learned.safe_zones_json)
    except Exception:
        return []


def get_learned_params(session: Any, machine_instance_id: int) -> Optional[Dict[str, Any]]:
    """Вернуть обученные параметры (k_machine_real, ap_crit_real, safe_zones, v_limit)."""
    from app.storage.machine_library import MachineLearnedParams

    learned = session.query(MachineLearnedParams).filter_by(machine_instance_id=machine_instance_id).first()
    if not learned:
        return None
    v_limit = _get_v_limit(session, learned)
    safe_zones = []
    if learned.safe_zones_json:
        try:
            safe_zones = json.loads(learned.safe_zones_json)
        except Exception:
            pass
    return {
        "k_machine_real": float(learned.k_machine_real),
        "ap_crit_real": float(learned.ap_crit_real) if learned.ap_crit_real else None,
        "safe_zones": safe_zones,
        "vibration_limit_mm_s": v_limit,
        "updated_at": learned.updated_at,
    }


def predict_stability(
    session: Any,
    machine_instance_id: int,
    modes: Dict[str, float],
) -> StabilityPrediction:
    """
    Оценка стабильности режимов по накопленной истории.

    modes: rpm, ap_mm, feed_mm_rev, vibration_rms (опционально — если уже измерена).
    Возвращает: predicted_stable, stability_index_estimate, in_safe_zone, k_machine_used, recommendations.
    """
    rpm = modes.get("rpm") or modes.get("n", 0)
    ap_mm = modes.get("ap_mm", 0)
    vibration_rms = modes.get("vibration_rms")

    learned = get_learned_params(session, machine_instance_id)
    k_used = 1.0
    safe_zones: List[Dict[str, int]] = []
    v_limit = 5.0

    if learned:
        k_used = learned["k_machine_real"]
        safe_zones = learned.get("safe_zones") or []
        v_limit = learned.get("vibration_limit_mm_s") or 5.0

    in_safe_zone = False
    if rpm and safe_zones:
        for z in safe_zones:
            if z.get("rpm_min", 0) <= rpm <= z.get("rpm_max", 0):
                in_safe_zone = True
                break

    if vibration_rms is not None:
        si = stability_index(float(vibration_rms), v_limit)
    else:
        si = 0.75 if in_safe_zone else 0.5

    predicted_stable = si >= STABILITY_INDEX_STABLE or in_safe_zone
    recs = []
    if not in_safe_zone and safe_zones:
        recs.append("Рекомендуемые диапазоны оборотов по истории: " + ", ".join(
            f"{z['rpm_min']}-{z['rpm_max']}" for z in safe_zones[:5]
        ))
    if si < STABILITY_INDEX_UNSTABLE and not predicted_stable:
        recs.append("Режим может быть нестабильным (низкий индекс стабильности). Снизьте ap или обороты.")

    return StabilityPrediction(
        predicted_stable=predicted_stable,
        stability_index_estimate=si,
        in_safe_zone=in_safe_zone,
        k_machine_used=k_used,
        safe_zones=safe_zones,
        recommendations=recs,
    )
