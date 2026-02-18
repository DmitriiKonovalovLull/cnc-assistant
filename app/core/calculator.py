"""
ЯДРО ФИЗИЧЕСКИХ РАСЧЕТОВ ДЛЯ CNC.
ТОЛЬКО формулы, без логики, правил и стратегий.
Архитектурно чистый core-модуль.
"""

import math
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


# ============================================================================
# КОНФИГУРАЦИЯ ФИЗИКИ (только константы)
# ============================================================================

class PhysicsLimitsConfig:
    """Конфигурация физических пределов (только константы)."""
    MIN_Vc_m_min = 20.0  # Минимальная скорость резания
    MIN_FEED_mm_rev = 0.05  # Минимальная подача
    MIN_RPM = 50  # Абсолютный минимум оборотов
    MAX_RPM_ABSOLUTE = 100000  # Абсолютный максимум оборотов для любого станка
    MIN_AP_ABSOLUTE_MM = 0.5  # Минимальная глубина в принципе
    MAX_AP_ABSOLUTE_MM = 15.0  # Максимальная глубина в принципе
    POWER_SAFE_RATIO = 0.8  # 80% от макс. мощности
    RPM_SAFE_RATIO = 0.9  # 90% от макс. оборотов
    AP_RADIUS_FACTOR = 0.67  # 2/3 радиуса пластины
    BASE_RIGIDITY_AP_MM = 4.0  # Базовая глубина для нормальной жёсткости
    OVERHANG_REDUCTION_PER_10MM = 0.2  # Уменьшение на каждые 10мм сверх нормы
    MIN_DIAMETER_MM = 1.0  # Минимальный безопасный диаметр для расчетов
    MIN_STOCK_MM = 0.1  # Минимальный припуск


class PhysicsConstants:
    """Физические константы для расчетов."""
    # Переводные коэффициенты
    POWER_NUMERATOR: float = 60000.0  # (Н/мм² * мм * мм/об * м/мин) -> кВт
    RPM_NUMERATOR: float = 1000.0  # (м/мин) -> (мм/мин) для формулы оборотов
    MM3_TO_CM3: float = 1000.0  # мм³ -> см³
    
    # Эмпирические коэффициенты
    BASE_FEED_TO_RADIUS_RATIO: float = 0.6  # Базовая подача как доля радиуса
    ROUGHING_FACTOR: float = 1.0  # Коэффициент для черновой
    FINISHING_FACTOR: float = 0.7  # Коэффициент для чистовой
    STEEL_FACTOR: float = 1.0  # Коэффициент для стали
    ALUMINUM_FACTOR: float = 1.5  # Коэффициент для алюминия
    
    # Математические константы
    PI: float = math.pi
    EPSILON: float = 1e-12  # Точность для сравнения с нулем


class MaterialConstants:
    """Эмпирические коэффициенты для разных материалов."""
    
    # Удельная сила резания kc (Н/мм²) для разных материалов
    KC_FACTORS: Dict[str, float] = {
        'steel_low_carbon': 1500.0,  # Низкоуглеродистая сталь
        'steel_medium_carbon': 1800.0,  # Среднеуглеродистая сталь
        'steel_high_carbon': 2000.0,  # Высокоуглеродистая сталь
        'stainless_steel': 2200.0,  # Нержавеющая сталь
        'aluminum': 800.0,  # Алюминий
        'titanium': 2500.0,  # Титан
        'cast_iron': 1200.0,  # Чугун
        'brass': 900.0,  # Латунь
        'copper': 1000.0,  # Медь
    }
    
    # Коэффициенты обрабатываемости (для расчета подачи)
    MACHINABILITY_FACTORS: Dict[str, float] = {
        'steel_low_carbon': 1.0,
        'steel_medium_carbon': 0.8,
        'steel_high_carbon': 0.6,
        'stainless_steel': 0.5,
        'aluminum': 2.0,
        'titanium': 0.3,
        'cast_iron': 1.2,
        'brass': 1.5,
        'copper': 1.3,
    }
    
    @classmethod
    def get_kc_factor(cls, material_type: str) -> float:
        """Получить коэффициент kc для материала."""
        material_lower = material_type.lower()
        for key, value in cls.KC_FACTORS.items():
            if key in material_lower:
                return value
        return 1800.0  # По умолчанию среднеуглеродистая сталь
    
    @classmethod
    def get_machinability_factor(cls, material_type: str) -> float:
        """Получить коэффициент обрабатываемости для материала."""
        material_lower = material_type.lower()
        for key, value in cls.MACHINABILITY_FACTORS.items():
            if key in material_lower:
                return value
        return 1.0  # По умолчанию


class OperationType(Enum):
    """Тип операции обработки."""
    TURNING = "turning"  # Точение
    MILLING = "milling"  # Фрезерование


# ============================================================================
# ВАЛИДАЦИЯ ВХОДНЫХ ДАННЫХ
# ============================================================================

def _validate_positive_float(value: float, name: str, allow_zero: bool = False) -> None:
    """
    Проверить, что число положительное и не NaN/inf.
    
    Args:
        value: Значение для проверки
        name: Имя параметра для сообщения об ошибке
        allow_zero: Разрешить нулевое значение
        
    Raises:
        ValueError: Если значение некорректно
    """
    if math.isnan(value) or math.isinf(value):
        raise ValueError(f"{name} cannot be NaN or infinite, got {value}")
    if not allow_zero and value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")
    if allow_zero and value < 0:
        raise ValueError(f"{name} cannot be negative, got {value}")


def _validate_float(value: float, name: str) -> None:
    """
    Проверить, что число валидно (не NaN/inf).
    
    Args:
        value: Значение для проверки
        name: Имя параметра для сообщения об ошибке
        
    Raises:
        ValueError: Если значение некорректно
    """
    if math.isnan(value) or math.isinf(value):
        raise ValueError(f"{name} cannot be NaN or infinite, got {value}")


# ============================================================================
# СТРУКТУРЫ ДАННЫХ (чистые DTO, без логики)
# ============================================================================

@dataclass
class Geometry:
    """Геометрия обработки."""
    diameter_start_mm: float
    diameter_end_mm: float
    length_mm: float
    is_external: bool = True


@dataclass
class MaterialProperties:
    """Свойства материала."""
    material_type: str  # Просто строка, не enum
    kc_factor: float  # Удельная сила резания (Н/мм²)
    hardness_hb: Optional[float] = None


@dataclass
class ToolProperties:
    """Свойства инструмента."""
    material: str  # Просто строка
    insert_radius_mm: float
    tool_overhang_mm: float
    tool_angle_deg: float = 80.0


@dataclass
class MachineLimits:
    """Ограничения станка."""
    max_power_kw: float
    max_rpm: float
    machine_type: str = "cnc_lathe"


@dataclass
class CalculationResult:
    """Результат расчета (только данные)."""
    vc_m_min: float
    rpm: float
    feed_mm_rev: float
    ap_mm: float
    power_kw: float


@dataclass
class PhysicalLimits:
    """Физические ограничения (только данные)."""
    max_power_kw: float
    max_rpm: float
    max_ap_tool_mm: float
    max_feed_tool_mm_rev: float
    calculated_ap_power_mm: float
    calculated_ap_rigidity_mm: float
    safe_rpm_min: float
    safe_rpm_max: float


# ============================================================================
# БАЗОВЫЙ КАЛЬКУЛЯТОР (только формулы)
# ============================================================================

class PhysicsCalculator:
    """
    Чистый калькулятор физических параметров.
    ТОЛЬКО формулы, без правил, стратегий и бизнес-логики.
    """

    @staticmethod
    def calculate_power(kc_factor: float, ap_mm: float, feed_mm_rev: float, vc_m_min: float) -> float:
        """
        Формула мощности: P = (kc * ap * f * vc) / 60000.

        Args:
            kc_factor: Удельная сила резания (Н/мм²)
            ap_mm: Глубина резания (мм)
            feed_mm_rev: Подача (мм/об)
            vc_m_min: Скорость резания (м/мин)

        Returns:
            Мощность резания (кВт)
        """
        # Валидация входных данных
        _validate_positive_float(kc_factor, "kc_factor")
        _validate_positive_float(ap_mm, "ap_mm")
        _validate_positive_float(feed_mm_rev, "feed_mm_rev")
        _validate_positive_float(vc_m_min, "vc_m_min")

        power_kw = (kc_factor * ap_mm * feed_mm_rev * vc_m_min) / PhysicsConstants.POWER_NUMERATOR
        
        # Проверка результата на валидность
        if math.isnan(power_kw) or math.isinf(power_kw):
            return 0.0
        
        return round(power_kw, 2)

    @staticmethod
    def calculate_max_ap_by_power(
            kc_factor: float,
            vc_m_min: float,
            feed_mm_rev: float,
            max_power_kw: float,
            safe_ratio: float = 0.8
    ) -> float:
        """
        Максимальная глубина по мощности.

        Args:
            kc_factor: Удельная сила резания (Н/мм²)
            vc_m_min: Скорость резания (м/мин)
            feed_mm_rev: Подача (мм/об)
            max_power_kw: Максимальная мощность станка (кВт)
            safe_ratio: Безопасный коэффициент (0.8 = 80%)

        Returns:
            Максимальная глубина резания (мм)
        """
        # Валидация входных данных
        _validate_positive_float(kc_factor, "kc_factor")
        _validate_positive_float(vc_m_min, "vc_m_min")
        _validate_positive_float(feed_mm_rev, "feed_mm_rev")
        _validate_positive_float(max_power_kw, "max_power_kw")
        _validate_float(safe_ratio, "safe_ratio")
        
        if safe_ratio <= 0 or safe_ratio > 1.0:
            safe_ratio = PhysicsLimitsConfig.POWER_SAFE_RATIO

        safe_power = max_power_kw * safe_ratio
        numerator = safe_power * PhysicsConstants.POWER_NUMERATOR
        denominator = kc_factor * feed_mm_rev * vc_m_min

        # Явная проверка на деление на ноль
        if math.isclose(denominator, 0, abs_tol=PhysicsConstants.EPSILON):
            return PhysicsLimitsConfig.MIN_AP_ABSOLUTE_MM

        ap_max = numerator / denominator

        # Проверка результата на валидность
        if math.isnan(ap_max) or math.isinf(ap_max):
            return PhysicsLimitsConfig.MIN_AP_ABSOLUTE_MM

        # Ограничиваем абсолютными пределами
        return max(
            PhysicsLimitsConfig.MIN_AP_ABSOLUTE_MM,
            min(ap_max, PhysicsLimitsConfig.MAX_AP_ABSOLUTE_MM)
        )

    @staticmethod
    def calculate_max_ap_by_rigidity(
            tool_overhang_mm: float,
            length_mm: float,
            current_diameter_mm: float
    ) -> float:
        """
        Максимальная глубина по жёсткости.

        Args:
            tool_overhang_mm: Вылет инструмента (мм)
            length_mm: Длина обработки (мм)
            current_diameter_mm: Текущий диаметр (мм)

        Returns:
            Максимальная глубина по жёсткости (мм)
        """
        # Валидация входных данных
        _validate_positive_float(tool_overhang_mm, "tool_overhang_mm", allow_zero=True)
        _validate_positive_float(length_mm, "length_mm", allow_zero=True)
        _validate_positive_float(current_diameter_mm, "current_diameter_mm", allow_zero=True)
        
        # Коэффициент жесткости инструмента
        base_overhang = 30.0
        if tool_overhang_mm <= base_overhang:
            rigidity_factor = 1.0
        else:
            extra = tool_overhang_mm - base_overhang
            reduction = (extra / 10) * PhysicsLimitsConfig.OVERHANG_REDUCTION_PER_10MM
            rigidity_factor = max(0.3, 1.0 - reduction)

        # Коэффициент отношения длина/диаметр
        if current_diameter_mm <= 0:
            ld_factor = 1.0
        else:
            ld_ratio = length_mm / current_diameter_mm
            if ld_ratio > 4:
                ld_factor = 0.5
            elif ld_ratio > 2:
                ld_factor = 0.75
            else:
                ld_factor = 1.0

        result = PhysicsLimitsConfig.BASE_RIGIDITY_AP_MM * rigidity_factor * ld_factor
        
        # Проверка результата
        if math.isnan(result) or math.isinf(result):
            return PhysicsLimitsConfig.MIN_AP_ABSOLUTE_MM
        
        return result

    @staticmethod
    def calculate_safe_rpm_range(
            current_diameter_mm: float,
            max_rpm: float,
            min_vc_m_min: float = None
    ) -> Tuple[float, float]:
        """
        Безопасный диапазон оборотов.

        Args:
            current_diameter_mm: Текущий диаметр (мм)
            max_rpm: Максимальные обороты станка
            min_vc_m_min: Минимальная скорость резания (если None, берётся из конфига)

        Returns:
            (safe_rpm_min, safe_rpm_max)
        """
        # Валидация входных данных
        _validate_positive_float(max_rpm, "max_rpm")
        if min_vc_m_min is not None:
            _validate_positive_float(min_vc_m_min, "min_vc_m_min")
        else:
            min_vc_m_min = PhysicsLimitsConfig.MIN_Vc_m_min

        # Максимальные (с безопасным коэффициентом)
        safe_rpm_max = max_rpm * PhysicsLimitsConfig.RPM_SAFE_RATIO

        # Минимальные (по минимальной Vc)
        if current_diameter_mm > 0:
            min_rpm_by_vc = (PhysicsConstants.RPM_NUMERATOR * min_vc_m_min) / (PhysicsConstants.PI * current_diameter_mm)
        else:
            min_rpm_by_vc = PhysicsLimitsConfig.MIN_RPM

        safe_rpm_min = max(PhysicsLimitsConfig.MIN_RPM, min_rpm_by_vc)
        
        # Проверка результатов
        if math.isnan(safe_rpm_min) or math.isinf(safe_rpm_min):
            safe_rpm_min = PhysicsLimitsConfig.MIN_RPM
        if math.isnan(safe_rpm_max) or math.isinf(safe_rpm_max):
            safe_rpm_max = PhysicsLimitsConfig.MAX_RPM_ABSOLUTE

        return round(safe_rpm_min), round(safe_rpm_max)

    @staticmethod
    def calculate_rpm(vc_m_min: float, diameter_mm: float) -> float:
        """
        Рассчитать обороты: n = (1000 * vc) / (π * D).

        Args:
            vc_m_min: Скорость резания (м/мин)
            diameter_mm: Диаметр (мм)

        Returns:
            Обороты (об/мин), защищённые от экстремальных значений
        """
        # Валидация входных данных
        _validate_positive_float(vc_m_min, "vc_m_min")
        _validate_positive_float(diameter_mm, "diameter_mm")
        
        # Защита от очень маленького диаметра (слишком большие обороты)
        if diameter_mm < PhysicsLimitsConfig.MIN_DIAMETER_MM:
            diameter_mm = PhysicsLimitsConfig.MIN_DIAMETER_MM
        
        # Математическая проверка на деление на ноль
        if math.isclose(diameter_mm, 0, abs_tol=PhysicsConstants.EPSILON):
            return PhysicsLimitsConfig.MIN_RPM

        try:
            rpm = (PhysicsConstants.RPM_NUMERATOR * vc_m_min) / (PhysicsConstants.PI * diameter_mm)
        except OverflowError:
            rpm = float('inf')

        # Проверка на бесконечность и NaN
        if math.isinf(rpm) or math.isnan(rpm):
            rpm = PhysicsLimitsConfig.MAX_RPM_ABSOLUTE
        
        # Защита от очень больших оборотов
        rpm = min(rpm, PhysicsLimitsConfig.MAX_RPM_ABSOLUTE)
        
        return max(PhysicsLimitsConfig.MIN_RPM, round(rpm))

    @staticmethod
    def calculate_cutting_speed(rpm: float, diameter_mm: float) -> float:
        """
        Рассчитать скорость резания: vc = (π * D * n) / 1000.

        Args:
            rpm: Обороты (об/мин)
            diameter_mm: Диаметр (мм)

        Returns:
            Скорость резания (м/мин)
        """
        # Валидация входных данных
        _validate_positive_float(rpm, "rpm")
        _validate_positive_float(diameter_mm, "diameter_mm")

        vc = (PhysicsConstants.PI * diameter_mm * rpm) / PhysicsConstants.RPM_NUMERATOR
        
        # Проверка результата
        if math.isnan(vc) or math.isinf(vc):
            return 0.0
        
        return round(vc, 1)

    @staticmethod
    def calculate_feed_rate(feed_mm_rev: float, rpm: float) -> float:
        """
        Рассчитать скорость подачи: vf = f * n.

        Args:
            feed_mm_rev: Подача на оборот (мм/об)
            rpm: Обороты (об/мин)

        Returns:
            Скорость подачи (мм/мин)
        """
        # Валидация входных данных
        _validate_positive_float(feed_mm_rev, "feed_mm_rev")
        _validate_positive_float(rpm, "rpm")
        
        # Защита от переполнения
        if feed_mm_rev > 1000 or rpm > PhysicsLimitsConfig.MAX_RPM_ABSOLUTE:
            return 0.0
        
        result = feed_mm_rev * rpm
        
        # Проверка результата
        if math.isnan(result) or math.isinf(result):
            return 0.0
        
        return round(result, 1)

    @staticmethod
    def calculate_material_removal_rate(
            ap_mm: float,
            feed_mm_rev: float,
            vc_m_min: float
    ) -> float:
        """
        Рассчитать скорость съёма материала: Q = ap * f * vc.

        Args:
            ap_mm: Глубина резания (мм)
            feed_mm_rev: Подача (мм/об)
            vc_m_min: Скорость резания (м/мин)

        Returns:
            Скорость съёма (см³/мин)
        """
        # Валидация входных данных
        _validate_positive_float(ap_mm, "ap_mm")
        _validate_positive_float(feed_mm_rev, "feed_mm_rev")
        _validate_positive_float(vc_m_min, "vc_m_min")
        
        # Для точения: Q = ap * f * vc (мм³/мин)
        mm3_per_min = ap_mm * feed_mm_rev * vc_m_min * PhysicsConstants.RPM_NUMERATOR  # vc в м/мин -> мм/мин
        cm3_per_min = mm3_per_min / PhysicsConstants.MM3_TO_CM3  # мм³ -> см³
        
        # Проверка результата
        if math.isnan(cm3_per_min) or math.isinf(cm3_per_min):
            return 0.0
        
        return round(cm3_per_min, 2)

    @staticmethod
    def calculate_ap_by_radius(insert_radius_mm: float, factor: float = None) -> float:
        """
        Максимальная глубина по радиусу пластины.

        Args:
            insert_radius_mm: Радиус пластины (мм)
            factor: Коэффициент (по умолчанию 2/3)

        Returns:
            Максимальная глубина (мм)
        """
        # Валидация входных данных
        _validate_positive_float(insert_radius_mm, "insert_radius_mm")
        
        if factor is None:
            factor = PhysicsLimitsConfig.AP_RADIUS_FACTOR
        else:
            _validate_float(factor, "factor")
            if factor <= 0 or factor > 1.0:
                factor = PhysicsLimitsConfig.AP_RADIUS_FACTOR
        
        result = insert_radius_mm * factor
        
        # Проверка результата
        if math.isnan(result) or math.isinf(result):
            return PhysicsLimitsConfig.MIN_AP_ABSOLUTE_MM
        
        return result

    @staticmethod
    def validate_geometry(geometry: Geometry) -> list:
        """
        Базовая проверка геометрии с расширенной валидацией.

        Args:
            geometry: Геометрия обработки

        Returns:
            Список ошибок (пустой если всё ок)
        """
        errors = []
        
        # Проверка на None/null
        if geometry is None:
            return ["Geometry cannot be None"]
        
        # Проверка на NaN и inf
        try:
            _validate_float(geometry.diameter_start_mm, "diameter_start_mm")
            _validate_float(geometry.diameter_end_mm, "diameter_end_mm")
            _validate_float(geometry.length_mm, "length_mm")
        except ValueError as e:
            errors.append(str(e))
            return errors  # Если есть NaN/inf, дальше проверять бессмысленно
        
        # Проверка на отрицательные значения
        if geometry.diameter_start_mm <= 0:
            errors.append(f"Start diameter must be positive, got {geometry.diameter_start_mm}")
        if geometry.diameter_end_mm <= 0:
            errors.append(f"End diameter must be positive, got {geometry.diameter_end_mm}")
        if geometry.length_mm <= 0:
            errors.append(f"Length must be positive, got {geometry.length_mm}")
        
        # Проверка на очень маленькие значения (меньше 0.1 мм)
        if geometry.diameter_start_mm < PhysicsLimitsConfig.MIN_STOCK_MM:
            errors.append(f"Start diameter too small (<{PhysicsLimitsConfig.MIN_STOCK_MM} mm): {geometry.diameter_start_mm}")
        if geometry.diameter_end_mm < PhysicsLimitsConfig.MIN_STOCK_MM:
            errors.append(f"End diameter too small (<{PhysicsLimitsConfig.MIN_STOCK_MM} mm): {geometry.diameter_end_mm}")
        if geometry.length_mm < PhysicsLimitsConfig.MIN_STOCK_MM:
            errors.append(f"Length too small (<{PhysicsLimitsConfig.MIN_STOCK_MM} mm): {geometry.length_mm}")

        # Проверка логики обработки
        if geometry.is_external and geometry.diameter_start_mm <= geometry.diameter_end_mm:
            errors.append("Для наружной обработки начальный диаметр должен быть больше конечного")
        elif not geometry.is_external and geometry.diameter_start_mm >= geometry.diameter_end_mm:
            errors.append("Для внутренней обработки начальный диаметр должен быть меньше конечного")

        stock_per_side = abs(geometry.diameter_start_mm - geometry.diameter_end_mm) / 2
        if stock_per_side < PhysicsLimitsConfig.MIN_STOCK_MM:
            errors.append(f"Слишком маленький припуск (<{PhysicsLimitsConfig.MIN_STOCK_MM} мм)")

        current_diameter = (geometry.diameter_start_mm + geometry.diameter_end_mm) / 2
        if current_diameter < PhysicsLimitsConfig.MIN_DIAMETER_MM:
            errors.append(f"Слишком маленький диаметр (<{PhysicsLimitsConfig.MIN_DIAMETER_MM} мм)")

        return errors


# ============================================================================
# СПЕЦИАЛИЗИРОВАННЫЕ КАЛЬКУЛЯТОРЫ ДЛЯ РАЗНЫХ ТИПОВ ОБРАБОТКИ
# ============================================================================

class TurningPhysicsCalculator(PhysicsCalculator):
    """Физика для токарной обработки."""
    
    # Все методы наследуются от базового класса
    pass


class MillingPhysicsCalculator(PhysicsCalculator):
    """Физика для фрезерной обработки."""
    
    @staticmethod
    def calculate_power(
        kc_factor: float,
        ap_mm: float,  # Глубина резания (мм)
        ae_mm: float,  # Ширина резания (мм)
        fz_mm: float,  # Подача на зуб (мм/зуб)
        z: int,  # Количество зубьев
        vc_m_min: float
    ) -> float:
        """
        Мощность для фрезерования: P = (kc * ap * ae * fz * z * vc) / (60000 * 1000).
        
        Args:
            kc_factor: Удельная сила резания (Н/мм²)
            ap_mm: Глубина резания (мм)
            ae_mm: Ширина резания (мм)
            fz_mm: Подача на зуб (мм/зуб)
            z: Количество зубьев
            vc_m_min: Скорость резания (м/мин)
            
        Returns:
            Мощность резания (кВт)
        """
        # Валидация входных данных
        _validate_positive_float(kc_factor, "kc_factor")
        _validate_positive_float(ap_mm, "ap_mm")
        _validate_positive_float(ae_mm, "ae_mm")
        _validate_positive_float(fz_mm, "fz_mm")
        _validate_positive_float(vc_m_min, "vc_m_min")
        if z <= 0:
            raise ValueError(f"Number of teeth (z) must be positive, got {z}")
        
        # Формула для фрезерования
        power_kw = (kc_factor * ap_mm * ae_mm * fz_mm * z * vc_m_min) / (PhysicsConstants.POWER_NUMERATOR * PhysicsConstants.MM3_TO_CM3)
        
        # Проверка результата
        if math.isnan(power_kw) or math.isinf(power_kw):
            return 0.0
        
        return round(power_kw, 2)
    
    @staticmethod
    def calculate_feed_rate_milling(
        fz_mm: float,  # Подача на зуб (мм/зуб)
        z: int,  # Количество зубьев
        rpm: float
    ) -> float:
        """
        Скорость подачи для фрезерования: vf = fz * z * n.
        
        Args:
            fz_mm: Подача на зуб (мм/зуб)
            z: Количество зубьев
            rpm: Обороты (об/мин)
            
        Returns:
            Скорость подачи (мм/мин)
        """
        # Валидация входных данных
        _validate_positive_float(fz_mm, "fz_mm")
        _validate_positive_float(rpm, "rpm")
        if z <= 0:
            raise ValueError(f"Number of teeth (z) must be positive, got {z}")
        
        result = fz_mm * z * rpm
        
        # Проверка результата
        if math.isnan(result) or math.isinf(result):
            return 0.0
        
        return round(result, 1)


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЙ КЛАСС ДЛЯ СЛОЖНЫХ РАСЧЁТОВ
# ============================================================================

class CuttingParametersCalculator:
    """
    Калькулятор для расчёта связанных параметров резания.
    Тоже только формулы, без бизнес-логики.
    """

    @staticmethod
    def calculate_optimal_feed(
            insert_radius_mm: float,
            operation_factor: float = 1.0,
            material_factor: float = 1.0
    ) -> float:
        """
        Рассчитать оптимальную подачу на основе радиуса пластины.

        Args:
            insert_radius_mm: Радиус пластины (мм)
            operation_factor: Коэффициент операции (черновая=1.0, чистовая=0.7)
            material_factor: Коэффициент материала (сталь=1.0, алюминий=1.5)

        Returns:
            Рекомендуемая подача (мм/об), защищённая минимальным значением
        """
        # Валидация входных данных
        _validate_positive_float(insert_radius_mm, "insert_radius_mm")
        _validate_float(operation_factor, "operation_factor")
        _validate_float(material_factor, "material_factor")
        
        # Базовое правило: подача ≈ 0.5-0.7 радиуса для черновой
        base_feed = insert_radius_mm * PhysicsConstants.BASE_FEED_TO_RADIUS_RATIO * operation_factor * material_factor
        
        # Проверка результата
        if math.isnan(base_feed) or math.isinf(base_feed):
            return PhysicsLimitsConfig.MIN_FEED_mm_rev
        
        return max(PhysicsLimitsConfig.MIN_FEED_mm_rev, round(base_feed, 3))

    @staticmethod
    def calculate_ld_ratio(length_mm: float, diameter_mm: float) -> float:
        """
        Рассчитать отношение длина/диаметр.

        Args:
            length_mm: Длина обработки (мм)
            diameter_mm: Диаметр (мм)

        Returns:
            L/D отношение
        """
        # Валидация входных данных
        _validate_positive_float(length_mm, "length_mm", allow_zero=True)
        _validate_positive_float(diameter_mm, "diameter_mm")
        
        if math.isclose(diameter_mm, 0, abs_tol=PhysicsConstants.EPSILON):
            return 0.0
        
        result = length_mm / diameter_mm
        
        # Проверка результата
        if math.isnan(result) or math.isinf(result):
            return 0.0
        
        return result

    @staticmethod
    def is_deep_cut(length_mm: float, diameter_mm: float, threshold: float = 3.0) -> bool:
        """
        Проверить, является ли обработка глубокой.

        Args:
            length_mm: Длина обработки (мм)
            diameter_mm: Диаметр (мм)
            threshold: Порог L/D для глубокой обработки

        Returns:
            True если L/D > threshold
        """
        # Валидация входных данных
        _validate_positive_float(length_mm, "length_mm", allow_zero=True)
        _validate_positive_float(diameter_mm, "diameter_mm")
        _validate_float(threshold, "threshold")
        
        if math.isclose(diameter_mm, 0, abs_tol=PhysicsConstants.EPSILON):
            return False
        
        ld_ratio = length_mm / diameter_mm
        
        # Проверка результата
        if math.isnan(ld_ratio) or math.isinf(ld_ratio):
            return False
        
        return ld_ratio > threshold

    @staticmethod
    def calculate_cutting_force(
            kc_factor: float,
            ap_mm: float,
            feed_mm_rev: float
    ) -> float:
        """
        Рассчитать силу резания.

        Args:
            kc_factor: Удельная сила резания (Н/мм²)
            ap_mm: Глубина резания (мм)
            feed_mm_rev: Подача (мм/об)

        Returns:
            Сила резания (Н)
        """
        # Валидация входных данных
        _validate_positive_float(kc_factor, "kc_factor")
        _validate_positive_float(ap_mm, "ap_mm")
        _validate_positive_float(feed_mm_rev, "feed_mm_rev")
        
        # Сила резания: Fc = kc * ap * f
        result = kc_factor * ap_mm * feed_mm_rev
        
        # Проверка результата
        if math.isnan(result) or math.isinf(result):
            return 0.0
        
        return result
