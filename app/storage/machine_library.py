"""
ORM-модели библиотеки станков (PostgreSQL).
Модель станка → экземпляр с учётом монтажа и жёсткости.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, Boolean,
    ForeignKey, Numeric, Index, CheckConstraint, Enum,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.storage.models import Base

if TYPE_CHECKING:
    from sqlalchemy.orm import Mapped


# -----------------------------------------------------------------------------
# Перечисления (для совместимости с SQLite используем String в БД)
# -----------------------------------------------------------------------------

class MachineKind(str, PyEnum):
    TURNING = "turning"
    MILLING = "milling"
    BORING = "boring"
    DRILLING = "drilling"


class FoundationType(str, PyEnum):
    CONCRETE = "concrete"
    SLAB = "slab"
    FRAME = "frame"
    FLOATING_SLAB = "floating_slab"


class AnchoringType(str, PyEnum):
    RIGID = "rigid"
    SOFT = "soft"
    NONE = "none"


# -----------------------------------------------------------------------------
# Модель станка (каталог)
# -----------------------------------------------------------------------------

class MachineModel(Base):
    """
    Базовая модель станка: мощность, обороты, момент, масса, тип,
    базовый коэффициент жёсткости шпиндельного узла.
    """
    __tablename__ = "machine_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    manufacturer = Column(String(255))
    machine_kind = Column(String(20), nullable=False)  # turning, milling, ...

    power_kw = Column(Numeric(10, 2), nullable=False)
    max_rpm = Column(Integer, nullable=False)
    torque_nm = Column(Numeric(12, 2))
    mass_kg = Column(Numeric(10, 2))

    spindle_rigidity_base = Column(
        Numeric(5, 3), nullable=False, default=Decimal("1.0")
    )  # 0.3..1.5

    max_cutting_force_n = Column(Numeric(12, 2))
    max_tool_overhang_mm = Column(Numeric(8, 2))

    created_at = Column(DateTime(True), server_default=func.now())
    updated_at = Column(DateTime(True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "spindle_rigidity_base >= 0.3 AND spindle_rigidity_base <= 1.5",
            name="ck_machine_models_spindle_rigidity",
        ),
        Index("idx_machine_models_kind", "machine_kind"),
        Index("idx_machine_models_power", "power_kw"),
    )

    instances: "List[MachineInstance]" = relationship(
        "MachineInstance", back_populates="model", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<MachineModel(id={self.id}, name={self.name!r}, kind={self.machine_kind})>"


# -----------------------------------------------------------------------------
# Монтаж (фундамент, анкеровка, виброопоры)
# -----------------------------------------------------------------------------

class MachineMounting(Base):
    """Тип фундамента, анкеровка, виброизоляция, коэффициент жёсткости установки."""
    __tablename__ = "machine_mounting"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255))

    foundation = Column(String(30), nullable=False)  # concrete, slab, frame, floating_slab
    anchoring = Column(String(20), nullable=False)  # rigid, soft, none
    has_vibration_pads = Column(Boolean, nullable=False, default=False)

    mounting_stiffness_coeff = Column(
        Numeric(4, 2), nullable=False, default=Decimal("1.0")
    )  # 0.5..1.2

    notes = Column(Text)
    created_at = Column(DateTime(True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "mounting_stiffness_coeff >= 0.5 AND mounting_stiffness_coeff <= 1.2",
            name="ck_machine_mounting_stiffness",
        ),
    )

    instances: "List[MachineInstance]" = relationship(
        "MachineInstance", back_populates="mounting", lazy="selectin"
    )


# -----------------------------------------------------------------------------
# Профиль жёсткости/вибрации
# -----------------------------------------------------------------------------

class MachineRigidityProfile(Base):
    """Жёсткость, демпфирование, реальный уровень вибрации (мм/с)."""
    __tablename__ = "machine_rigidity_profile"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255))

    rigidity_coeff = Column(
        Numeric(4, 2), nullable=False, default=Decimal("1.0")
    )  # 0.5..1.2
    damping_ratio = Column(Numeric(5, 4))
    vibration_mm_per_s = Column(Numeric(8, 4))
    vibration_risk = Column(String(20), default="moderate")

    notes = Column(Text)
    created_at = Column(DateTime(True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "rigidity_coeff >= 0.5 AND rigidity_coeff <= 1.2",
            name="ck_machine_rigidity_coeff",
        ),
    )

    instances: "List[MachineInstance]" = relationship(
        "MachineInstance", back_populates="rigidity_profile", lazy="selectin"
    )


# -----------------------------------------------------------------------------
# Экземпляр станка (установленный станок)
# -----------------------------------------------------------------------------

class MachineInstance(Base):
    """
    Конкретный установленный станок: ссылка на модель + опционально
    монтаж и профиль жёсткости. Один и тот же модельный станок может
    вести себя по-разному в зависимости от установки.
    """
    __tablename__ = "machine_instances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("machine_models.id", ondelete="RESTRICT"), nullable=False)
    instance_name = Column(String(255), nullable=False)

    mounting_id = Column(Integer, ForeignKey("machine_mounting.id", ondelete="SET NULL"))
    rigidity_profile_id = Column(Integer, ForeignKey("machine_rigidity_profile.id", ondelete="SET NULL"))

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(True), server_default=func.now())
    updated_at = Column(DateTime(True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("idx_machine_instances_model", "model_id"),)

    model = relationship("MachineModel", back_populates="instances")
    mounting = relationship("MachineMounting", back_populates="instances")
    rigidity_profile = relationship("MachineRigidityProfile", back_populates="instances")

    def get_k_total(self) -> float:
        """
        Итоговый коэффициент жёсткости установки:
        K_total = K_machine_base × K_mounting × K_rigidity
        """
        k_base = float(self.model.spindle_rigidity_base)
        k_mount = float(self.mounting.mounting_stiffness_coeff) if self.mounting else 1.0
        k_rig = float(self.rigidity_profile.rigidity_coeff) if self.rigidity_profile else 1.0
        return round(k_base * k_mount * k_rig, 4)

    def __repr__(self) -> str:
        return f"<MachineInstance(id={self.id}, name={self.instance_name!r})>"


# -----------------------------------------------------------------------------
# Уровень оператора (опыт) — коэффициент для расчёта режимов
# -----------------------------------------------------------------------------

class OperatorLevel(Base):
    """Уровень подготовки оператора: настраиваемый коэффициент K_operator."""
    __tablename__ = "operator_levels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), nullable=False, unique=True)  # novice, medium, experienced, expert
    name = Column(String(100), nullable=False)
    coefficient = Column(Numeric(4, 2), nullable=False, default=Decimal("1.0"))  # 0.75..1.1
    description = Column(Text)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "coefficient >= 0.5 AND coefficient <= 1.2",
            name="ck_operator_level_coeff",
        ),
    )


# -----------------------------------------------------------------------------
# Настраиваемые коэффициенты расчёта (в БД)
# -----------------------------------------------------------------------------

class CalculationCoefficient(Base):
    """Ключ-значение коэффициентов: мощность 0.75, C_machine для ap_crit и т.д."""
    __tablename__ = "calculation_coefficients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(80), nullable=False, unique=True)
    value = Column(Numeric(12, 6), nullable=False)
    category = Column(String(40))  # power_limit, stiffness, vibration, ld, etc.
    description = Column(Text)
    updated_at = Column(DateTime(True), server_default=func.now(), onupdate=func.now())


# -----------------------------------------------------------------------------
# История операций станка (для автообучения)
# -----------------------------------------------------------------------------

class MachineOperationHistory(Base):
    """
    Запись одного запуска обработки: режимы, вибрация, результат.
    Используется для адаптивной коррекции K_machine_real, ap_crit, SAFE_ZONES.
    """
    __tablename__ = "machine_operation_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    machine_instance_id = Column(
        Integer,
        ForeignKey("machine_instances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    tool = Column(String(255))           # описание инструмента
    material = Column(String(255))      # материал заготовки
    diameter_mm = Column(Numeric(10, 3))   # D
    overhang_mm = Column(Numeric(10, 3))   # L
    teeth_count = Column(Integer)      # z

    rpm = Column(Numeric(12, 2))        # n
    vc_m_min = Column(Numeric(10, 2))
    feed_mm_rev = Column(Numeric(8, 4))   # f
    ap_mm = Column(Numeric(8, 4))
    ae_mm = Column(Numeric(8, 4))

    vibration_rms = Column(Numeric(10, 4))   # V_rms, мм/с
    peak_frequency_hz = Column(Numeric(10, 2))
    power_kw = Column(Numeric(8, 3))

    result = Column(String(20), nullable=False)  # stable, chatter, failure, tool_wear
    operator_level = Column(String(20))  # novice, medium, experienced, expert
    created_at = Column(DateTime(True), server_default=func.now())

    __table_args__ = (
        Index("idx_machine_operation_history_instance", "machine_instance_id"),
        Index("idx_machine_operation_history_created", "created_at"),
    )


# -----------------------------------------------------------------------------
# Обученные параметры станка (адаптивная модель)
# -----------------------------------------------------------------------------

class MachineLearnedParams(Base):
    """
    Коэффициенты, уточнённые по истории: K_machine_real, ap_crit_real, SAFE_ZONES.
    Один ряд на экземпляр станка (machine_instance_id UNIQUE).
    """
    __tablename__ = "machine_learned_params"

    id = Column(Integer, primary_key=True, autoincrement=True)
    machine_instance_id = Column(
        Integer,
        ForeignKey("machine_instances.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    k_machine_real = Column(
        Numeric(5, 3),
        nullable=False,
        default=Decimal("1.0"),
    )  # 0.6..1.2
    ap_crit_real = Column(Numeric(12, 6))  # скорректированная критическая глубина (опционально)
    safe_zones_json = Column(Text)          # JSON: [{"rpm_min": 3200, "rpm_max": 3400}, ...]
    vibration_limit_mm_s = Column(Numeric(8, 2))  # V_limit для StabilityIndex (если NULL — из коэффициентов)
    updated_at = Column(DateTime(True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "k_machine_real >= 0.6 AND k_machine_real <= 1.2",
            name="ck_learned_k_machine_real",
        ),
    )


# -----------------------------------------------------------------------------
# Зоны оборотов (нестабильные / безопасные)
# -----------------------------------------------------------------------------

class MachineSpeedZone(Base):
    """
    Диапазон оборотов: bad — нестабильная зона (смещать n на ±15%);
    safe — рекомендуемая зона.
    """
    __tablename__ = "machine_speed_zones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    machine_instance_id = Column(
        Integer,
        ForeignKey("machine_instances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    min_rpm = Column(Numeric(10, 2), nullable=False)
    max_rpm = Column(Numeric(10, 2), nullable=False)
    zone_type = Column(String(10), nullable=False)  # 'bad' | 'safe'
    notes = Column(Text)
    created_at = Column(DateTime(True), server_default=func.now())

    __table_args__ = (
        Index("idx_machine_speed_zones_instance", "machine_instance_id"),
    )
