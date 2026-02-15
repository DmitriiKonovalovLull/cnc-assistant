# Библиотека станков и учёт установки/жёсткости

Один и тот же модельный станок может вести себя по-разному в зависимости от фундамента, анкеровки и виброизоляции. В системе есть общая библиотека моделей станков и экземпляры с привязкой к монтажу и профилю жёсткости.

## 1. Структура БД (PostgreSQL)

- **machine_models** — каталог: мощность шпинделя, макс. обороты, крутящий момент, масса, тип (токарный/фрезерный), базовый коэффициент жёсткости шпиндельного узла.
- **machine_instances** — конкретный установленный станок: ссылка на модель + опционально монтаж и профиль жёсткости.
- **machine_mounting** — тип фундамента (бетон, плита, рама), анкеровка (жёсткая/слабая/без), виброопоры, коэффициент жёсткости установки (0.5–1.2).
- **machine_rigidity_profile** — жёсткость узла, демпфирование, реальный уровень вибрации (мм/с), риск вибрации.
- **operator_levels** — уровень оператора (code, name, coefficient): novice 0.75, medium 0.9, experienced 1.0, expert 1.1; используется как K_operator в инженерном расчёте.
- **calculation_coefficients** — настраиваемые коэффициенты (key, value, category): мощность (`power_reserve_ratio`, `power_reserve_warning`, `power_reserve_critical`), момент (`torque_warning_ratio`), риск вибрации (`risk_index_high`, `risk_index_very_high`), режимы (`mode_aggressive_*`, `mode_safe_*`), зоны (`bad_zone_shift_ratio`), обучение (`k_increase_stable`), `c_machine_ap_crit`, `vibration_limit_mm_s`, `vibration_frequency_tolerance`. Все коэффициенты можно менять через БД.
- **machine_speed_zones** — зоны оборотов по экземпляру: machine_instance_id, min_rpm, max_rpm, zone_type (bad/safe). При попадании n в bad zone расчёт смещает обороты на ±15%.
- **machine_operation_history** — история операций станка для автообучения: machine_instance_id, инструмент, материал, D, L, z, n, Vc, f, ap, ae, vibration_rms, peak_frequency, power_kw, result (stable/chatter/failure/tool_wear), operator_level, created_at.
- **machine_learned_params** — обученные параметры по истории: k_machine_real (0.6–1.2), ap_crit_real, safe_zones_json (диапазоны оборотов), vibration_limit_mm_s; один ряд на экземпляр станка.

Представление **v_machine_instance_full** выдаёт экземпляр с полями модели и готовым **k_total** для расчётов.

Схема: `app/storage/schema_machines_postgres.sql`. Для PostgreSQL выполнить скрипт; для SQLite таблицы создаются через SQLAlchemy `Base.metadata.create_all(engine)` после импорта моделей из `app.storage.machine_library`.

## 2. ORM (SQLAlchemy)

Модели в `app/storage/machine_library.py`: `MachineModel`, `MachineInstance`, `MachineMounting`, `MachineRigidityProfile`. Используется общий `Base` из `app.storage.models`.

Итоговый коэффициент жёсткости установки у экземпляра: `instance.get_k_total()` → K_total = K_machine_base × K_mounting × K_rigidity.

## 3. Расчёт оптимальных режимов

### 3.1 Простой калькулятор

Модуль: `app/services/machine_modes_calculator.py`.

- **calculate_optimal_modes(machine_instance, tool, material, diameter_mm=None)**  
  Скорректированные режимы (Vc, подача, ap, ae при фрезеровании) с учётом K_total и склонности материала к вибрации.  
  Если **K_total < 0.8**: уменьшаются ap, ae (если есть) и Vc для снижения риска вибрации.

Инструмент и материал можно передавать как `ToolParams`/`MaterialParams` или как словари.

### 3.2 Инженерный расчётный модуль (полные формулы)

Модуль: `app/services/engineering_calculator.py`.

- **calculate_optimal_modes(machine_instance, tool, material, operator=None, diameter_mm=None, db_session=None, mode='NORMAL')**  
  Режимы с учётом: материала (kc), инструмента (L/D, диаметр, подача), операции (точение/фрезерование), станка (P_machine, Tmax, n_max, K_machine_base), установки (K_mount), вибрации (K_vib), опыта оператора (K_operator), ограничений (Pc, n, M ≤ Tmax), ap_crit, K_system, **режима работы** (AGGRESSIVE / NORMAL / SAFE), **зон оборотов** (bad zone → смещение n на ±15%). В результат входят: **запас мощности** P_reserve_ratio (предупреждение < 20%, критично < 10%), **требуемый момент** M_required (предупреждение > 0.8·Tmax), **индекс риска вибрации** RiskIndex = (L/D)·(ap/D)·(1/K_system) (high > 2, very_high > 3).

Типы: **ToolParams**, **MaterialParams**, **OperatorParams**, результат **EngineeringResult** (включая power_reserve_ratio, m_required_nm, vibration_risk_index, vibration_risk_level, warnings). **build_engineering_report(result, p_machine_kw, t_max_nm)** формирует структурированный **EngineeringReport** (требуемая мощность, запас %, момент, индекс риска, тип проблемы вибрации, итоговые режимы, предупреждения).

Коэффициенты (доля мощности 0.75, C_machine для ap_crit и др.) хранятся в БД в таблице **calculation_coefficients** и подставляются при передаче `db_session`. Уровни оператора — в **operator_levels** (новичок 0.75, средний 0.9, опытный 1.0, эксперт 1.1).

## 4. Выбор оптимального станка

Модуль: `app/services/machine_selector.py`.

- **select_best_machine(instances, operation_requirements, kind_filter=True, top_n=5)**  
  Возвращает список кортежей `(instance, total_score, score_breakdown)`.

**Классический скоринг** (по умолчанию): запас по мощности, запас по крутящему моменту, K_total, стабильность при L/D > 4, минимизация вибрации. Веса: power 25%, torque 20%, rigidity 25%, ld_stability 15%, vibration 15%.

**Инженерная формула Score** (ТЗ): задайте в **OperationRequirements** поля `power_required_kw` (Pc), `torque_required_nm` (M_required), `ld_ratio` и `use_engineering_score=True`. Тогда:

- **Score** = 0.3·(P_reserve / P_required) + 0.3·K_system + 0.2·(Tmax / M_required) + 0.2·Stability_index  
- P_reserve = P_machine − Pc  
- Stability_index = min(1, K_system · 3 / max(3, L/D))

Выбирается станок с **максимальным Score**.

Требования к операции: **OperationRequirements** (power_kw_min, torque_nm_min, max_rpm_min, machine_kind, ld_ratio, vibration_sensitive, preferred_k_total_min; для инж. формулы: power_required_kw, torque_required_nm, use_engineering_score).

## 5. Пример

- SQL-запрос выбора лучшего станка по представлению: `app/storage/examples_machine_library.py` → `example_sql_select_best_machine()`.
- Полный пример на Python (создание тестовых данных, расчёт режимов, выбор станка): `example_python_usage()` в том же файле. Запуск: `python -m app.storage.examples_machine_library`.

Для работы с PostgreSQL нужна строка подключения и выполнение `schema_machines_postgres.sql`; зависимости: `psycopg2-binary` или `asyncpg` при необходимости.

## 6. Автообучение по истории станка

Модуль: `app/services/machine_learning_service.py`.

Система запоминает каждый запуск обработки (режимы, вибрация, результат), анализирует успешность и постепенно корректирует коэффициенты станка (K_machine_real, ap_crit_real, SAFE_ZONES).

- **StabilityIndex** = 1 − (V_rms / V_limit). Если > 0.8 — режим стабильный; если < 0.5 — нестабильный. V_limit задаётся в `calculation_coefficients` (ключ `vibration_limit_mm_s`, по умолчанию 5 мм/с).
- **record_operation(session, record)** — сохранить одну операцию в `machine_operation_history` (OperationRecord: machine_instance_id, tool, material, D, L, z, n, Vc, f, ap, ae, vibration_rms, peak_frequency, power_kw, result, operator_level).
- **update_machine_learning(session, machine_instance_id, history_limit=500)** — пересчёт обученных параметров: при нестабильных/chatter — снижение K_machine_real (×0.97/×0.95), при стабильных — повышение (×1.02); ограничение K в [0.6, 1.2]; построение SAFE_ZONES по диапазонам оборотов; коррекция ap_crit_real.
- **get_safe_zones(session, machine_instance_id)** — список безопасных диапазонов оборотов.
- **predict_stability(session, machine_instance_id, modes)** — оценка стабильности режимов (rpm, ap_mm, …): predicted_stable, stability_index_estimate, in_safe_zone, recommendations.

Инженерный расчёт при наличии `db_session` и `machine_instance.id` подставляет обученные **k_machine_real** и **ap_crit_real** из `machine_learned_params`. Коэффициент **k_increase_stable** (по умолчанию 1.01) задаётся в `calculation_coefficients` для авто-адаптации при StabilityIndex > 0.8.

Цепочка: расчёт режимов → запуск обработки → запись результата и вибрации в историю → вызов **update_machine_learning** → следующий расчёт использует уточнённые коэффициенты.

## 7. Анализ вибрации по введённой частоте

Модуль: `app/services/vibration_analyzer.py`.

- **analyze_vibration(f_measured_hz, rpm, teeth_count=1, ap_mm, feed_mm_rev, f_safe_hz=None, tolerance=None, db_session=None)** — анализ без фото. f_spindle = n/60, f_tooth = f_spindle·z. Если |f_measured − f_tooth| < 5% → tooth_excitation; если |f_measured − f_spindle| < 5% → imbalance; иначе structural_resonance. Коррекция: resonance → n×0.85, ap×0.7; tooth_excitation → n = (f_safe×60)/z; imbalance → n×0.9. Возвращает **VibrationAnalysisResult** (problem_type, new_rpm, new_ap_mm, new_feed_mm_rev, recommendations).
- **analyze_vibration_from_image(...)** — то же по фото спектра (OCR частоты).

## 8. Точки входа (архитектура)

- **calculate_optimal_modes** — `app/services/engineering_calculator.py`
- **analyze_vibration** / **analyze_vibration_from_image** — `app/services/vibration_analyzer.py`
- **update_machine_learning** — `app/services/machine_learning_service.py`
- **select_best_machine** — `app/services/machine_selector.py`

Все пороговые коэффициенты хранятся в БД (`calculation_coefficients`). Защита от выхода за пределы мощности, момента и оборотов встроена в расчёт.
