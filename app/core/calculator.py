"""
ЯДРО ФИЗИЧЕСКИХ РАСЧЕТОВ ДЛЯ CNC.
ТОЛЬКО формулы, без логики, правил и стратегий.
Архитектурно чистый core-модуль.
"""

import math
from typing import Dict, Optional, Tuple
from dataclasses import dataclass


# ============================================================================
# КОНФИГУРАЦИЯ ФИЗИКИ (только константы)
# ============================================================================

class PhysicsLimitsConfig:
    """Конфигурация физических пределов (только константы)."""
    MIN_Vc_m_min = 20.0  # Минимальная скорость резания
    MIN_FEED_mm_rev = 0.05  # Минимальная подача
    MIN_RPM = 50  # Абсолютный минимум оборотов
    MIN_AP_ABSOLUTE_MM = 0.5  # Минимальная глубина в принципе
    MAX_AP_ABSOLUTE_MM = 15.0  # Максимальная глубина в принципе
    POWER_SAFE_RATIO = 0.8  # 80% от макс. мощности
    RPM_SAFE_RATIO = 0.9  # 90% от макс. оборотов
    AP_RADIUS_FACTOR = 0.67  # 2/3 радиуса пластины
    BASE_RIGIDITY_AP_MM = 4.0  # Базовая глубина для нормальной жёсткости
    OVERHANG_REDUCTION_PER_10MM = 0.2  # Уменьшение на каждые 10мм сверх нормы


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
# ЧИСТЫЙ КАЛЬКУЛЯТОР (только формулы)
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
        if ap_mm <= 0 or feed_mm_rev <= 0 or vc_m_min <= 0:
            return 0.0

        power_kw = (kc_factor * ap_mm * feed_mm_rev * vc_m_min) / 60000
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
        if vc_m_min <= 0 or feed_mm_rev <= 0 or kc_factor <= 0:
            return PhysicsLimitsConfig.MIN_AP_ABSOLUTE_MM

        safe_power = max_power_kw * safe_ratio
        numerator = safe_power * 60000
        denominator = kc_factor * feed_mm_rev * vc_m_min

        if denominator == 0:
            return PhysicsLimitsConfig.MIN_AP_ABSOLUTE_MM

        ap_max = numerator / denominator

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

        return PhysicsLimitsConfig.BASE_RIGIDITY_AP_MM * rigidity_factor * ld_factor

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
        if min_vc_m_min is None:
            min_vc_m_min = PhysicsLimitsConfig.MIN_Vc_m_min

        # Максимальные (с безопасным коэффициентом)
        safe_rpm_max = max_rpm * PhysicsLimitsConfig.RPM_SAFE_RATIO

        # Минимальные (по минимальной Vc)
        if current_diameter_mm > 0:
            min_rpm_by_vc = (1000 * min_vc_m_min) / (math.pi * current_diameter_mm)
        else:
            min_rpm_by_vc = PhysicsLimitsConfig.MIN_RPM

        safe_rpm_min = max(PhysicsLimitsConfig.MIN_RPM, min_rpm_by_vc)

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
        if diameter_mm <= 0:
            return PhysicsLimitsConfig.MIN_RPM

        rpm = (1000 * vc_m_min) / (math.pi * diameter_mm)
        # 🔧 Улучшение: защита от экзотики при больших диаметрах
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
        if diameter_mm <= 0 or rpm <= 0:
            return 0.0

        vc = (math.pi * diameter_mm * rpm) / 1000
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
        return round(feed_mm_rev * rpm, 1)

    @staticmethod
    def calculate_material_removal_rate(
            ap_mm: float,
            feed_mm_rev: float,
            vc_m_min: float
    ) -> float:
        """
        Рассчитать скорость съёма материала: Q = ap * f * vc.
        🔧 Улучшение: убран неиспользуемый diameter_mm

        Args:
            ap_mm: Глубина резания (мм)
            feed_mm_rev: Подача (мм/об)
            vc_m_min: Скорость резания (м/мин)

        Returns:
            Скорость съёма (см³/мин)
        """
        # Для точения: Q = ap * f * vc (мм³/мин)
        mm3_per_min = ap_mm * feed_mm_rev * vc_m_min * 1000  # vc в м/мин -> мм/мин
        cm3_per_min = mm3_per_min / 1000  # мм³ -> см³
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
        if factor is None:
            factor = PhysicsLimitsConfig.AP_RADIUS_FACTOR
        return insert_radius_mm * factor

    @staticmethod
    def validate_geometry(geometry: Geometry) -> list:
        """
        Базовая проверка геометрии.

        Args:
            geometry: Геометрия обработки

        Returns:
            Список ошибок (пустой если всё ок)
        """
        errors = []

        if geometry.is_external and geometry.diameter_start_mm <= geometry.diameter_end_mm:
            errors.append("Для наружной обработки начальный диаметр должен быть больше конечного")
        elif not geometry.is_external and geometry.diameter_start_mm >= geometry.diameter_end_mm:
            errors.append("Для внутренней обработки начальный диаметр должен быть меньше конечного")

        stock_per_side = abs(geometry.diameter_start_mm - geometry.diameter_end_mm) / 2
        if stock_per_side < 0.1:
            errors.append("Слишком маленький припуск (<0.1 мм)")

        current_diameter = (geometry.diameter_start_mm + geometry.diameter_end_mm) / 2
        if current_diameter < 1:
            errors.append("Слишком маленький диаметр (<1 мм)")

        return errors


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
        # Базовое правило: подача ≈ 0.5-0.7 радиуса для черновой
        base_feed = insert_radius_mm * 0.6 * operation_factor * material_factor
        # 🔧 Используем MIN_FEED_mm_rev (используется только здесь - это ОК)
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
        if diameter_mm <= 0:
            return 0.0
        return length_mm / diameter_mm

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
        if diameter_mm <= 0:
            return False
        return (length_mm / diameter_mm) > threshold

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
        # Сила резания: Fc = kc * ap * f
        return kc_factor * ap_mm * feed_mm_rev