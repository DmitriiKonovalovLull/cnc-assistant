"""
Модели данных для сбора практических решений операторов.
Главная цель: сохранять РАЗНИЦУ между рекомендацией бота и реальными действиями пользователя.
"""

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, Literal
from datetime import datetime
import json


@dataclass
class MachineSpecs:
    """Характеристики станка"""
    machine_type: Literal["cnc_lathe", "manual_lathe", "milling", "other"] = "cnc_lathe"
    machine_model: Optional[str] = None
    machine_power_kw: float = 15.0  # кВт, по умолчанию средний станок
    max_rpm: Optional[float] = None  # макс обороты станка
    manufacturer: Optional[str] = None

    # Физические ограничения станка
    max_cutting_depth_mm: Optional[float] = None  # макс глубина резания для этого станка
    max_tool_overhang_mm: Optional[float] = None  # максимальный вылет инструмента


@dataclass
class MaterialData:
    """Данные о материале"""
    material_type: Literal["steel", "aluminum", "stainless_steel", "titanium", "copper", "brass", "other"]
    material_grade: Optional[str] = None  # марка стали, алюминия и т.д.
    hardness_hb: Optional[float] = None  # твердость по Бринеллю
    tensile_strength_mpa: Optional[float] = None  # предел прочности
    is_heat_treated: bool = False  # термообработанный или нет


@dataclass
class ToolData:
    """Данные об инструменте"""
    tool_type: Literal["turning_80", "turning_55", "milling", "boring", "grooving", "threading", "other"]
    insert_material: Literal["carbide", "hss", "ceramic", "cbn", "diamond", "unknown"] = "carbide"
    insert_grade: Optional[str] = None  # марка твердого сплава
    insert_radius_mm: float = 0.8  # радиус при вершине
    tool_overhang_mm: float = 30.0  # вылет инструмента, мм
    tool_holder_type: Optional[str] = None  # тип державки
    is_coolant_used: bool = True  # используется СОЖ или нет


@dataclass
class GeometryData:
    """Геометрические параметры обработки"""
    diameter_start_mm: float  # начальный диаметр
    diameter_end_mm: float  # конечный диаметр
    length_mm: float  # длина обработки

    # Рассчитываемые поля
    @property
    def total_stock_mm(self) -> float:
        """Общий припуск на сторону"""
        return (self.diameter_start_mm - self.diameter_end_mm) / 2

    @property
    def total_stock_volume_mm3(self) -> float:
        """Объем снимаемого материала"""
        avg_diameter = (self.diameter_start_mm + self.diameter_end_mm) / 2
        return self.total_stock_mm * avg_diameter * 3.14159 * self.length_mm


@dataclass
class OperationData:
    """Данные об операции"""
    operation_type: Literal["roughing", "finishing", "semi_finishing", "grooving", "threading", "boring"]
    is_external: bool = True  # наружная или внутренняя обработка
    tolerance_mm: Optional[float] = None  # допуск на размер
    surface_roughness_ra: Optional[float] = None  # требуемая шероховатость


@dataclass
class BotRecommendation:
    """Рекомендация бота (только базовые, табличные значения)"""
    cutting_speed_vc_m_min: float  # скорость резания, м/мин
    spindle_rpm: float  # обороты шпинделя, об/мин
    feed_per_rev_mm: float  # подача на оборот, мм/об
    depth_of_cut_ap_mm: float  # глубина резания, мм
    estimated_power_kw: float  # расчетная мощность, кВт

    # Стратегия проходов
    passes_strategy: Dict[str, Any]  # как разбито на проходы
    total_passes: int  # общее количество проходов


@dataclass
class UserActual:
    """Фактические параметры, которые поставил оператор"""
    spindle_rpm: float  # реальные обороты
    feed_per_rev_mm: float  # реальная подача
    depth_of_cut_ap_mm: float  # реальная глубина резания

    # Как пользователь отнесся к рекомендации
    comparison_choice: Literal["lower", "same", "higher", "manual"] = "manual"
    user_comment: Optional[str] = None  # комментарий оператора


@dataclass
class OperationResult:
    """Результат операции (заполняется после обработки)"""
    result_type: Literal["ok", "chatter", "tool_wear", "breakage", "surface_issue", "dimension_issue", "unknown"]
    result_details: Optional[str] = None  # детали результата
    tool_life_minutes: Optional[float] = None  # стойкость инструмента
    actual_machining_time_min: Optional[float] = None  # фактическое время обработки


@dataclass
class UserDecisionRecord:
    """
    ОСНОВНАЯ ЗАПИСЬ - решение оператора.
    Это "золото" для обучения ИИ.
    """
    # Идентификаторы
    record_id: str  # UUID или timestamp-based ID
    user_id: str  # идентификатор пользователя
    timestamp: datetime

    # Контекст (что обрабатываем)
    machine: MachineSpecs
    material: MaterialData
    tool: ToolData
    geometry: GeometryData
    operation: OperationData

    # Рекомендация vs Реальность
    bot_recommendation: BotRecommendation
    user_actual: UserActual

    # Коэффициенты сравнения
    difference_coeff_rpm: float  # коэффициент отличия по оборотам
    difference_coeff_feed: float  # коэффициент отличия по подаче
    difference_coeff_ap: float  # коэффициент отличия по глубине резания

    # Результат
    operation_result: Optional[OperationResult] = None

    # Метаданные для анализа
    experience_level: Literal["beginner", "intermediate", "expert", "unknown"] = "unknown"
    variance_adaptation_score: float = 0.0  # оценка адаптивности оператора
    was_decision_adaptive: bool = False  # было ли решение адаптивным к условиям

    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь для сохранения в БД"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

    def to_json(self) -> str:
        """Конвертация в JSON строку"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def calculate_differences(cls, bot: BotRecommendation, user: UserActual) -> Dict[str, float]:
        """Расчет коэффициентов отличия"""
        return {
            'difference_coeff_rpm': user.spindle_rpm / bot.spindle_rpm if bot.spindle_rpm > 0 else 1.0,
            'difference_coeff_feed': user.feed_per_rev_mm / bot.feed_per_rev_mm if bot.feed_per_rev_mm > 0 else 1.0,
            'difference_coeff_ap': user.depth_of_cut_ap_mm / bot.depth_of_cut_ap_mm if bot.depth_of_cut_ap_mm > 0 else 1.0,
        }


@dataclass
class ExperienceProfile:
    """Профиль опыта оператора (динамически обновляемый)"""
    user_id: str
    total_decisions: int = 0
    adaptive_decisions: int = 0  # решения с изменением параметров под условия

    # Коэффициенты предпочтений (средние по истории)
    avg_rpm_coeff: float = 1.0  # среднее отношение user/bot по оборотам
    avg_feed_coeff: float = 1.0  # среднее отношение user/bot по подаче
    avg_ap_coeff: float = 1.0  # среднее отношение user/bot по глубине

    # Адаптивность (меняет ли параметры при изменении условий)
    material_adaptation_score: float = 0.0  # 0-1, меняет ли при смене материала
    diameter_adaptation_score: float = 0.0  # 0-1, меняет ли при смене диаметра
    operation_adaptation_score: float = 0.0  # 0-1, меняет ли при смене операции

    @property
    def overall_experience_score(self) -> float:
        """Общая оценка опыта (0-100)"""
        # Вес адаптивности выше, чем просто стабильность
        adaptation = (self.material_adaptation_score +
                      self.diameter_adaptation_score +
                      self.operation_adaptation_score) / 3

        # Количество решений тоже важно
        volume_score = min(self.total_decisions / 50, 1.0)  # максимум при 50+ решениях

        return (adaptation * 0.7 + volume_score * 0.3) * 100


# Утилитарные функции для работы с моделями
def create_record_id() -> str:
    """Создание уникального ID записи"""
    from datetime import datetime
    import uuid
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique = str(uuid.uuid4())[:8]
    return f"decision_{timestamp}_{unique}"


def validate_physical_limits(record: UserDecisionRecord) -> list[str]:
    """
    Валидация физических ограничений.
    Возвращает список предупреждений.
    """
    warnings = []

    # Проверка глубины резания
    if record.user_actual.depth_of_cut_ap_mm > 10:
        warnings.append(
            f"Глубина резания {record.user_actual.depth_of_cut_ap_mm} мм превышает типичные значения (2-6 мм для стали)")

    # Проверка мощности
    if record.bot_recommendation.estimated_power_kw > record.machine.machine_power_kw:
        warnings.append(
            f"Расчетная мощность {record.bot_recommendation.estimated_power_kw} кВт превышает мощность станка {record.machine.machine_power_kw} кВт")

    # Проверка количества проходов
    if record.bot_recommendation.total_passes > 20:
        warnings.append(
            f"Количество проходов {record.bot_recommendation.total_passes} очень большое, проверьте стратегию")

    return warnings