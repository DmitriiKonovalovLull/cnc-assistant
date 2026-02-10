"""
Модели данных для CNC Assistant.
Основные сущности системы.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============= ENUMS =============

class MaterialGroup(Enum):
    """Группы материалов по обрабатываемости"""
    CARBON_STEEL = "carbon_steel"
    ALLOY_STEEL = "alloy_steel"
    STAINLESS_STEEL = "stainless_steel"
    TOOL_STEEL = "tool_steel"
    CAST_IRON = "cast_iron"
    ALUMINUM = "aluminum"
    COPPER = "copper"
    TITANIUM = "titanium"
    HEAT_RESISTANT = "heat_resistant"
    HARD_TO_CUT = "hard_to_cut"
    OTHER = "other"


class MachineType(Enum):
    """Типы токарных станков"""
    CONVENTIONAL = "conventional"
    CNC_TURNING = "cnc_turning"
    SWISS_TYPE = "swiss_type"
    VERTICAL_LATHE = "vertical_lathe"
    MULTI_AXIS = "multi_axis"


class ToolMaterial(Enum):
    """Материал режущей части инструмента"""
    HSS = "hss"
    CARBIDE = "carbide"
    CERAMIC = "ceramic"
    CBN = "cbn"
    DIAMOND = "diamond"
    PCD = "pcd"


class ToolCoating(Enum):
    """Покрытия инструмента"""
    NONE = "none"
    TIN = "tin"
    TIALN = "tialn"
    ALCRN = "alcrn"
    DIAMOND_COATED = "diamond_coated"


class OperationType(Enum):
    """Типы токарных операций"""
    ROUGH_TURNING = "rough_turning"
    FINISH_TURNING = "finish_turning"
    FACING = "facing"
    GROOVING = "grooving"
    THREADING = "threading"
    DRILLING = "drilling"
    BORING = "boring"
    PARTING = "parting"
    KNURLING = "knurling"
    CHAMFERING = "chamfering"


class CuttingMode(Enum):
    """Режимы резания (стратегии)"""
    AGGRESSIVE = "aggressive"
    STANDARD = "standard"
    CONSERVATIVE = "conservative"
    FINISHING = "finishing"
    HARD_MACHINING = "hard_machining"


class SurfaceFinish(Enum):
    """Качество поверхности"""
    ROUGH = "rough"  # Ra > 6.3 μm
    NORMAL = "normal"  # Ra = 3.2-6.3 μm
    FINE = "fine"  # Ra = 1.6-3.2 μm
    VERY_FINE = "very_fine"  # Ra = 0.8-1.6 μm
    MIRROR = "mirror"  # Ra < 0.8 μm


# ============= DOMAIN MODELS =============

@dataclass
class Material:
    """Материал заготовки"""
    id: str = field(default_factory=lambda: f"mat_{datetime.now().timestamp()}")
    name: str
    group: MaterialGroup
    hardness_hb: Optional[float] = None
    tensile_strength: Optional[float] = None
    thermal_conductivity: Optional[float] = None
    normalized_name: Optional[str] = None
    standard: Optional[str] = None
    description: Optional[str] = None
    cutting_speed_range: Optional[Dict[str, float]] = None  # мин-макс скорость резания

    def __post_init__(self):
        if self.cutting_speed_range is None:
            self.cutting_speed_range = self._get_default_speed_range()

    def _get_default_speed_range(self) -> Dict[str, float]:
        """Получить диапазон скоростей по умолчанию для группы материала"""
        ranges = {
            MaterialGroup.CARBON_STEEL: {"min": 100, "max": 300},
            MaterialGroup.STAINLESS_STEEL: {"min": 80, "max": 200},
            MaterialGroup.ALUMINUM: {"min": 200, "max": 500},
            MaterialGroup.TITANIUM: {"min": 30, "max": 80},
            MaterialGroup.CAST_IRON: {"min": 80, "max": 200},
        }
        return ranges.get(self.group, {"min": 50, "max": 200})


@dataclass
class CuttingTool:
    """Режущий инструмент"""
    id: str = field(default_factory=lambda: f"tool_{datetime.now().timestamp()}")
    identifier: str
    type: str
    material: ToolMaterial
    coating: ToolCoating
    geometry: Dict[str, Any]
    manufacturer: Optional[str] = None
    normalized_code: Optional[str] = None
    recommended_params: Dict[str, Any] = field(default_factory=dict)

    @property
    def tool_angle(self) -> float:
        """Угол при вершине инструмента"""
        return self.geometry.get('tool_angle', 80.0)

    @property
    def nose_radius(self) -> float:
        """Радиус при вершине"""
        return self.geometry.get('nose_radius', 0.8)


@dataclass
class Machine:
    """Станок"""
    id: str = field(default_factory=lambda: f"machine_{datetime.now().timestamp()}")
    name: str
    type: MachineType
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    power_kw: Optional[float] = None
    max_rpm: Optional[float] = None
    torque_nm: Optional[float] = None
    chuck_size: Optional[float] = None
    axis_travel: Dict[str, float] = field(default_factory=dict)
    control_system: Optional[str] = None

    def can_handle_power(self, required_power_kw: float) -> bool:
        """Проверка, может ли станок обеспечить требуемую мощность"""
        if self.power_kw is None:
            return True  # Неизвестная мощность, предполагаем что может
        return required_power_kw <= self.power_kw * 0.8  # 80% от номинала


@dataclass
class CuttingParameters:
    """Параметры резания для одной операции"""
    cutting_speed_vc: float  # м/мин
    spindle_speed_n: float  # об/мин
    feed_per_rev_f: float  # мм/об
    feed_per_tooth_fz: Optional[float] = None  # мм/зуб
    depth_of_cut_ap: float  # мм
    width_of_cut_ae: Optional[float] = None  # мм
    material_removal_rate: Optional[float] = None  # см³/мин

    @property
    def is_valid(self) -> bool:
        """Проверка валидности параметров"""
        return all([
            self.cutting_speed_vc > 0,
            self.spindle_speed_n > 0,
            self.feed_per_rev_f > 0,
            self.depth_of_cut_ap > 0
        ])

    def calculate_mrr(self, diameter: float) -> float:
        """Расчет объема снимаемого материала"""
        # MRR = π × D × ap × f × n / 1000
        return (3.14159 * diameter * self.depth_of_cut_ap *
                self.feed_per_rev_f * self.spindle_speed_n) / 1000


@dataclass
class Operation:
    """Токарная операция"""
    id: str = field(default_factory=lambda: f"op_{datetime.now().timestamp()}")
    type: OperationType
    material: Material
    tool: CuttingTool
    machine: Machine
    cutting_params: CuttingParameters
    diameter: float  # мм
    length: Optional[float] = None  # мм
    surface_finish_required: Optional[float] = None  # Ra
    operation_notes: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_finishing(self) -> bool:
        """Является ли операция чистовой"""
        return self.type in [OperationType.FINISH_TURNING, OperationType.FACING]

    @property
    def is_roughing(self) -> bool:
        """Является ли операция черновой"""
        return self.type == OperationType.ROUGH_TURNING


@dataclass
class ProcessPlan:
    """Технологический процесс"""
    id: str = field(default_factory=lambda: f"plan_{datetime.now().timestamp()}")
    operations: List[Operation]
    total_machining_time: Optional[float] = None
    total_material_removed: Optional[float] = None
    plan_notes: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)

    def add_operation(self, operation: Operation):
        """Добавить операцию к процессу"""
        self.operations.append(operation)
        self.modified_at = datetime.now()


@dataclass
class UserContext:
    """Контекст пользователя/оператора"""
    operator_id: str
    preferred_machines: List[str]
    preferred_tools: List[str]
    working_shift: Optional[str] = None
    fatigue_level: Optional[float] = None
    last_operation: Optional[Operation] = None
    experience_level: Optional[str] = None


@dataclass
class CalculationResult:
    """Результат расчета режимов резания"""
    parameters: CuttingParameters
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    confidence: float = 0.8  # Уверенность в расчете (0-1)

    def is_safe(self) -> bool:
        """Безопасны ли рассчитанные параметры"""
        return len(self.warnings) == 0