"""
Пример использования библиотеки станков и расчётного модуля.

Требуется PostgreSQL с применённой схемой schema_machines_postgres.sql
и установленный psycopg2: pip install psycopg2-binary

Либо SQLite для теста ORM (таблицы machine_models, machine_instances и т.д.
нужно создать через create_all).
"""

from decimal import Decimal


def example_sql_select_best_machine():
    """
    Пример SQL-запроса: выбор лучшего станка по требованиям операции.
    Используется представление v_machine_instance_full с готовым k_total.
    """
    sql = """
-- Требования: токарная операция, нужна мощность не менее 15 кВт, макс. обороты 3000.
-- Важно: стабильность при L/D > 4 (жёсткость), минимизация вибрации.

WITH requirements AS (
    SELECT
        15.0   AS power_kw_min,
        3000   AS max_rpm_min,
        'turning' AS machine_kind,
        0.85   AS k_total_min
),
candidates AS (
    SELECT
        v.instance_id,
        v.instance_name,
        v.model_name,
        v.power_kw,
        v.max_rpm,
        v.torque_nm,
        v.k_total,
        v.vibration_mm_per_s,
        v.vibration_risk,
        -- Простой скоринг: запас по мощности + жёсткость
        LEAST(1.0, (v.power_kw / r.power_kw_min)) AS score_power,
        CASE WHEN v.k_total >= r.k_total_min THEN 1.0 ELSE v.k_total / r.k_total_min END AS score_rigidity
    FROM v_machine_instance_full v
    CROSS JOIN requirements r
    WHERE v.machine_kind = r.machine_kind
      AND v.max_rpm >= r.max_rpm_min
)
SELECT
    instance_id,
    instance_name,
    model_name,
    power_kw,
    max_rpm,
    k_total,
    vibration_risk,
    (0.6 * score_power + 0.4 * score_rigidity) AS total_score
FROM candidates
ORDER BY total_score DESC, k_total DESC
LIMIT 5;
"""
    return sql


def example_python_usage():
    """
    Пример вызова из Python: расчёт режимов и выбор станка.
    Запускать только при наличии БД с таблицами machine_*.
    """
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.storage.machine_library import (
            MachineModel,
            MachineInstance,
            MachineMounting,
            MachineRigidityProfile,
        )
        from app.services.machine_modes_calculator import (
            calculate_optimal_modes,
            ToolParams,
            MaterialParams,
        )
        from app.services.engineering_calculator import (
            calculate_optimal_modes as calc_engineering,
            ToolParams as EngToolParams,
            MaterialParams as EngMaterialParams,
            OperatorParams,
            EngineeringResult,
        )
        from app.services.machine_selector import (
            select_best_machine,
            OperationRequirements,
        )
    except ImportError as e:
        return f"Import error: {e}"

    # Подключение к PostgreSQL (или SQLite для теста)
    # DATABASE_URL = "postgresql://user:pass@localhost/cnc_assistant"
    DATABASE_URL = "sqlite:///app/storage/cnc.db"
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1) Создание таблиц (если ещё нет). Используем Base из models — на нём зарегистрированы и machine_*
    try:
        from app.storage.models import Base
        Base.metadata.create_all(engine)
    except Exception:
        pass

    model = session.query(MachineModel).first()
    if not model:
        # Создаём тестовые данные
        model = MachineModel(
            name="Токарный ЧПУ NEF500",
            manufacturer="СтанкоМаш",
            machine_kind="turning",
            power_kw=Decimal("15.0"),
            max_rpm=3500,
            torque_nm=Decimal("200"),
            mass_kg=Decimal("2500"),
            spindle_rigidity_base=Decimal("1.0"),
        )
        session.add(model)
        session.flush()

        mounting = MachineMounting(
            name="Бетон, жёсткая анкеровка",
            foundation="concrete",
            anchoring="rigid",
            has_vibration_pads=False,
            mounting_stiffness_coeff=Decimal("1.0"),
        )
        session.add(mounting)
        session.flush()

        rigidity = MachineRigidityProfile(
            name="Нормальная жёсткость",
            rigidity_coeff=Decimal("0.95"),
            vibration_mm_per_s=Decimal("3.5"),
            vibration_risk="moderate",
        )
        session.add(rigidity)
        session.flush()

        instance = MachineInstance(
            model_id=model.id,
            instance_name="Токарный №3",
            mounting_id=mounting.id,
            rigidity_profile_id=rigidity.id,
        )
        session.add(instance)
        session.commit()

    instances = session.query(MachineInstance).filter(MachineInstance.is_active == True).all()
    if not instances:
        return "No machine instances in DB. Create model/mounting/rigidity/instance first."

    # 2) Расчёт оптимальных режимов (простой калькулятор)
    tool = ToolParams(vc_m_min=180.0, feed=0.25, ap_mm=2.0, operation="turning")
    material = MaterialParams(name="сталь 45", vibration_tendency="medium")
    result = calculate_optimal_modes(instances[0], tool, material, diameter_mm=80.0)
    print("K_total:", result.k_total)
    print("Скорректированные режимы: Vc={}, ap={}, rpm={}".format(
        result.vc_m_min, result.ap_mm, result.rpm))
    print("Коррекции:", result.corrections_applied)

    # 2b) Инженерный расчёт (полные формулы: K_LD, K_mount, K_vib, K_operator, ap_crit, ограничения)
    tool_eng = EngToolParams(
        vc_m_min=180.0, feed_mm_rev=0.25, ap_mm=2.0,
        tool_overhang_mm=60.0, tool_diameter_mm=20.0, operation="turning",
    )
    mat_eng = EngMaterialParams(name="сталь 45", kc_n_mm2=2000.0)
    operator = OperatorParams(level="experienced")
    res_eng = calc_engineering(instances[0], tool_eng, mat_eng, operator, diameter_mm=80.0, db_session=session)
    print("Инженерный расчёт: Vc={}, ap={}, Pc={} кВт, K_system={}".format(
        res_eng.vc_m_min, res_eng.ap_mm, res_eng.pc_kw, res_eng.k_system))
    print("Коррекции:", res_eng.corrections_applied)

    # 3) Выбор лучшего станка (классический скоринг)
    req = OperationRequirements(
        power_kw_min=11.0,
        max_rpm_min=2000,
        machine_kind="turning",
        ld_ratio=5.0,
        vibration_sensitive=True,
        preferred_k_total_min=0.85,
    )
    best = select_best_machine(instances, req, top_n=3)
    for inst, score, breakdown in best:
        print(f"Станок: {inst.instance_name}, score={score:.3f}, breakdown={breakdown}")

    # 3b) Выбор лучшего станка по инженерной формуле Score (ТЗ)
    req_eng = OperationRequirements(
        machine_kind="turning",
        ld_ratio=5.0,
        power_required_kw=res_eng.pc_kw,
        torque_required_nm=(9550.0 * res_eng.pc_kw / res_eng.rpm) if res_eng.rpm else 0,
        use_engineering_score=True,
    )
    best_eng = select_best_machine(instances, req_eng, top_n=3)
    for inst, score, breakdown in best_eng:
        print(f"Станок (инж. Score): {inst.instance_name}, score={score:.3f}, {breakdown}")

    session.close()
    return "OK"


if __name__ == "__main__":
    print("=== SQL пример (выбор лучшего станка) ===")
    print(example_sql_select_best_machine())
    print("\n=== Python пример (расчёт режимов + выбор станка) ===")
    print(example_python_usage())
