-- =============================================================================
-- CNC Assistant: библиотека станков и учёт установки/жесткости (PostgreSQL)
-- Один и тот же модельный станок может вести себя по-разному в зависимости
-- от фундамента, анкеровки и виброизоляции.
-- =============================================================================

-- Типы станков
CREATE TYPE machine_kind AS ENUM ('turning', 'milling', 'boring', 'drilling');

-- Тип фундамента/установки
CREATE TYPE foundation_type AS ENUM ('concrete', 'slab', 'frame', 'floating_slab');

-- Тип анкеровки
CREATE TYPE anchoring_type AS ENUM ('rigid', 'soft', 'none');

-- -----------------------------------------------------------------------------
-- Модель станка (каталог, общая библиотека)
-- -----------------------------------------------------------------------------
CREATE TABLE machine_models (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    manufacturer    VARCHAR(255),
    machine_kind    machine_kind NOT NULL,

    -- Базовые характеристики
    power_kw        NUMERIC(10, 2) NOT NULL,           -- мощность шпинделя, кВт
    max_rpm         INTEGER NOT NULL,                  -- макс. обороты, об/мин
    torque_nm       NUMERIC(12, 2),                    -- крутящий момент, Н·м
    mass_kg         NUMERIC(10, 2),                    -- масса станка, кг

    -- Жёсткость шпиндельного узла (базовый коэффициент 0.5–1.2, 1.0 = эталон)
    spindle_rigidity_base NUMERIC(5, 3) NOT NULL DEFAULT 1.0 CHECK (spindle_rigidity_base >= 0.3 AND spindle_rigidity_base <= 1.5),

    -- Ограничения (опционально)
    max_cutting_force_n NUMERIC(12, 2),
    max_tool_overhang_mm NUMERIC(8, 2),

    created_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (name, manufacturer)
);

CREATE INDEX idx_machine_models_kind ON machine_models(machine_kind);
CREATE INDEX idx_machine_models_power ON machine_models(power_kw);

-- -----------------------------------------------------------------------------
-- Конкретный установленный станок (экземпляр)
-- Ссылается на модель + монтаж + профиль жёсткости
-- -----------------------------------------------------------------------------
CREATE TABLE machine_instances (
    id                  SERIAL PRIMARY KEY,
    model_id            INTEGER NOT NULL REFERENCES machine_models(id) ON DELETE RESTRICT,
    instance_name       VARCHAR(255) NOT NULL,         -- например "Токарный №3", "Фрезер ЧПУ цех 2"

    -- Привязка к монтажу и жёсткости (опционально; если NULL — используются дефолты по модели)
    mounting_id         INTEGER NULL,                 -- см. machine_mounting
    rigidity_profile_id INTEGER NULL,                 -- см. machine_rigidity_profile

    is_active           BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_machine_instances_model ON machine_instances(model_id);
CREATE UNIQUE INDEX idx_machine_instances_name ON machine_instances(instance_name);

-- -----------------------------------------------------------------------------
-- Условия монтажа (фундамент, анкеровка, виброизоляция)
-- -----------------------------------------------------------------------------
CREATE TABLE machine_mounting (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(255),                 -- например "Бетонный фундамент, жёсткая анкеровка"

    foundation          foundation_type NOT NULL,
    anchoring           anchoring_type NOT NULL,
    has_vibration_pads   BOOLEAN NOT NULL DEFAULT false,

    -- Коэффициент жёсткости установки (0.5–1.2). 1.0 = идеальная установка.
    mounting_stiffness_coeff NUMERIC(4, 2) NOT NULL DEFAULT 1.0
        CHECK (mounting_stiffness_coeff >= 0.5 AND mounting_stiffness_coeff <= 1.2),

    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- Профиль жёсткости/вибрации (реальные измерения или оценка)
-- -----------------------------------------------------------------------------
CREATE TABLE machine_rigidity_profile (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(255),

    -- Жёсткость узла (относительный коэффициент, 0.5–1.2)
    rigidity_coeff      NUMERIC(4, 2) NOT NULL DEFAULT 1.0
        CHECK (rigidity_coeff >= 0.5 AND rigidity_coeff <= 1.2),

    -- Демпфирование (опционально, для расчётов вибрации)
    damping_ratio       NUMERIC(5, 4),                 -- 0.01–0.1 типично

    -- Реальный уровень вибрации (мм/с, по стандарту вибродиагностики)
    vibration_mm_per_s  NUMERIC(8, 4),

    -- Риск вибрации при L/D > 4 (low / moderate / high / critical)
    vibration_risk      VARCHAR(20) DEFAULT 'moderate',

    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- Связь machine_instances с mounting и rigidity (FK уже в machine_instances)
-- Добавляем FK после создания таблиц
-- -----------------------------------------------------------------------------
ALTER TABLE machine_instances
    ADD CONSTRAINT fk_machine_instances_mounting
        FOREIGN KEY (mounting_id) REFERENCES machine_mounting(id) ON DELETE SET NULL;
ALTER TABLE machine_instances
    ADD CONSTRAINT fk_machine_instances_rigidity
        FOREIGN KEY (rigidity_profile_id) REFERENCES machine_rigidity_profile(id) ON DELETE SET NULL;

-- -----------------------------------------------------------------------------
-- Триггер обновления updated_at
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER machine_models_updated_at
    BEFORE UPDATE ON machine_models
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER machine_instances_updated_at
    BEFORE UPDATE ON machine_instances
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

-- -----------------------------------------------------------------------------
-- Представление: экземпляр с полными данными для расчёта
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_machine_instance_full AS
SELECT
    i.id AS instance_id,
    i.instance_name,
    i.model_id,
    m.name AS model_name,
    m.manufacturer,
    m.machine_kind,
    m.power_kw,
    m.max_rpm,
    m.torque_nm,
    m.mass_kg,
    m.spindle_rigidity_base,
    COALESCE(mt.mounting_stiffness_coeff, 1.0) AS mounting_stiffness_coeff,
    COALESCE(r.rigidity_coeff, 1.0) AS rigidity_coeff,
    r.vibration_mm_per_s,
    r.vibration_risk,
    (m.spindle_rigidity_base * COALESCE(mt.mounting_stiffness_coeff, 1.0) * COALESCE(r.rigidity_coeff, 1.0)) AS k_total
FROM machine_instances i
JOIN machine_models m ON m.id = i.model_id
LEFT JOIN machine_mounting mt ON mt.id = i.mounting_id
LEFT JOIN machine_rigidity_profile r ON r.id = i.rigidity_profile_id
WHERE i.is_active = true;

COMMENT ON TABLE machine_models IS 'Каталог моделей станков (базовые характеристики)';
COMMENT ON TABLE machine_instances IS 'Конкретные установленные станки с привязкой к монтажу и жёсткости';
COMMENT ON TABLE machine_mounting IS 'Тип фундамента, анкеровка, виброопоры, коэффициент жёсткости установки';
COMMENT ON TABLE machine_rigidity_profile IS 'Жёсткость, демпфирование, уровень вибрации (реальные измерения)';

-- -----------------------------------------------------------------------------
-- Уровень оператора (опыт) — коэффициент для расчёта режимов
-- -----------------------------------------------------------------------------
CREATE TABLE operator_levels (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(20) NOT NULL UNIQUE,
    name            VARCHAR(100) NOT NULL,
    coefficient     NUMERIC(4, 2) NOT NULL DEFAULT 1.0
        CHECK (coefficient >= 0.5 AND coefficient <= 1.2),
    description     TEXT,
    sort_order      INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO operator_levels (code, name, coefficient, sort_order) VALUES
    ('novice',      'Новичок',      0.75, 1),
    ('medium',      'Средний',      0.90, 2),
    ('experienced', 'Опытный',      1.00, 3),
    ('expert',      'Эксперт',      1.10, 4);

-- -----------------------------------------------------------------------------
-- Настраиваемые коэффициенты расчёта (мощность 0.75, C_machine для ap_crit и т.д.)
-- -----------------------------------------------------------------------------
CREATE TABLE calculation_coefficients (
    id          SERIAL PRIMARY KEY,
    key         VARCHAR(80) NOT NULL UNIQUE,
    value       NUMERIC(12, 6) NOT NULL,
    category    VARCHAR(40),
    description TEXT,
    updated_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER calculation_coefficients_updated_at
    BEFORE UPDATE ON calculation_coefficients
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

INSERT INTO calculation_coefficients (key, value, category, description) VALUES
    ('power_reserve_ratio', 0.75,  'power_limit', 'Доля мощности станка для резания: Pc ≤ value * P_machine'),
    ('power_reserve_warning', 0.2,  'power_limit', 'Запас мощности: предупреждение если P_reserve_ratio < value'),
    ('power_reserve_critical', 0.1, 'power_limit', 'Запас мощности: критично если P_reserve_ratio < value'),
    ('torque_warning_ratio', 0.8,  'power_limit', 'Предупреждение по моменту если M_required > value * Tmax'),
    ('c_machine_ap_crit',   1e-6,  'stiffness',   'Коэффициент для расчёта критической глубины резания (анти-chatter)'),
    ('risk_index_high', 2.0,       'vibration',  'Индекс риска вибрации: high risk если RiskIndex > value'),
    ('risk_index_very_high', 3.0,   'vibration',  'Индекс риска вибрации: very high risk если RiskIndex > value'),
    ('vibration_frequency_tolerance', 0.05, 'vibration', 'Допуск совпадения частоты при анализе вибрации (0.05 = 5%)'),
    ('vibration_limit_mm_s', 5.0,   'vibration',  'Допустимая вибрация V_limit (мм/с) для StabilityIndex = 1 - V_rms/V_limit'),
    ('mode_aggressive_vc', 1.05,   'mode', 'Режим AGGRESSIVE: множитель Vc'),
    ('mode_aggressive_ap', 1.1,    'mode', 'Режим AGGRESSIVE: множитель ap'),
    ('mode_aggressive_f', 1.05,   'mode', 'Режим AGGRESSIVE: множитель f'),
    ('mode_safe_vc', 0.85,        'mode', 'Режим SAFE: множитель Vc'),
    ('mode_safe_ap', 0.8,         'mode', 'Режим SAFE: множитель ap'),
    ('mode_safe_f', 0.9,         'mode', 'Режим SAFE: множитель f'),
    ('bad_zone_shift_ratio', 0.15,'vibration', 'Смещение оборотов при попадании в bad zone: ±15%'),
    ('k_increase_stable', 1.01,   'learning', 'Авто-адаптация: множитель K_machine при StabilityIndex > 0.8');

-- -----------------------------------------------------------------------------
-- История операций станка (автообучение)
-- -----------------------------------------------------------------------------
CREATE TABLE machine_operation_history (
    id                  SERIAL PRIMARY KEY,
    machine_instance_id INTEGER NOT NULL REFERENCES machine_instances(id) ON DELETE CASCADE,

    tool                VARCHAR(255),
    material            VARCHAR(255),
    diameter_mm         NUMERIC(10, 3),
    overhang_mm         NUMERIC(10, 3),
    teeth_count         INTEGER,

    rpm                 NUMERIC(12, 2),
    vc_m_min            NUMERIC(10, 2),
    feed_mm_rev         NUMERIC(8, 4),
    ap_mm               NUMERIC(8, 4),
    ae_mm               NUMERIC(8, 4),

    vibration_rms       NUMERIC(10, 4),
    peak_frequency_hz   NUMERIC(10, 2),
    power_kw            NUMERIC(8, 3),

    result              VARCHAR(20) NOT NULL,   -- stable, chatter, failure, tool_wear
    operator_level      VARCHAR(20),
    created_at          TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_machine_operation_history_instance ON machine_operation_history(machine_instance_id);
CREATE INDEX idx_machine_operation_history_created ON machine_operation_history(created_at);

-- -----------------------------------------------------------------------------
-- Обученные параметры станка (K_machine_real, ap_crit_real, SAFE_ZONES)
-- -----------------------------------------------------------------------------
CREATE TABLE machine_learned_params (
    id                  SERIAL PRIMARY KEY,
    machine_instance_id INTEGER NOT NULL UNIQUE REFERENCES machine_instances(id) ON DELETE CASCADE,

    k_machine_real      NUMERIC(5, 3) NOT NULL DEFAULT 1.0
        CHECK (k_machine_real >= 0.6 AND k_machine_real <= 1.2),
    ap_crit_real        NUMERIC(12, 6),
    safe_zones_json     TEXT,
    vibration_limit_mm_s NUMERIC(8, 2),
    updated_at          TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER machine_learned_params_updated_at
    BEFORE UPDATE ON machine_learned_params
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

-- -----------------------------------------------------------------------------
-- Зоны оборотов (нестабильные bad / безопасные safe)
-- -----------------------------------------------------------------------------
CREATE TABLE machine_speed_zones (
    id                  SERIAL PRIMARY KEY,
    machine_instance_id INTEGER NOT NULL REFERENCES machine_instances(id) ON DELETE CASCADE,
    min_rpm             NUMERIC(10, 2) NOT NULL,
    max_rpm             NUMERIC(10, 2) NOT NULL,
    zone_type           VARCHAR(10) NOT NULL CHECK (zone_type IN ('bad', 'safe')),
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_machine_speed_zones_instance ON machine_speed_zones(machine_instance_id);
