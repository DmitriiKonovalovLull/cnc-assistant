"""Инженерный расчёт режимов обработки: мощность, момент, риск вибрации, режимы, зоны оборотов."""

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Union

logger = logging.getLogger(__name__)

WorkMode = Literal["AGGRESSIVE", "NORMAL", "SAFE"]

DEFAULT_POWER_RESERVE_RATIO = 0.75
DEFAULT_C_MACHINE_AP_CRIT = 1e-6
DEFAULT_KC_N_MM2 = 2000.0


@dataclass
class ToolParams:
    """Параметры инструмента: Vc, подача, ap, L, D, z, операция."""
    vc_m_min: float = 0.0
    feed_mm_rev: float = 0.0
    ap_mm: float = 0.0
    ae_mm: Optional[float] = None
    tool_overhang_mm: float = 30.0
    tool_diameter_mm: float = 20.0
    teeth_count: Optional[int] = None
    operation: str = "turning"
    k_tool: Optional[float] = None


@dataclass
class MaterialParams:
    """Материал: название, kc (Н/мм²), склонность к вибрации."""
    name: str = ""
    kc_n_mm2: float = 2000.0
    vibration_tendency: str = "medium"


@dataclass
class OperatorParams:
    """Уровень оператора: level (novice/medium/experienced/expert) или k_operator явно."""
    level: str = "experienced"
    k_operator: float = 1.0


@dataclass
class EngineeringResult:
    """Результат инженерного расчёта."""
    vc_m_min: float = 0.0
    rpm: float = 0.0
    feed_mm_rev: float = 0.0
    vf_mm_min: float = 0.0
    ap_mm: float = 0.0
    ae_mm: Optional[float] = None
    fc_n: float = 0.0
    pc_kw: float = 0.0
    m_required_nm: float = 0.0
    power_reserve_ratio: float = 1.0
    k_system: float = 1.0
    k_ld: float = 1.0
    k_mount: float = 1.0
    k_vib: float = 1.0
    k_operator: float = 1.0
    ld_ratio: float = 0.0
    vibration_risk_index: float = 0.0
    vibration_risk_level: str = ""
    vibration_issue_type: Optional[str] = None
    ap_crit_used: bool = False
    corrections_applied: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    limits_respected: bool = True


@dataclass
class EngineeringReport:
    """Структурированный инженерный отчёт."""
    required_power_kw: float = 0.0
    power_reserve_ratio_pct: float = 0.0
    torque_required_nm: float = 0.0
    torque_limit_nm: float = 0.0
    vibration_risk_index: float = 0.0
    vibration_risk_level: str = ""
    vibration_issue_type: Optional[str] = None
    final_modes: Dict[str, float] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    corrections: List[str] = field(default_factory=list)


def _get_coeff_from_db(session: Any, key: str, default: float) -> float:
    """Читает коэффициент из calculation_coefficients по ключу."""
    if session is None:
        return default
    try:
        from app.storage.machine_library import CalculationCoefficient
        row = session.query(CalculationCoefficient).filter_by(key=key).first()
        return float(row.value) if row else default
    except Exception:
        return default


def _get_operator_coefficient(session: Any, operator: Union[OperatorParams, Dict[str, Any], None]) -> float:
    """K_operator: новичок 0.75, средний 0.9, опытный 1.0, эксперт 1.1."""
    if operator is None:
        return 1.0
    if isinstance(operator, dict):
        if "k_operator" in operator and operator["k_operator"] is not None:
            return float(operator["k_operator"])
        level = (operator.get("level") or "experienced").lower()
    else:
        if operator.k_operator != 1.0:
            return operator.k_operator
        level = (operator.level or "experienced").lower()
    defaults = {"novice": 0.75, "medium": 0.9, "experienced": 1.0, "expert": 1.1}
    if level in defaults:
        return defaults[level]
    if session:
        try:
            from app.storage.machine_library import OperatorLevel
            row = session.query(OperatorLevel).filter_by(code=level).first()
            return float(row.coefficient) if row else 1.0
        except Exception:
            pass
    return 1.0


def _k_ld(overhang_mm: float, diameter_mm: float) -> tuple:
    """R = L/D. Если R ≤ 3: K_LD = 1; если R > 3: K_LD = (3/R)^2."""
    if diameter_mm <= 0:
        return 1.0, 0.0
    r = overhang_mm / diameter_mm
    if r <= 3:
        return 1.0, r
    k = (3.0 / r) ** 2
    return max(0.1, min(1.0, k)), r


def _k_vib(v_rms_mm_s: Optional[float]) -> tuple:
    """K_vib = 1 / (1 + V_rms). Если V_rms > 1.0 — флаг снизить ap на 20%."""
    if v_rms_mm_s is None or v_rms_mm_s < 0:
        return 1.0, False
    k = 1.0 / (1.0 + v_rms_mm_s)
    reduce_ap_20 = v_rms_mm_s > 1.0
    return max(0.2, min(1.0, k)), reduce_ap_20


def _ap_crit(
    d_mm: float,
    l_mm: float,
    k_mount: float,
    k_machine_base: float,
    c_machine: float,
) -> float:
    """ap_crit = C_machine * (D^4 / L^3) * K_mount * K_machine_base."""
    if l_mm <= 0:
        return 1e6
    term = (d_mm ** 4) / (l_mm ** 3)
    return c_machine * term * k_mount * k_machine_base


def _machine_data(instance: Any) -> Dict[str, float]:
    """Извлечь из экземпляра станка: P_machine, Tmax, n_max, K_machine_base, K_mount, V_rms."""
    model = getattr(instance, "model", None) or (instance.get("model") if isinstance(instance, dict) else None)
    mounting = getattr(instance, "mounting", None) or (instance.get("mounting") if isinstance(instance, dict) else None)
    rigidity = getattr(instance, "rigidity_profile", None) or (instance.get("rigidity_profile") if isinstance(instance, dict) else None)

    def _f(obj: Any, key: str, default: float = 0.0) -> float:
        if obj is None:
            return default
        v = getattr(obj, key, None) if not isinstance(obj, dict) else obj.get(key)
        if v is None:
            return default
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    p_machine = _f(model, "power_kw", 15.0)
    n_max = _f(model, "max_rpm", 3000.0)
    t_max = _f(model, "torque_nm", 200.0)
    k_machine_base = _f(model, "spindle_rigidity_base", 1.0)
    k_mount = _f(mounting, "mounting_stiffness_coeff", 1.0) if mounting else 1.0
    v_rms = _f(rigidity, "vibration_mm_per_s") if rigidity else None
    if v_rms is not None and v_rms <= 0:
        v_rms = None
    return {
        "p_machine": p_machine,
        "n_max": n_max,
        "t_max": t_max,
        "k_machine_base": k_machine_base,
        "k_mount": k_mount,
        "v_rms": v_rms,
    }


def _stiffness_k_total(
    k_machine: float,
    k_tool: Optional[float],
    k_fixture: Optional[float],
) -> float:
    """1/K_total = 1/K_machine + 1/K_tool + 1/K_fixture. Если нет данных — эмпирика."""
    inv = 1.0 / max(0.01, k_machine)
    if k_tool and k_tool > 0:
        inv += 1.0 / k_tool
    else:
        inv += 0.2
    if k_fixture and k_fixture > 0:
        inv += 1.0 / k_fixture
    else:
        inv += 0.1
    return 1.0 / inv


def _vibration_risk_index(
    ld_ratio: float, ap_mm: float, d_mm: float, k_system: float
) -> tuple:
    """RiskIndex = (L/D)*(ap/D)*(1/K_system). Возвращает (index, level)."""
    if d_mm <= 0 or k_system <= 0:
        return 0.0, ""
    ri = ld_ratio * (ap_mm / d_mm) * (1.0 / k_system)
    level = ""
    if ri > 3.0:
        level = "very_high"
    elif ri > 2.0:
        level = "high"
    return ri, level


def _apply_work_mode(vc: float, ap: float, f: float, mode: str, db_session: Any) -> tuple:
    """Множители Vc, ap, f по режиму (AGGRESSIVE/NORMAL/SAFE) из БД."""
    mode = (mode or "NORMAL").upper()
    if mode == "NORMAL":
        return vc, ap, f
    if mode == "AGGRESSIVE":
        kv = _get_coeff_from_db(db_session, "mode_aggressive_vc", 1.05)
        ka = _get_coeff_from_db(db_session, "mode_aggressive_ap", 1.1)
        kf = _get_coeff_from_db(db_session, "mode_aggressive_f", 1.05)
        return vc * kv, ap * ka, f * kf
    if mode == "SAFE":
        kv = _get_coeff_from_db(db_session, "mode_safe_vc", 0.85)
        ka = _get_coeff_from_db(db_session, "mode_safe_ap", 0.8)
        kf = _get_coeff_from_db(db_session, "mode_safe_f", 0.9)
        return vc * kv, ap * ka, f * kf
    return vc, ap, f


def _get_bad_zone_shift(
    db_session: Any, machine_instance_id: int, n: float
) -> Optional[float]:
    """Если n в зоне bad — возвращает n со сдвигом (bad_zone_shift_ratio), иначе None."""
    if not db_session or not machine_instance_id or n <= 0:
        return None
    try:
        from app.storage.machine_library import MachineSpeedZone
        zones = db_session.query(MachineSpeedZone).filter_by(
            machine_instance_id=machine_instance_id,
            zone_type="bad",
        ).all()
        shift_ratio = _get_coeff_from_db(db_session, "bad_zone_shift_ratio", 0.15)
        for z in zones:
            lo, hi = float(z.min_rpm), float(z.max_rpm)
            if lo <= n <= hi:
                n_new = n * (1.0 - shift_ratio)
                if n_new < lo:
                    n_new = hi * (1.0 + shift_ratio)
                return n_new
    except Exception:
        pass
    return None


def calculate_optimal_modes(
    machine_instance: Any,
    tool: Union[ToolParams, Dict[str, Any]],
    material: Union[MaterialParams, Dict[str, Any]],
    operator: Union[OperatorParams, Dict[str, Any], None] = None,
    diameter_mm: Optional[float] = None,
    db_session: Any = None,
    mode: WorkMode = "NORMAL",
) -> EngineeringResult:
    """
    Рассчитать оптимальные режимы с учётом всех факторов.

    - Базовые формулы: Vc, n, Vf, Fc, Pc.
    - Жёсткость системы, K_LD (вылет), K_mount, K_vib, K_operator.
    - ap_crit (анти-chatter), ограничения Pc ≤ 0.75*P_machine, n ≤ n_max, M ≤ Tmax.
    - K_system и коррекция: Vc_final, ap_final, f_final; при L/D > 6 доп. снижение.
    """
    if isinstance(tool, dict):
        t = ToolParams(
            vc_m_min=float(tool.get("vc_m_min", 0) or tool.get("vc", 0)),
            feed_mm_rev=float(tool.get("feed_mm_rev", 0) or tool.get("feed", 0)),
            ap_mm=float(tool.get("ap_mm", 0) or tool.get("ap", 0)),
            ae_mm=tool.get("ae_mm") and float(tool["ae_mm"]),
            tool_overhang_mm=float(tool.get("tool_overhang_mm", 30)),
            tool_diameter_mm=float(tool.get("tool_diameter_mm", 20)),
            teeth_count=tool.get("teeth_count"),
            operation=str(tool.get("operation", "turning")),
            k_tool=tool.get("k_tool"),
        )
    else:
        t = tool

    if isinstance(material, dict):
        mat = MaterialParams(
            name=material.get("name", ""),
            kc_n_mm2=float(material.get("kc_n_mm2", DEFAULT_KC_N_MM2)),
            vibration_tendency=str(material.get("vibration_tendency", "medium")),
        )
    else:
        mat = material

    mach = _machine_data(machine_instance)
    p_machine = mach["p_machine"]
    n_max = mach["n_max"]
    t_max = mach["t_max"]
    k_machine_base = mach["k_machine_base"]
    k_mount = mach["k_mount"]
    v_rms = mach["v_rms"]
    ap_crit_learned: Optional[float] = None
    if db_session and getattr(machine_instance, "id", None):
        try:
            from app.storage.machine_library import MachineLearnedParams
            learned = db_session.query(MachineLearnedParams).filter_by(
                machine_instance_id=machine_instance.id
            ).first()
            if learned:
                if learned.k_machine_real is not None:
                    k_machine_base = float(learned.k_machine_real)
                if learned.ap_crit_real is not None and float(learned.ap_crit_real) > 0:
                    ap_crit_learned = float(learned.ap_crit_real)
        except Exception:
            pass

    power_ratio = _get_coeff_from_db(db_session, "power_reserve_ratio", DEFAULT_POWER_RESERVE_RATIO)
    c_machine = _get_coeff_from_db(db_session, "c_machine_ap_crit", DEFAULT_C_MACHINE_AP_CRIT)
    k_operator = _get_operator_coefficient(db_session, operator)

    # L/D и K_LD
    l_mm = t.tool_overhang_mm
    d_tool = t.tool_diameter_mm
    k_ld, ld_ratio = _k_ld(l_mm, d_tool)

    # K_vib
    k_vib, reduce_ap_vib = _k_vib(v_rms)

    # K_system = K_machine_base * K_mount * K_LD * K_vib * K_operator
    k_system = k_machine_base * k_mount * k_ld * k_vib * k_operator
    k_system = max(0.2, min(1.2, k_system))

    # Базовые режимы
    vc_base = t.vc_m_min or 100.0
    ap_base = t.ap_mm or 2.0
    f_base = t.feed_mm_rev or 0.2

    # Критическая глубина (анти-chatter); при наличии — используем обученное значение
    ap_crit = _ap_crit(d_tool, l_mm, k_mount, k_machine_base, c_machine)
    if ap_crit_learned is not None:
        ap_crit = min(ap_crit, ap_crit_learned)
    ap_after_crit = ap_base
    ap_crit_used = False
    corrections: List[str] = []
    warnings: List[str] = []

    if ap_base > ap_crit and ap_crit > 0:
        ap_after_crit = ap_crit * 0.8
        ap_crit_used = True
        corrections.append(f"ap ограничена анти-chatter: ap_crit={ap_crit:.2f} мм → ap={ap_after_crit:.2f} мм")

    # Коррекция режимов по K_system
    vc_final = vc_base * k_system
    ap_final = ap_after_crit * k_system
    f_final = f_base * math.sqrt(k_system)

    if ld_ratio > 6:
        ap_final *= 0.7
        vc_final *= 0.85
        corrections.append(f"L/D={ld_ratio:.1f} > 6: ap −30%, Vc −15%")

    if reduce_ap_vib:
        ap_final *= 0.8
        corrections.append("V_rms > 1 мм/с: ap дополнительно −20%")

    # Диаметр обработки (для точения — диаметр детали; для фрезы — диаметр фрезы)
    d_work = diameter_mm if diameter_mm and diameter_mm > 0 else d_tool
    if t.operation == "turning" and diameter_mm and diameter_mm > 0:
        d_work = diameter_mm

    # Обороты: n = 1000*Vc / (π*D)
    if d_work <= 0:
        n = 0.0
    else:
        n = (1000.0 * vc_final) / (math.pi * d_work)

    # Ограничение n ≤ n_max
    if n_max > 0 and n > n_max:
        n = n_max
        vc_final = (math.pi * d_work * n) / 1000.0
        corrections.append(f"Обороты ограничены n_max={n_max} об/мин")
    n = max(0.0, n)

    # Сила и мощность резания: Fc = kc * ap * f (Н), Pc = Fc * Vc / 60000 (кВт)
    kc = mat.kc_n_mm2
    fc = kc * ap_final * f_final
    pc_kw = (fc * vc_final) / 60000.0
    p_limit = power_ratio * p_machine
    limits_ok = True

    if p_limit > 0 and pc_kw > p_limit:
        scale = p_limit / pc_kw
        pc_kw = p_limit
        vc_final *= scale
        ap_final *= scale
        f_final *= math.sqrt(scale)
        n = (1000.0 * vc_final) / (math.pi * d_work) if d_work > 0 else n
        if n_max > 0 and n > n_max:
            n = n_max
            vc_final = (math.pi * d_work * n) / 1000.0
        fc = kc * ap_final * f_final
        corrections.append(f"Мощность ограничена 0.75*P_machine={p_limit:.2f} кВт")
        limits_ok = True

    m_required = (9550.0 * pc_kw) / n if n > 0 else 0.0
    if t_max > 0 and n > 0 and m_required > t_max:
        m_scale = t_max / m_required
        pc_kw *= m_scale
        vc_final *= m_scale
        ap_final *= m_scale
        f_final *= math.sqrt(m_scale)
        n = (1000.0 * vc_final) / (math.pi * d_work) if d_work > 0 else n
        fc = kc * ap_final * f_final
        m_required = (9550.0 * pc_kw) / n
        corrections.append(f"Крутящий момент ограничен Tmax={t_max} Н·м")
        limits_ok = True

    # Зоны нестабильных оборотов: сместить n на ±15% при попадании в bad zone
    inst_id = getattr(machine_instance, "id", None)
    n_shifted = _get_bad_zone_shift(db_session, inst_id, n)
    if n_shifted is not None and abs(n_shifted - n) > 0.5:
        n = n_shifted
        vc_final = (math.pi * d_work * n) / 1000.0 if d_work > 0 else vc_final
        fc = kc * ap_final * f_final
        pc_kw = (fc * vc_final) / 60000.0
        m_required = (9550.0 * pc_kw) / n if n > 0 else 0.0
        vf = f_final * n
        if t.operation == "milling" and t.teeth_count:
            vf = f_final * t.teeth_count * n
        corrections.append("Обороты смещены из нестабильной зоны (bad zone) на 15%")

    # Режим работы: AGGRESSIVE / NORMAL / SAFE (применяется к итоговым режимам)
    vc_final, ap_final, f_final = _apply_work_mode(vc_final, ap_final, f_final, mode, db_session)
    if mode and mode != "NORMAL":
        fc = kc * ap_final * f_final
        pc_kw = (fc * vc_final) / 60000.0
        m_required = (9550.0 * pc_kw) / n if n > 0 else 0.0
        vf = f_final * n
        if t.operation == "milling" and t.teeth_count:
            vf = f_final * t.teeth_count * n
        corrections.append(f"Применён режим {mode}")

    # Индекс риска вибрации: (L/D)*(ap/D)*(1/K_system)
    d_risk = d_work if d_work > 0 else d_tool
    risk_idx, risk_level = _vibration_risk_index(ld_ratio, ap_final, d_risk, k_system)
    ri_high = _get_coeff_from_db(db_session, "risk_index_high", 2.0)
    ri_very = _get_coeff_from_db(db_session, "risk_index_very_high", 3.0)
    if risk_idx > ri_very:
        warnings.append("Очень высокий риск вибрации (RiskIndex > 3)")
    elif risk_idx > ri_high:
        warnings.append("Высокий риск вибрации (RiskIndex > 2)")

    # Запас мощности: P_reserve_ratio = (P_machine - Pc) / P_machine
    p_reserve_ratio = (p_machine - pc_kw) / p_machine if p_machine > 0 else 1.0
    p_reserve_warn = _get_coeff_from_db(db_session, "power_reserve_warning", 0.2)
    p_reserve_crit = _get_coeff_from_db(db_session, "power_reserve_critical", 0.1)
    if p_reserve_ratio < p_reserve_crit:
        warnings.append("Критично: запас мощности < 10%")
    elif p_reserve_ratio < p_reserve_warn:
        warnings.append("Предупреждение: запас мощности < 20%")

    # Крутящий момент: предупреждение при M_required > 0.8*Tmax
    torque_warn_ratio = _get_coeff_from_db(db_session, "torque_warning_ratio", 0.8)
    if t_max > 0 and m_required > t_max:
        warnings.append("Ошибка: требуемый момент превышает Tmax")
    elif t_max > 0 and m_required > torque_warn_ratio * t_max:
        warnings.append("Предупреждение: требуемый момент > 80% Tmax")

    return EngineeringResult(
        vc_m_min=round(vc_final, 2),
        rpm=round(n, 0),
        feed_mm_rev=round(f_final, 4),
        vf_mm_min=round(vf, 2),
        ap_mm=round(ap_final, 3),
        ae_mm=round(t.ae_mm, 3) if t.ae_mm is not None else None,
        fc_n=round(fc, 1),
        pc_kw=round(pc_kw, 3),
        m_required_nm=round(m_required, 2),
        power_reserve_ratio=round(p_reserve_ratio, 4),
        k_system=round(k_system, 4),
        k_ld=k_ld,
        k_mount=k_mount,
        k_vib=k_vib,
        k_operator=k_operator,
        ld_ratio=round(ld_ratio, 2),
        vibration_risk_index=round(risk_idx, 4),
        vibration_risk_level=risk_level,
        ap_crit_used=ap_crit_used,
        corrections_applied=corrections,
        warnings=warnings,
        limits_respected=limits_ok,
    )


def build_engineering_report(
    result: EngineeringResult,
    p_machine_kw: float,
    t_max_nm: float,
    vibration_issue_type: Optional[str] = None,
) -> EngineeringReport:
    """Сформировать структурированный инженерный отчёт из результата расчёта."""
    report = EngineeringReport(
        required_power_kw=result.pc_kw,
        power_reserve_ratio_pct=round(result.power_reserve_ratio * 100, 2),
        torque_required_nm=result.m_required_nm,
        torque_limit_nm=t_max_nm,
        vibration_risk_index=result.vibration_risk_index,
        vibration_risk_level=result.vibration_risk_level,
        vibration_issue_type=vibration_issue_type or result.vibration_issue_type,
        final_modes={
            "vc_m_min": result.vc_m_min,
            "rpm": result.rpm,
            "feed_mm_rev": result.feed_mm_rev,
            "ap_mm": result.ap_mm,
            "vf_mm_min": result.vf_mm_min,
        },
        warnings=list(result.warnings),
        corrections=list(result.corrections_applied),
    )
    return report
