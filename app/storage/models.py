"""
ORM модели для базы данных.
Теперь с акцентом на сбор РЕШЕНИЙ операторов для обучения ИИ.
"""
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, JSON, Boolean, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
from datetime import datetime
import json
from typing import Optional, Dict, Any

Base = declarative_base()


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
# НОВЫЕ ТАБЛИЦЫ (для сбора решений операторов)
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
    Это "золото" для обучения ИИ.
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

    # Тип операции
    operation_type = Column(String, nullable=False)  # roughing, finishing, semi_finishing, etc.
    is_external = Column(Boolean, default=True)
    tolerance_mm = Column(Float)
    surface_roughness_ra = Column(Float)

    # Рекомендация бота (базовые табличные значения)
    bot_vc_m_min = Column(Float)  # скорость резания, м/мин
    bot_rpm = Column(Float)  # обороты шпинделя
    bot_feed_mm_rev = Column(Float)  # подача на оборот, мм/об
    bot_ap_mm = Column(Float)  # глубина резания, мм
    bot_power_kw = Column(Float)  # расчетная мощность

    # Стратегия проходов (JSON)
    passes_strategy_json = Column(Text, default='{}')
    total_passes = Column(Integer)

    # Фактические параметры оператора
    user_rpm = Column(Float, nullable=False)
    user_feed_mm_rev = Column(Float, nullable=False)
    user_ap_mm = Column(Float, nullable=False)

    # Как пользователь отнесся к рекомендации
    comparison_choice = Column(String)  # lower, same, higher, manual
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

    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь (как в domain/models.py)."""
        return {
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

            # Операция
            'operation': {
                'operation_type': self.operation_type,
                'is_external': self.is_external,
                'tolerance_mm': self.tolerance_mm,
                'surface_roughness_ra': self.surface_roughness_ra
            },

            # Рекомендация бота
            'bot_recommendation': {
                'vc': self.bot_vc_m_min,
                'rpm': self.bot_rpm,
                'feed': self.bot_feed_mm_rev,
                'ap': self.bot_ap_mm,
                'power_kw': self.bot_power_kw,
                'passes_strategy': self.passes_strategy,
                'total_passes': self.total_passes
            },

            # Фактические параметры
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


class ExperienceProfile(Base):
    """Профиль опыта оператора (динамически обновляемый)."""
    __tablename__ = 'experience_profiles'

    user_id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Статистика
    total_decisions = Column(Integer, default=0)
    adaptive_decisions = Column(Integer, default=0)

    # Средние коэффициенты предпочтений
    avg_rpm_coeff = Column(Float, default=1.0)
    avg_feed_coeff = Column(Float, default=1.0)
    avg_ap_coeff = Column(Float, default=1.0)

    # Оценки адаптивности (0-1)
    material_adaptation_score = Column(Float, default=0.0)
    diameter_adaptation_score = Column(Float, default=0.0)
    operation_adaptation_score = Column(Float, default=0.0)

    # Профиль рисков
    risk_tolerance = Column(Float, default=0.5)  # 0-1, где 0 - консервативный, 1 - агрессивный
    preferred_aggressiveness = Column(Float, default=0.5)  # 0-1

    @property
    def overall_experience_score(self) -> float:
        """Общая оценка опыта (0-100)."""
        adaptation = (self.material_adaptation_score +
                      self.diameter_adaptation_score +
                      self.operation_adaptation_score) / 3

        volume_score = min(self.total_decisions / 50, 1.0)

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
# УТИЛИТЫ ДЛЯ РАБОТЫ С БАЗОЙ
# ============================================================================

def create_decision_id() -> str:
    """Создание уникального ID для записи решения."""
    from datetime import datetime
    import uuid
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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
        full_context: Optional[Dict] = None
) -> UserDecision:
    """
    Сохранить решение оператора в базу данных.

    Args:
        session: SQLAlchemy сессия
        user_id: ID пользователя
        geometry: словарь с diameter_start_mm, diameter_end_mm, length_mm
        operation: словарь с operation_type, is_external и др.
        bot_recommendation: словарь с рекомендациями бота
        user_actual: словарь с фактическими параметрами
        comparison_choice: lower, same, higher, manual
        source: источник данных (telegram, cli, web)
        session_id: ID сессии
        full_context: полный контекст для анализа

    Returns:
        Сохраненная запись
    """
    # Рассчитываем коэффициенты различий
    bot = bot_recommendation
    user = user_actual

    diff_rpm = user.get('rpm', 0) / bot.get('rpm', 1) if bot.get('rpm') else 1.0
    diff_feed = user.get('feed', 0) / bot.get('feed', 1) if bot.get('feed') else 1.0
    diff_ap = user.get('ap', 0) / bot.get('ap', 1) if bot.get('ap') else 1.0

    # Создаем запись
    decision = UserDecision(
        id=create_decision_id(),
        user_id=user_id,

        # Геометрия
        diameter_start_mm=geometry.get('diameter_start_mm', 0),
        diameter_end_mm=geometry.get('diameter_end_mm', 0),
        length_mm=geometry.get('length_mm', 0),

        # Операция
        operation_type=operation.get('operation_type', 'roughing'),
        is_external=operation.get('is_external', True),
        tolerance_mm=operation.get('tolerance_mm'),
        surface_roughness_ra=operation.get('surface_roughness_ra'),

        # Рекомендация бота
        bot_vc_m_min=bot.get('vc'),
        bot_rpm=bot.get('rpm'),
        bot_feed_mm_rev=bot.get('feed'),
        bot_ap_mm=bot.get('ap'),
        bot_power_kw=bot.get('power_kw'),
        passes_strategy=bot.get('passes_strategy', {}),
        total_passes=bot.get('total_passes', 1),

        # Фактические параметры
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

    # Сохраняем
    session.add(decision)
    session.commit()

    # Обновляем профиль опыта
    update_experience_profile(session, user_id, decision)

    return decision


def update_experience_profile(session, user_id: str, decision: UserDecision):
    """Обновить профиль опыта пользователя на основе нового решения."""
    # Ищем существующий профиль или создаем новый
    profile = session.query(ExperienceProfile).filter_by(user_id=user_id).first()
    if not profile:
        profile = ExperienceProfile(user_id=user_id)
        session.add(profile)

    # Обновляем статистику
    profile.total_decisions += 1

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

    # TODO: Обновить оценки адаптивности на основе сравнения с предыдущими решениями

    session.commit()


def get_user_decisions(session, user_id: str, limit: int = 100) -> list:
    """Получить решения пользователя."""
    return (session.query(UserDecision)
            .filter_by(user_id=user_id)
            .order_by(UserDecision.timestamp.desc())
            .limit(limit)
            .all())


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