"""
ORM модели для базы данных.
Теперь с акцентом на сбор РЕШЕНИЙ операторов для обучения ИИ.
Версия с поддержкой цепочки операций (черновая → получистовая → чистовая).
"""
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, JSON, Boolean, Enum, Table, \
    ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, backref, declarative_base
from sqlalchemy.sql import func
from datetime import datetime
import json
from typing import Optional, Dict, Any, List
from enum import Enum as PyEnum

Base = declarative_base()
Base.__allow_unmapped__ = True  # allow legacy relationship annotations (List[...] etc.)


# ============================================================================
# ПЕРЕЧИСЛЕНИЯ
# ============================================================================

class OperationType(PyEnum):
    """Типы операций для цепочки."""
    ROUGHING = "roughing"  # черновая
    SEMI_FINISHING = "semi_finishing"  # получистовая
    FINISHING = "finishing"  # чистовая
    FINISHING_HIGH_QUALITY = "finishing_high_quality"  # высококачественная чистовая


class ComparisonChoice(PyEnum):
    """Варианты сравнения с рекомендацией."""
    LOWER = "lower"  # ниже рекомендации
    SAME = "same"  # так же как рекомендация
    HIGHER = "higher"  # выше рекомендации
    CUSTOM = "custom"  # уникальное решение
    MIXED = "mixed"  # смешанное (в цепочке разные варианты)


class ResultType(PyEnum):
    """Результаты операции."""
    OK = "ok"  # успешно
    CHATTER = "chatter"  # вибрации
    TOOL_WEAR = "tool_wear"  # износ инструмента
    BREAKAGE = "breakage"  # поломка инструмента
    SURFACE_ISSUE = "surface_issue"  # проблемы с поверхностью
    DIMENSIONAL_ERROR = "dimensional_error"  # отклонение размеров


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ТАБЛИЦЫ ДЛЯ ЦЕПОЧЕК
# ============================================================================

class OperationStep(Base):
    """Один шаг в цепочке операций."""
    __tablename__ = 'operation_steps'

    id = Column(Integer, primary_key=True)
    step_order = Column(Integer, nullable=False)  # порядковый номер в цепочке
    operation_type = Column(String, nullable=False)  # roughing, semi_finishing, finishing

    # Параметры для этого шага
    target_diameter_mm = Column(Float)  # целевой диаметр после этого шага
    stock_to_remove_mm = Column(Float)  # припуск на удаление

    # Рекомендуемые параметры бота для этого шага
    bot_vc_m_min = Column(Float)  # скорость резания
    bot_rpm = Column(Float)  # обороты
    bot_feed_mm_rev = Column(Float)  # подача
    bot_ap_mm = Column(Float)  # глубина резания
    bot_passes = Column(Integer)  # количество проходов

    # Фактические параметры оператора для этого шага
    user_rpm = Column(Float)
    user_feed_mm_rev = Column(Float)
    user_ap_mm = Column(Float)
    user_passes = Column(Integer)

    # Сравнение
    comparison_choice = Column(String)  # lower, same, higher, custom

    # Внешний ключ на родительскую запись
    decision_id = Column(String, ForeignKey('user_decisions.id'))

    # Отношения
    decision = relationship("UserDecision", back_populates="operation_steps")


class PassStrategyDetail(Base):
    """Детали стратегии проходов для шага операции."""
    __tablename__ = 'pass_strategy_details'

    id = Column(Integer, primary_key=True)
    operation_step_id = Column(Integer, ForeignKey('operation_steps.id'))
    pass_number = Column(Integer)  # номер прохода
    pass_type = Column(String)  # roughing, semi_finishing, finishing

    # Геометрия
    diameter_before_mm = Column(Float)
    diameter_after_mm = Column(Float)
    ap_mm = Column(Float)  # глубина резания

    # Параметры
    vc_m_min = Column(Float)
    feed_mm_rev = Column(Float)
    rpm = Column(Float)

    # Отношения
    operation_step = relationship("OperationStep", back_populates="pass_details")


# Добавляем обратные связи
OperationStep.pass_details = relationship("PassStrategyDetail", back_populates="operation_step",
                                          cascade="all, delete-orphan")


# ============================================================================
# СТАРЫЕ ТАБЛИЦЫ (сохраняем для обратной совместимости)
# ============================================================================

class Interaction(Base):
    """Старая модель взаимодействия (для обратной совместимости)."""
    __tablename__ = 'interactions'

    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Контекст
    material = Column(String, nullable=False)
    operation = Column(String, nullable=False)
    mode = Column(String, nullable=False)
    diameter = Column(Float, nullable=False)

    # Рекомендации
    recommended_vc = Column(Float)
    recommended_rpm = Column(Float)
    recommended_feed = Column(Float)

    # Действие пользователя
    user_rpm = Column(Float)
    user_feed = Column(Float)

    # Результаты
    deviation_score = Column(Float)
    decision_quality = Column(Integer)  # будет заполняться позже

    # Контекст
    context_json = Column(Text, default='{}')

    # Метаданные
    source = Column(String, default='telegram')
    session_id = Column(String)

    @property
    def context(self):
        return json.loads(self.context_json) if self.context_json else {}

    @context.setter
    def context(self, value):
        self.context_json = json.dumps(value, ensure_ascii=False)

    def to_dict(self):
        """Преобразовать в словарь."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'material': self.material,
            'operation': self.operation,
            'mode': self.mode,
            'diameter': self.diameter,
            'recommended_vc': self.recommended_vc,
            'recommended_rpm': self.recommended_rpm,
            'recommended_feed': self.recommended_feed,
            'user_rpm': self.user_rpm,
            'user_feed': self.user_feed,
            'deviation_score': self.deviation_score,
            'decision_quality': self.decision_quality,
            'context': self.context,
            'source': self.source,
            'session_id': self.session_id
        }


class UserMetadata(Base):
    """Метаданные пользователя (старая версия)."""
    __tablename__ = 'user_metadata'

    user_id = Column(String, primary_key=True)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    total_interactions = Column(Integer, default=0)
    inferred_machine_type = Column(String)
    preferences_json = Column(Text, default='{}')
    consistency_score = Column(Float)

    @property
    def preferences(self):
        return json.loads(self.preferences_json) if self.preferences_json else {}

    @preferences.setter
    def preferences(self, value):
        self.preferences_json = json.dumps(value, ensure_ascii=False)


class Feedback(Base):
    """Обратная связь по результатам обработки (старая версия)."""
    __tablename__ = 'feedback'

    id = Column(Integer, primary_key=True)
    interaction_id = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Обратная связь от пользователя
    vibration_level = Column(Integer)  # 1-5
    surface_quality = Column(Integer)  # 1-5
    tool_wear_observed = Column(Integer)  # 1-5

    # Системная оценка
    success_metric = Column(Float)


# ============================================================================
# НОВЫЕ ТАБЛИЦЫ (для сбора решений операторов) - ОБНОВЛЕННЫЕ
# ============================================================================

class MachineRecord(Base):
    """Запись о станке."""
    __tablename__ = 'machines'

    id = Column(Integer, primary_key=True)
    machine_type = Column(String, nullable=False)  # cnc_lathe, manual_lathe, milling, etc.
    machine_model = Column(String)
    machine_power_kw = Column(Float, default=15.0)
    max_rpm = Column(Float)
    manufacturer = Column(String)

    # Физические ограничения
    max_cutting_depth_mm = Column(Float)
    max_tool_overhang_mm = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MaterialRecord(Base):
    """Запись о материале."""
    __tablename__ = 'materials'

    id = Column(Integer, primary_key=True)
    material_type = Column(String, nullable=False)  # steel, aluminum, stainless_steel, etc.
    material_grade = Column(String)
    hardness_hb = Column(Float)
    tensile_strength_mpa = Column(Float)
    is_heat_treated = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)


class ToolRecord(Base):
    """Запись об инструменте."""
    __tablename__ = 'tools'

    id = Column(Integer, primary_key=True)
    tool_type = Column(String, nullable=False)  # turning_80, turning_55, milling, etc.
    insert_material = Column(String, nullable=False)  # carbide, hss, ceramic, etc.
    insert_grade = Column(String)
    insert_radius_mm = Column(Float, default=0.8)
    tool_overhang_mm = Column(Float, default=30.0)
    tool_holder_type = Column(String)
    is_coolant_used = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class UserDecision(Base):
    """
    ОСНОВНАЯ ТАБЛИЦА - решение оператора.
    ОБНОВЛЕНА: Поддержка цепочки операций.
    """
    __tablename__ = 'user_decisions'

    id = Column(String, primary_key=True)  # decision_20241215_123456_abc123
    user_id = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Внешние ключи (опционально, можно хранить и как JSON)
    machine_id = Column(Integer, nullable=True)
    material_id = Column(Integer, nullable=True)
    tool_id = Column(Integer, nullable=True)

    # Геометрия обработки
    diameter_start_mm = Column(Float, nullable=False)
    diameter_end_mm = Column(Float, nullable=False)
    length_mm = Column(Float, nullable=False)

    # ЦЕПОЧКА ОПЕРАЦИЙ (новое поле)
    operation_chain_json = Column(Text, default='[]')  # JSON список типов операций

    # Для обратной совместимости (старое поле)
    operation_type = Column(String, nullable=True)  # DEPRECATED: используем operation_chain_json

    # Общие параметры (для простых случаев)
    is_external = Column(Boolean, default=True)
    tolerance_mm = Column(Float)
    surface_roughness_ra = Column(Float)

    # Сводные рекомендации бота (средние по цепочке)
    bot_vc_m_min = Column(Float)  # скорость резания, м/мин
    bot_rpm = Column(Float)  # обороты шпинделя
    bot_feed_mm_rev = Column(Float)  # подача на оборот, мм/об
    bot_ap_mm = Column(Float)  # глубина резания, мм
    bot_power_kw = Column(Float)  # расчетная мощность

    # Стратегия проходов (JSON)
    passes_strategy_json = Column(Text, default='{}')
    total_passes = Column(Integer)

    # Сводные фактические параметры оператора
    user_rpm = Column(Float, nullable=False)
    user_feed_mm_rev = Column(Float, nullable=False)
    user_ap_mm = Column(Float, nullable=False)

    # Как пользователь отнесся к рекомендации
    comparison_choice = Column(String)  # lower, same, higher, custom, mixed
    user_comment = Column(Text)

    # Коэффициенты сравнения
    diff_coeff_rpm = Column(Float)  # user_rpm / bot_rpm
    diff_coeff_feed = Column(Float)  # user_feed / bot_feed
    diff_coeff_ap = Column(Float)  # user_ap / bot_ap

    # Результат операции (заполняется ПОСЛЕ)
    result_type = Column(String)  # ok, chatter, tool_wear, breakage, etc.
    result_details = Column(Text)
    tool_life_minutes = Column(Float)
    actual_machining_time_min = Column(Float)

    # Метаданные для анализа
    experience_level = Column(String, default='unknown')  # beginner, intermediate, expert, unknown
    variance_adaptation_score = Column(Float, default=0.0)
    was_decision_adaptive = Column(Boolean, default=False)

    # Полные JSON данные (для резервного копирования и анализа)
    full_context_json = Column(Text, default='{}')

    # Метаданные сессии
    source = Column(String, default='telegram')
    session_id = Column(String)

    # Отношения для цепочки операций
    operation_steps = relationship("OperationStep", back_populates="decision", cascade="all, delete-orphan")

    @property
    def operation_chain(self):
        """Цепочка операций как список."""
        if self.operation_chain_json:
            return json.loads(self.operation_chain_json)
        # Для обратной совместимости
        if self.operation_type:
            return [self.operation_type]
        return []

    @operation_chain.setter
    def operation_chain(self, value):
        self.operation_chain_json = json.dumps(value, ensure_ascii=False)

    @property
    def passes_strategy(self):
        return json.loads(self.passes_strategy_json) if self.passes_strategy_json else {}

    @passes_strategy.setter
    def passes_strategy(self, value):
        self.passes_strategy_json = json.dumps(value, ensure_ascii=False)

    @property
    def full_context(self):
        return json.loads(self.full_context_json) if self.full_context_json else {}

    @full_context.setter
    def full_context(self, value):
        self.full_context_json = json.dumps(value, ensure_ascii=False)

    @property
    def total_stock_mm(self):
        """Припуск на сторону, мм."""
        return (self.diameter_start_mm - self.diameter_end_mm) / 2

    @property
    def has_operation_chain(self):
        """Есть ли цепочка операций (более 1 операции)."""
        return len(self.operation_chain) > 1

    @property
    def primary_operation_type(self):
        """Основной тип операции (первая в цепочке или единственная)."""
        if self.operation_chain:
            return self.operation_chain[0]
        return self.operation_type or 'roughing'

    def get_operation_chain_description(self) -> str:
        """Описание цепочки операций для отображения."""
        if not self.operation_chain:
            return "одна операция"

        chain_names = {
            'roughing': 'черновая',
            'semi_finishing': 'получистовая',
            'finishing': 'чистовая',
            'finishing_high_quality': 'высококачественная чистовая'
        }

        descriptions = [chain_names.get(op, op) for op in self.operation_chain]

        if len(descriptions) == 1:
            return descriptions[0]
        elif len(descriptions) == 2:
            return f"{descriptions[0]} → {descriptions[1]}"
        else:
            return f"{descriptions[0]} → ... → {descriptions[-1]}"

    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь (как в domain/models.py)."""
        # Собираем данные по шагам операций
        operation_steps_data = []
        for step in sorted(self.operation_steps, key=lambda s: s.step_order):
            step_data = {
                'step_order': step.step_order,
                'operation_type': step.operation_type,
                'target_diameter_mm': step.target_diameter_mm,
                'stock_to_remove_mm': step.stock_to_remove_mm,
                'bot_recommendation': {
                    'vc_m_min': step.bot_vc_m_min,
                    'rpm': step.bot_rpm,
                    'feed_mm_rev': step.bot_feed_mm_rev,
                    'ap_mm': step.bot_ap_mm,
                    'passes': step.bot_passes
                },
                'user_actual': {
                    'rpm': step.user_rpm,
                    'feed_mm_rev': step.user_feed_mm_rev,
                    'ap_mm': step.user_ap_mm,
                    'passes': step.user_passes
                },
                'comparison_choice': step.comparison_choice,
                'pass_details': [
                    {
                        'pass_number': pd.pass_number,
                        'pass_type': pd.pass_type,
                        'diameter_before_mm': pd.diameter_before_mm,
                        'diameter_after_mm': pd.diameter_after_mm,
                        'ap_mm': pd.ap_mm,
                        'vc_m_min': pd.vc_m_min,
                        'feed_mm_rev': pd.feed_mm_rev,
                        'rpm': pd.rpm
                    }
                    for pd in sorted(step.pass_details, key=lambda pd: pd.pass_number)
                ]
            }
            operation_steps_data.append(step_data)

        result = {
            'record_id': self.id,
            'user_id': self.user_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,

            # Геометрия
            'geometry': {
                'diameter_start_mm': self.diameter_start_mm,
                'diameter_end_mm': self.diameter_end_mm,
                'length_mm': self.length_mm,
                'total_stock_mm': self.total_stock_mm
            },

            # Цепочка операций
            'operation_chain': {
                'chain': self.operation_chain,
                'description': self.get_operation_chain_description(),
                'has_chain': self.has_operation_chain,
                'primary_operation': self.primary_operation_type,
                'steps': operation_steps_data
            },

            # Общие параметры операции
            'operation': {
                'operation_type': self.primary_operation_type,  # для обратной совместимости
                'operation_chain': self.operation_chain,  # новая версия
                'is_external': self.is_external,
                'tolerance_mm': self.tolerance_mm,
                'surface_roughness_ra': self.surface_roughness_ra
            },

            # Сводная рекомендация бота
            'bot_recommendation': {
                'vc': self.bot_vc_m_min,
                'rpm': self.bot_rpm,
                'feed': self.bot_feed_mm_rev,
                'ap': self.bot_ap_mm,
                'power_kw': self.bot_power_kw,
                'passes_strategy': self.passes_strategy,
                'total_passes': self.total_passes
            },

            # Сводные фактические параметры
            'user_actual': {
                'rpm': self.user_rpm,
                'feed': self.user_feed_mm_rev,
                'ap': self.user_ap_mm,
                'comparison_choice': self.comparison_choice,
                'user_comment': self.user_comment
            },

            # Коэффициенты различий
            'difference_coeff': {
                'rpm': self.diff_coeff_rpm,
                'feed': self.diff_coeff_feed,
                'ap': self.diff_coeff_ap
            },

            # Результат
            'operation_result': {
                'result_type': self.result_type,
                'result_details': self.result_details,
                'tool_life_minutes': self.tool_life_minutes,
                'actual_machining_time_min': self.actual_machining_time_min
            } if self.result_type else None,

            # Метаданные
            'experience_level': self.experience_level,
            'variance_adaptation_score': self.variance_adaptation_score,
            'was_decision_adaptive': self.was_decision_adaptive,
            'source': self.source,
            'session_id': self.session_id,
            'full_context': self.full_context
        }

        return result


class ExperienceProfile(Base):
    """Профиль опыта оператора (динамически обновляемый)."""
    __tablename__ = 'experience_profiles'

    user_id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Статистика
    total_decisions = Column(Integer, default=0)
    adaptive_decisions = Column(Integer, default=0)

    # Статистика по цепочкам операций
    chain_operation_count = Column(Integer, default=0)  # количество решений с цепочками
    avg_chain_length = Column(Float, default=1.0)  # средняя длина цепочки

    # Средние коэффициенты предпочтений
    avg_rpm_coeff = Column(Float, default=1.0)
    avg_feed_coeff = Column(Float, default=1.0)
    avg_ap_coeff = Column(Float, default=1.0)

    # Оценки адаптивности (0-1)
    material_adaptation_score = Column(Float, default=0.0)
    diameter_adaptation_score = Column(Float, default=0.0)
    operation_adaptation_score = Column(Float, default=0.0)
    chain_adaptation_score = Column(Float, default=0.0)  # адаптивность к цепочкам

    # Профиль рисков
    risk_tolerance = Column(Float, default=0.5)  # 0-1, где 0 - консервативный, 1 - агрессивный
    preferred_aggressiveness = Column(Float, default=0.5)  # 0-1

    # Предпочтения по цепочкам операций
    preferred_chain_pattern_json = Column(Text, default='{}')

    @property
    def preferred_chain_pattern(self):
        return json.loads(self.preferred_chain_pattern_json) if self.preferred_chain_pattern_json else {}

    @preferred_chain_pattern.setter
    def preferred_chain_pattern(self, value):
        self.preferred_chain_pattern_json = json.dumps(value, ensure_ascii=False)

    @property
    def overall_experience_score(self) -> float:
        """Общая оценка опыта (0-100)."""
        # Защита от None значений
        material_score = self.material_adaptation_score or 0.0
        diameter_score = self.diameter_adaptation_score or 0.0
        operation_score = self.operation_adaptation_score or 0.0
        chain_score = self.chain_adaptation_score or 0.0
        
        adaptation = (material_score + diameter_score + operation_score + chain_score) / 4

        total_decisions = self.total_decisions or 0
        volume_score = min(total_decisions / 50, 1.0)

        return (adaptation * 0.7 + volume_score * 0.3) * 100


class ToolLibrary(Base):
    """Библиотека инструментов (справочник)."""
    __tablename__ = 'tool_library'

    id = Column(Integer, primary_key=True)
    tool_type = Column(String, nullable=False)
    manufacturer = Column(String)
    model = Column(String)

    # Рекомендуемые параметры для разных материалов
    recommended_params_json = Column(Text, default='{}')

    # Ограничения
    max_depth_of_cut_mm = Column(Float)
    max_feed_mm_rev = Column(Float)
    recommended_overhang_mm = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def recommended_params(self):
        return json.loads(self.recommended_params_json) if self.recommended_params_json else {}

    @recommended_params.setter
    def recommended_params(self, value):
        self.recommended_params_json = json.dumps(value, ensure_ascii=False)


class MaterialLibrary(Base):
    """Библиотека материалов (справочник)."""
    __tablename__ = 'material_library'

    id = Column(Integer, primary_key=True)
    material_type = Column(String, nullable=False)
    material_grade = Column(String, nullable=False)

    # Характеристики
    hardness_hb_min = Column(Float)
    hardness_hb_max = Column(Float)
    tensile_strength_min_mpa = Column(Float)
    tensile_strength_max_mpa = Column(Float)

    # Рекомендуемые скорости резания для разных операций
    turning_speeds_json = Column(Text, default='{}')
    milling_speeds_json = Column(Text, default='{}')

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def turning_speeds(self):
        return json.loads(self.turning_speeds_json) if self.turning_speeds_json else {}

    @turning_speeds.setter
    def turning_speeds(self, value):
        self.turning_speeds_json = json.dumps(value, ensure_ascii=False)

    @property
    def milling_speeds(self):
        return json.loads(self.milling_speeds_json) if self.milling_speeds_json else {}

    @milling_speeds.setter
    def milling_speeds(self, value):
        self.milling_speeds_json = json.dumps(value, ensure_ascii=False)


# ============================================================================
# УТИЛИТЫ ДЛЯ РАБОТЫ С БАЗОЙ (ОБНОВЛЕННЫЕ)
# ============================================================================

def create_decision_id() -> str:
    """Создание уникального ID для записи решения."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    import uuid
    unique = str(uuid.uuid4())[:8]
    return f"decision_{timestamp}_{unique}"


def save_user_decision(
        session,
        user_id: str,
        geometry: Dict[str, float],
        operation: Dict[str, Any],
        bot_recommendation: Dict[str, Any],
        user_actual: Dict[str, Any],
        comparison_choice: str,
        source: str = "telegram",
        session_id: Optional[str] = None,
        full_context: Optional[Dict] = None,
        operation_chain: Optional[List[str]] = None,
        operation_steps: Optional[List[Dict[str, Any]]] = None
) -> UserDecision:
    """
    Сохранить решение оператора в базу данных.
    ОБНОВЛЕНО: Поддержка цепочек операций.
    """
    # Рассчитываем коэффициенты различий
    bot = bot_recommendation
    user = user_actual

    diff_rpm = user.get('rpm', 0) / bot.get('rpm', 1) if bot.get('rpm') else 1.0
    diff_feed = user.get('feed', 0) / bot.get('feed', 1) if bot.get('feed') else 1.0
    diff_ap = user.get('ap', 0) / bot.get('ap', 1) if bot.get('ap') else 1.0

    # Определяем цепочку операций
    if operation_chain:
        chain = operation_chain
        primary_op = operation_chain[0] if operation_chain else 'roughing'
    else:
        # Для обратной совместимости
        chain = [operation.get('operation_type', 'roughing')]
        primary_op = operation.get('operation_type', 'roughing')

    # Создаем основную запись
    decision = UserDecision(
        id=create_decision_id(),
        user_id=user_id,

        # Геометрия
        diameter_start_mm=geometry.get('diameter_start_mm', 0),
        diameter_end_mm=geometry.get('diameter_end_mm', 0),
        length_mm=geometry.get('length_mm', 0),

        # Цепочка операций
        operation_chain=chain,
        operation_type=primary_op,  # для обратной совместимости

        # Общие параметры
        is_external=operation.get('is_external', True),
        tolerance_mm=operation.get('tolerance_mm'),
        surface_roughness_ra=operation.get('surface_roughness_ra'),

        # Сводные рекомендации бота
        bot_vc_m_min=bot.get('vc'),
        bot_rpm=bot.get('rpm'),
        bot_feed_mm_rev=bot.get('feed'),
        bot_ap_mm=bot.get('ap'),
        bot_power_kw=bot.get('power_kw'),
        passes_strategy=bot.get('passes_strategy', {}),
        total_passes=bot.get('total_passes', 1),

        # Сводные фактические параметры
        user_rpm=user.get('rpm', 0),
        user_feed_mm_rev=user.get('feed', 0),
        user_ap_mm=user.get('ap', 0),

        # Сравнение
        comparison_choice=comparison_choice,
        user_comment=user.get('user_comment'),

        # Коэффициенты
        diff_coeff_rpm=diff_rpm,
        diff_coeff_feed=diff_feed,
        diff_coeff_ap=diff_ap,

        # Метаданные
        source=source,
        session_id=session_id,
        full_context=full_context or {}
    )

    # Сохраняем основную запись
    session.add(decision)
    session.flush()  # Получаем ID

    # Сохраняем шаги операций, если они предоставлены
    if operation_steps:
        for i, step_data in enumerate(operation_steps, 1):
            operation_step = OperationStep(
                step_order=i,
                operation_type=step_data.get('operation_type', 'roughing'),
                target_diameter_mm=step_data.get('target_diameter_mm'),
                stock_to_remove_mm=step_data.get('stock_to_remove_mm'),

                # Рекомендации бота для шага
                bot_vc_m_min=step_data.get('bot_recommendation', {}).get('vc_m_min'),
                bot_rpm=step_data.get('bot_recommendation', {}).get('rpm'),
                bot_feed_mm_rev=step_data.get('bot_recommendation', {}).get('feed_mm_rev'),
                bot_ap_mm=step_data.get('bot_recommendation', {}).get('ap_mm'),
                bot_passes=step_data.get('bot_recommendation', {}).get('passes'),

                # Фактические параметры для шага
                user_rpm=step_data.get('user_actual', {}).get('rpm'),
                user_feed_mm_rev=step_data.get('user_actual', {}).get('feed_mm_rev'),
                user_ap_mm=step_data.get('user_actual', {}).get('ap_mm'),
                user_passes=step_data.get('user_actual', {}).get('passes'),

                comparison_choice=step_data.get('comparison_choice'),
                decision_id=decision.id
            )

            session.add(operation_step)
            session.flush()

            # Сохраняем детали проходов
            pass_details = step_data.get('pass_details', [])
            for pass_detail in pass_details:
                detail = PassStrategyDetail(
                    operation_step_id=operation_step.id,
                    pass_number=pass_detail.get('pass_number'),
                    pass_type=pass_detail.get('pass_type'),
                    diameter_before_mm=pass_detail.get('diameter_before_mm'),
                    diameter_after_mm=pass_detail.get('diameter_after_mm'),
                    ap_mm=pass_detail.get('ap_mm'),
                    vc_m_min=pass_detail.get('vc_m_min'),
                    feed_mm_rev=pass_detail.get('feed_mm_rev'),
                    rpm=pass_detail.get('rpm')
                )
                session.add(detail)

    session.commit()

    # Обновляем профиль опыта
    update_experience_profile(session, user_id, decision, operation_steps)

    return decision


def update_experience_profile(session, user_id: str, decision: UserDecision, operation_steps: Optional[List] = None):
    """Обновить профиль опыта пользователя на основе нового решения."""
    # Ищем существующий профиль или создаем новый
    profile = session.query(ExperienceProfile).filter_by(user_id=user_id).first()
    if not profile:
        profile = ExperienceProfile(user_id=user_id)
        session.add(profile)
    
    # Инициализируем None значения (защита от старых записей в БД)
    if profile.total_decisions is None:
        profile.total_decisions = 0
    if profile.adaptive_decisions is None:
        profile.adaptive_decisions = 0
    if profile.chain_operation_count is None:
        profile.chain_operation_count = 0
    if profile.avg_chain_length is None:
        profile.avg_chain_length = 1.0
    if profile.avg_rpm_coeff is None:
        profile.avg_rpm_coeff = 1.0
    if profile.avg_feed_coeff is None:
        profile.avg_feed_coeff = 1.0
    if profile.avg_ap_coeff is None:
        profile.avg_ap_coeff = 1.0
    if profile.material_adaptation_score is None:
        profile.material_adaptation_score = 0.0
    if profile.diameter_adaptation_score is None:
        profile.diameter_adaptation_score = 0.0
    if profile.operation_adaptation_score is None:
        profile.operation_adaptation_score = 0.0
    if profile.chain_adaptation_score is None:
        profile.chain_adaptation_score = 0.0
    if profile.risk_tolerance is None:
        profile.risk_tolerance = 0.5
    if profile.preferred_aggressiveness is None:
        profile.preferred_aggressiveness = 0.5

    # Обновляем статистику
    profile.total_decisions += 1

    # Обновляем статистику по цепочкам
    if decision.has_operation_chain:
        profile.chain_operation_count += 1
        chain_length = len(decision.operation_chain)
        # Обновляем среднюю длину цепочки
        if profile.avg_chain_length == 1.0:
            profile.avg_chain_length = chain_length
        else:
            profile.avg_chain_length = (profile.avg_chain_length * (profile.chain_operation_count - 1) +
                                        chain_length) / profile.chain_operation_count

    # Обновляем средние коэффициенты (скользящее среднее)
    if decision.diff_coeff_rpm:
        profile.avg_rpm_coeff = (profile.avg_rpm_coeff * (profile.total_decisions - 1) +
                                 decision.diff_coeff_rpm) / profile.total_decisions

    if decision.diff_coeff_feed:
        profile.avg_feed_coeff = (profile.avg_feed_coeff * (profile.total_decisions - 1) +
                                  decision.diff_coeff_feed) / profile.total_decisions

    if decision.diff_coeff_ap:
        profile.avg_ap_coeff = (profile.avg_ap_coeff * (profile.total_decisions - 1) +
                                decision.diff_coeff_ap) / profile.total_decisions

    # Обновляем оценку адаптивности к цепочкам
    if operation_steps and len(operation_steps) > 1:
        # Если оператор успешно работает с цепочками, повышаем оценку
        profile.chain_adaptation_score = min(1.0, profile.chain_adaptation_score + 0.1)

    session.commit()


def get_user_decisions(session, user_id: str, limit: int = 100) -> list:
    """Получить решения пользователя."""
    return (session.query(UserDecision)
            .filter_by(user_id=user_id)
            .order_by(UserDecision.timestamp.desc())
            .limit(limit)
            .all())


def get_decision_with_steps(session, decision_id: str) -> Optional[UserDecision]:
    """Получить решение со всеми шагами операций."""
    return (session.query(UserDecision)
            .filter_by(id=decision_id)
            .options(
        session.query(UserDecision).joinedload(UserDecision.operation_steps)
        .joinedload(OperationStep.pass_details)
    )
            .first())


# ============================================================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С ЦЕПОЧКАМИ ОПЕРАЦИЙ
# ============================================================================

def create_operation_chain_from_text(text: str) -> List[str]:
    """
    Создать цепочку операций из текста пользователя.
    Например: "черновой потом чистовой" → ["roughing", "finishing"]
    """
    text_lower = text.lower()

    # Словарь для распознавания
    operation_keywords = {
        'чернов': 'roughing',
        'грубо': 'roughing',
        'съем': 'roughing',
        'припуск': 'roughing',

        'получист': 'semi_finishing',
        'средн': 'semi_finishing',
        'переход': 'semi_finishing',

        'чистов': 'finishing',
        'чисто': 'finishing',
        'финиш': 'finishing',
        'окончат': 'finishing',
        'отдел': 'finishing'
    }

    # Разделители для цепочек
    separators = ['потом', 'затем', 'далее', 'после', '→', '->', 'и', 'а потом']

    # Ищем операции в тексте
    found_operations = []

    for keyword, operation in operation_keywords.items():
        if keyword in text_lower:
            found_operations.append(operation)

    # Убираем дубликаты, сохраняя порядок
    seen = set()
    unique_operations = []
    for op in found_operations:
        if op not in seen:
            seen.add(op)
            unique_operations.append(op)

    # Если операций не найдено, возвращаем стандартную цепочку
    if not unique_operations:
        # Пытаемся определить по контексту
        if 'припуск' in text_lower or 'снять' in text_lower or 'много' in text_lower:
            # Большой припуск → черновая + чистовая
            return ['roughing', 'finishing']
        elif 'чисто' in text_lower or 'точн' in text_lower or 'шероховат' in text_lower:
            # Акцент на качество → чистовая
            return ['finishing']
        else:
            # По умолчанию → черновая
            return ['roughing']

    # Сортируем по логическому порядку, если нет явных указаний
    operation_order = ['roughing', 'semi_finishing', 'finishing', 'finishing_high_quality']
    sorted_operations = sorted(unique_operations,
                               key=lambda x: operation_order.index(x) if x in operation_order else len(operation_order))

    return sorted_operations


def get_chain_description(chain: List[str]) -> str:
    """Получить описание цепочки операций."""
    descriptions = {
        'roughing': 'черновая',
        'semi_finishing': 'получистовая',
        'finishing': 'чистовая',
        'finishing_high_quality': 'высококачественная чистовая'
    }

    translated = [descriptions.get(op, op) for op in chain]

    if len(translated) == 1:
        return translated[0]
    elif len(translated) == 2:
        return f"{translated[0]} → {translated[1]}"
    else:
        return f"{translated[0]} → ... → {translated[-1]}"


def calculate_chain_statistics(chain: List[str], total_stock_mm: float) -> Dict[str, Any]:
    """
    Рассчитать статистику для цепочки операций.
    """
    if not chain:
        return {}

    # Распределение припуска по операциям
    stock_distribution = {}

    if len(chain) == 1:
        # Одна операция - весь припуск
        stock_distribution[chain[0]] = total_stock_mm
    elif len(chain) == 2:
        # Две операции: черновая 80%, чистовая 20%
        if chain[0] == 'roughing' and chain[1] in ['semi_finishing', 'finishing']:
            stock_distribution[chain[0]] = total_stock_mm * 0.8
            stock_distribution[chain[1]] = total_stock_mm * 0.2
        else:
            # Равномерно
            per_op = total_stock_mm / len(chain)
            for op in chain:
                stock_distribution[op] = per_op
    else:
        # Три и более операций: прогрессивное уменьшение
        base = total_stock_mm / sum(range(1, len(chain) + 1))
        for i, op in enumerate(chain, 1):
            stock_distribution[op] = base * (len(chain) - i + 1)

    # Расчетные параметры для каждой операции
    operation_params = {}
    for op, stock in stock_distribution.items():
        if op == 'roughing':
            operation_params[op] = {
                'target_ap_mm': min(stock / 3, 4.0),  # Средняя глубина
                'typical_feed_mm_rev': 0.2,
                'typical_vc_multiplier': 1.0
            }
        elif op == 'semi_finishing':
            operation_params[op] = {
                'target_ap_mm': min(stock / 2, 1.5),
                'typical_feed_mm_rev': 0.15,
                'typical_vc_multiplier': 1.1
            }
        elif op == 'finishing':
            operation_params[op] = {
                'target_ap_mm': min(stock, 0.8),
                'typical_feed_mm_rev': 0.1,
                'typical_vc_multiplier': 1.2
            }
        elif op == 'finishing_high_quality':
            operation_params[op] = {
                'target_ap_mm': min(stock, 0.3),
                'typical_feed_mm_rev': 0.05,
                'typical_vc_multiplier': 1.3
            }

    return {
        'chain': chain,
        'description': get_chain_description(chain),
        'total_operations': len(chain),
        'stock_distribution': stock_distribution,
        'operation_params': operation_params,
        'estimated_total_passes': sum([max(1, int(stock / operation_params[op]['target_ap_mm']))
                                       for op, stock in stock_distribution.items()])
    }


# ============================================================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ
# ============================================================================

def init_orm_database(db_url: str = "sqlite:///storage/cnc.db"):
    """Инициализация ORM."""
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session


def get_session(db_url: str = "sqlite:///storage/cnc.db"):
    """Получить сессию базы данных."""
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    return Session()


# ============================================================================
# ТЕСТИРОВАНИЕ
# ============================================================================

if __name__ == "__main__":
    print("🧪 Тестирование моделей с поддержкой цепочек операций")
    print("=" * 60)

    # Тестирование создания цепочек
    test_phrases = [
        "черновой потом чистовой",
        "сначала черновая затем чистовая обработка",
        "чистовая отделка",
        "большой припуск, надо снять много материала",
        "черновой, получистовой и потом чистовая"
    ]

    for phrase in test_phrases:
        chain = create_operation_chain_from_text(phrase)
        print(f"📝 '{phrase}' → {chain} ({get_chain_description(chain)})")

    print("\n📊 Тестирование статистики цепочек:")
    chains_to_test = [
        ['roughing', 'finishing'],
        ['roughing', 'semi_finishing', 'finishing'],
        ['finishing'],
        ['roughing', 'finishing_high_quality']
    ]

    for chain in chains_to_test:
        stats = calculate_chain_statistics(chain, 10.0)
        print(f"\nЦепочка: {get_chain_description(chain)}")
        print(f"  Операций: {stats['total_operations']}")
        print(f"  Распределение припуска: {stats['stock_distribution']}")
        print(f"  Оценочное количество проходов: {stats['estimated_total_passes']}")

    print("\n✅ Модели обновлены для поддержки цепочек операций!")
    print("   • Добавлены таблицы OperationStep и PassStrategyDetail")
    print("   • Обновлена UserDecision для хранения цепочек")
    print("   • Обновлены функции сохранения с поддержкой цепочек")
    print("   • Добавлены утилиты для работы с цепочками")
    print("   • Сохранена обратная совместимость")