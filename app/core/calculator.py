"""
Калькулятор режимов резания с учетом физических ограничений.
Главный принцип: НЕ давать заведомо ложные цифры, а показывать ОГРАНИЧЕНИЯ.
"""
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import math


@dataclass
class CuttingLimits:
    """Физические ограничения для обработки."""
    # Ограничения по станку
    max_power_kw: float = 15.0  # максимальная мощность станка
    max_rpm: float = 3000.0  # максимальные обороты станка
    max_cutting_force_n: float = 5000.0  # максимальное усилие резания

    # Ограничения по инструменту
    max_ap_by_tool_mm: float = 6.0  # максимальная глубина резания для инструмента
    max_feed_by_tool_mm_rev: float = 0.4  # максимальная подача для инструмента
    min_insert_radius_mm: float = 0.4  # минимальный радиус при вершине

    # Ограничения по жесткости
    max_tool_overhang_mm: float = 50.0  # максимальный вылет инструмента
    recommended_max_overhang_mm: float = 30.0  # рекомендуемый вылет

    # Безопасные диапазоны (по умолчанию)
    safe_ap_range_mm: Tuple[float, float] = (0.5, 6.0)  # безопасная глубина резания
    safe_feed_range_mm_rev: Tuple[float, float] = (0.05, 0.3)  # безопасная подача
    safe_rpm_range: Tuple[float, float] = (100, 2000)  # безопасные обороты


@dataclass
class MaterialProperties:
    """Свойства материала для расчета."""
    material_type: str  # steel, aluminum, stainless_steel, etc.
    hardness_hb: Optional[float] = None
    tensile_strength_mpa: Optional[float] = None
    is_heat_treated: bool = False

    # Коэффициенты для расчета сил резания (эмпирические)
    kc1: float = 1800  # удельная сила резания, Н/мм²
    mc: float = 0.28  # показатель степени
    gamma: float = 0.75  # коэффициент передней грани


@dataclass
class ToolProperties:
    """Свойства инструмента."""
    insert_material: str  # carbide, hss, ceramic, etc.
    insert_radius_mm: float = 0.8  # радиус при вершине
    tool_overhang_mm: float = 30.0  # вылет инструмента
    tool_angle_deg: float = 80.0  # угол в плане
    is_coolant_used: bool = True


@dataclass
class Geometry:
    """Геометрия обработки."""
    diameter_start_mm: float  # начальный диаметр
    diameter_end_mm: float  # конечный диаметр
    length_mm: float  # длина обработки
    is_external: bool = True  # наружная обработка

    @property
    def diameter_current_mm(self) -> float:
        """Текущий диаметр (для расчета в процессе обработки)."""
        return self.diameter_start_mm

    @property
    def stock_per_side_mm(self) -> float:
        """Припуск на сторону, мм."""
        return (self.diameter_start_mm - self.diameter_end_mm) / 2

    @property
    def stock_volume_mm3(self) -> float:
        """Объем снимаемого материала, мм³."""
        avg_diameter = (self.diameter_start_mm + self.diameter_end_mm) / 2
        return self.stock_per_side_mm * avg_diameter * math.pi * self.length_mm

    @property
    def is_heavy_stock(self) -> bool:
        """Является ли припуск большим."""
        return self.stock_per_side_mm > 10.0


class CuttingCalculator:
    """
    Калькулятор режимов резания с физическими ограничениями.
    """

    # Базовые скорости резания (м/мин) для разных материалов и операций
    # Источник: справочники по режимам резания
    BASE_CUTTING_SPEEDS = {
        'steel': {
            'roughing': 80,  # черновая
            'semi_finishing': 120,  # получистовая
            'finishing': 150,  # чистовая
        },
        'aluminum': {
            'roughing': 250,
            'semi_finishing': 350,
            'finishing': 500,
        },
        'stainless_steel': {
            'roughing': 60,
            'semi_finishing': 80,
            'finishing': 100,
        },
        'titanium': {
            'roughing': 30,
            'semi_finishing': 45,
            'finishing': 60,
        },
        'copper': {
            'roughing': 150,
            'semi_finishing': 200,
            'finishing': 250,
        }
    }

    # Базовые подачи (мм/об) для разных операций
    BASE_FEEDS = {
        'roughing': 0.2,
        'semi_finishing': 0.1,
        'finishing': 0.05,
    }

    # Коэффициенты для инструмента
    TOOL_MATERIAL_COEFFS = {
        'carbide': 1.0,
        'ceramic': 1.5,
        'cbn': 2.0,
        'diamond': 3.0,
        'hss': 0.5,
    }

    def __init__(
            self,
            limits: CuttingLimits,
            material: MaterialProperties,
            tool: ToolProperties,
            geometry: Geometry
    ):
        self.limits = limits
        self.material = material
        self.tool = tool
        self.geometry = geometry

        # Проверка ввода
        self._validate_inputs()

    def _validate_inputs(self):
        """Проверка корректности входных данных."""
        if self.geometry.diameter_start_mm <= self.geometry.diameter_end_mm:
            raise ValueError("Начальный диаметр должен быть больше конечного")

        if self.geometry.stock_per_side_mm <= 0:
            raise ValueError("Припуск должен быть положительным")

        if self.tool.tool_overhang_mm > self.limits.max_tool_overhang_mm:
            raise ValueError(
                f"Вылет инструмента {self.tool.tool_overhang_mm} мм превышает максимальный {self.limits.max_tool_overhang_mm} мм")

    def calculate_max_ap_by_power(self, vc: float, feed: float) -> float:
        """
        Рассчитать максимальную глубину резания по мощности станка.

        Args:
            vc: скорость резания, м/мин
            feed: подача, мм/об

        Returns:
            Максимальная глубина резания, мм
        """
        # Удельная сила резания (упрощенный расчет)
        kc = self.material.kc1  # Н/мм²

        # Мощность резания: P = (kc * ap * f * vc) / (60000 * eta)
        # где eta ≈ 0.8 - КПД
        eta = 0.8

        # Преобразуем: ap_max = (P_max * 60000 * eta) / (kc * f * vc)
        if vc <= 0 or feed <= 0:
            return self.limits.safe_ap_range_mm[0]

        ap_max = (self.limits.max_power_kw * 60000 * eta) / (kc * feed * vc)

        # Ограничиваем безопасным диапазоном
        return min(ap_max, self.limits.safe_ap_range_mm[1])

    def calculate_max_ap_by_tool(self) -> float:
        """Максимальная глубина резания по инструменту."""
        # Правило: ap_max ≤ 2/3 * радиуса пластины
        ap_by_radius = self.tool.insert_radius_mm * 0.67

        # Ограничение по типу инструмента
        ap_by_tool_type = self.limits.max_ap_by_tool_mm

        return min(ap_by_radius, ap_by_tool_type, self.limits.safe_ap_range_mm[1])

    def calculate_max_ap_by_rigidity(self) -> float:
        """Максимальная глубина резания по жесткости."""
        # Эмпирическое правило: ap_max уменьшается с увеличением вылета
        rigidity_factor = 1.0 - (self.tool.tool_overhang_mm / self.limits.max_tool_overhang_mm) * 0.5

        # Базовое значение для нормального вылета
        base_ap = 4.0  # мм

        return base_ap * rigidity_factor

    def get_safe_ap(self, vc: float, feed: float) -> float:
        """
        Получить безопасную глубину резания с учетом всех ограничений.
        """
        ap_power = self.calculate_max_ap_by_power(vc, feed)
        ap_tool = self.calculate_max_ap_by_tool()
        ap_rigidity = self.calculate_max_ap_by_rigidity()

        # Берем минимальное из всех ограничений
        ap_max = min(ap_power, ap_tool, ap_rigidity)

        # Но не меньше минимального безопасного значения
        ap_max = max(ap_max, self.limits.safe_ap_range_mm[0])

        return ap_max

    def get_base_cutting_speed(self, operation_type: str) -> float:
        """
        Получить базовую скорость резания для материала и операции.
        """
        material_type = self.material.material_type.lower()

        if material_type not in self.BASE_CUTTING_SPEEDS:
            # По умолчанию - сталь
            material_type = 'steel'

        if operation_type not in self.BASE_CUTTING_SPEEDS[material_type]:
            # По умолчанию - черновая
            operation_type = 'roughing'

        base_vc = self.BASE_CUTTING_SPEEDS[material_type][operation_type]

        # Корректировка по твердости (если известна)
        if self.material.hardness_hb:
            if material_type == 'steel':
                # Для стали: чем тверже, тем меньше скорость
                hardness_factor = 200 / max(self.material.hardness_hb, 100)
                base_vc *= hardness_factor

        # Корректировка по инструменту
        tool_coeff = self.TOOL_MATERIAL_COEFFS.get(
            self.tool.insert_material.lower(),
            1.0
        )

        return base_vc * tool_coeff

    def calculate_rpm(self, vc: float, diameter_mm: float) -> float:
        """
        Рассчитать обороты по скорости резания и диаметру.

        Формула: n = (1000 * vc) / (π * D)
        """
        if diameter_mm <= 0:
            return self.limits.safe_rpm_range[0]

        rpm = (1000 * vc) / (math.pi * diameter_mm)

        # Ограничиваем оборотами станка
        rpm = min(rpm, self.limits.max_rpm)

        # Ограничиваем безопасным диапазоном
        rpm = max(rpm, self.limits.safe_rpm_range[0])
        rpm = min(rpm, self.limits.safe_rpm_range[1])

        return round(rpm, 1)

    def get_base_feed(self, operation_type: str) -> float:
        """
        Получить базовую подачу для операции.
        """
        if operation_type not in self.BASE_FEEDS:
            operation_type = 'roughing'

        base_feed = self.BASE_FEEDS[operation_type]

        # Корректировка по радиусу пластины
        # Больший радиус - можно больше подача
        radius_factor = self.tool.insert_radius_mm / 0.8  # относительно стандарта 0.8
        base_feed *= radius_factor

        # Ограничиваем максимальной подачей для инструмента
        base_feed = min(base_feed, self.limits.max_feed_by_tool_mm_rev)

        # Ограничиваем безопасным диапазоном
        base_feed = max(base_feed, self.limits.safe_feed_range_mm_rev[0])
        base_feed = min(base_feed, self.limits.safe_feed_range_mm_rev[1])

        return round(base_feed, 3)

    def calculate_cutting_power(self, ap_mm: float, feed_mm_rev: float, vc_m_min: float) -> float:
        """
        Рассчитать требуемую мощность резания.

        Формула: P = (kc * ap * f * vc) / (60000 * η)
        где:
          kc - удельная сила резания, Н/мм²
          ap - глубина резания, мм
          f - подача, мм/об
          vc - скорость резания, м/мин
          η - КПД (0.7-0.9)
        """
        kc = self.material.kc1  # Н/мм²
        eta = 0.8  # КПД станка

        if ap_mm <= 0 or feed_mm_rev <= 0 or vc_m_min <= 0:
            return 0.0

        power_kw = (kc * ap_mm * feed_mm_rev * vc_m_min) / (60000 * eta)

        return round(power_kw, 2)

    def calculate_passes_strategy(
            self,
            operation_type: str,
            target_ap_mm: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Рассчитать стратегию проходов.

        Главное правило: НЕ брать весь припуск за один проход!
        """
        total_stock = self.geometry.stock_per_side_mm

        # Базовые рекомендации по глубине резания
        recommended_ap = {
            'roughing': 4.0,  # черновая
            'semi_finishing': 2.0,  # получистовая
            'finishing': 0.5,  # чистовая
        }

        if target_ap_mm is None:
            target_ap_mm = recommended_ap.get(operation_type, 2.0)

        # Ограничиваем target_ap безопасными значениями
        target_ap_mm = min(target_ap_mm, self.limits.safe_ap_range_mm[1])
        target_ap_mm = max(target_ap_mm, self.limits.safe_ap_range_mm[0])

        # НЕ ДЕЛИМ НА 50 ПРОХОДОВ! Это абсурд
        if total_stock <= target_ap_mm:
            # Весь припуск за один проход
            passes = [{'pass_num': 1, 'ap_mm': total_stock, 'type': operation_type}]
            total_passes = 1
        else:
            # Рассчитываем количество проходов
            # НЕ МАЛЕНЬКИМИ СЛОЙКАМИ!
            rough_passes = []
            remaining_stock = total_stock

            # Черновые проходы
            pass_num = 1
            while remaining_stock > target_ap_mm * 0.5:  # пока есть что снимать
                ap_this_pass = min(target_ap_mm, remaining_stock)
                rough_passes.append({
                    'pass_num': pass_num,
                    'ap_mm': round(ap_this_pass, 2),
                    'type': 'roughing'
                })
                remaining_stock -= ap_this_pass
                pass_num += 1

            # Если остался небольшой припуск - чистовой проход
            if remaining_stock > 0.1:  # больше 0.1 мм
                rough_passes.append({
                    'pass_num': pass_num,
                    'ap_mm': round(remaining_stock, 2),
                    'type': 'finishing' if operation_type == 'finishing' else 'semi_finishing'
                })

            passes = rough_passes
            total_passes = len(passes)

        # РЕАЛЬНЫЕ цифры: 5-12 проходов для черновой, не 50!
        if total_passes > 20:
            # Что-то пошло не так, пересчитываем с большей глубиной
            return self.calculate_passes_strategy(
                operation_type,
                target_ap_mm * 1.5  # увеличиваем глубину
            )

        return {
            'passes': passes,
            'total_passes': total_passes,
            'total_stock_mm': total_stock,
            'operation_type': operation_type,
            'recommended_ap_mm': target_ap_mm,
        }

    def get_recommendation(
            self,
            operation_type: str = 'roughing'
    ) -> Dict[str, Any]:
        """
        Получить рекомендацию по режимам резания.

        Возвращает:
        - Безопасные, физически корректные параметры
        - Стратегию проходов
        - Расчетную мощность
        - Предупреждения об ограничениях
        """
        warnings = []

        # 1. Базовая скорость резания
        vc = self.get_base_cutting_speed(operation_type)

        # 2. Базовая подача
        feed = self.get_base_feed(operation_type)

        # 3. Обороты
        rpm = self.calculate_rpm(vc, self.geometry.diameter_current_mm)

        # 4. Безопасная глубина резания
        safe_ap = self.get_safe_ap(vc, feed)

        # 5. Стратегия проходов
        strategy = self.calculate_passes_strategy(operation_type, safe_ap)

        # 6. Расчетная мощность
        power = self.calculate_cutting_power(safe_ap, feed, vc)

        # 7. Проверка ограничений
        if power > self.limits.max_power_kw * 0.9:  # 90% от максимальной
            warnings.append(f"Расчетная мощность {power} кВт близка к максимальной {self.limits.max_power_kw} кВт")
            # Уменьшаем глубину резания
            safe_ap *= 0.7
            power = self.calculate_cutting_power(safe_ap, feed, vc)

        if rpm > self.limits.max_rpm * 0.9:
            warnings.append(f"Обороты {rpm} об/мин близки к максимальным {self.limits.max_rpm} об/мин")

        if strategy['total_passes'] > 15:
            warnings.append(
                f"Количество проходов {strategy['total_passes']} велико, рассмотрите инструмент с большей глубиной резания")

        # 8. Проверка абсурдных значений (которые были в старом боте)
        if safe_ap > 10:
            warnings.append(f"Глубина резания {safe_ap} мм слишком велика, ограничиваем 6 мм")
            safe_ap = min(safe_ap, 6.0)

        if strategy['total_passes'] > 30:
            warnings.append(f"{strategy['total_passes']} проходов - это нереально! Пересчитываем...")
            # Форсированно увеличиваем глубину резания
            safe_ap = min(self.limits.safe_ap_range_mm[1], self.geometry.stock_per_side_mm / 10)
            strategy = self.calculate_passes_strategy(operation_type, safe_ap)

        return {
            'vc': round(vc, 1),  # м/мин
            'rpm': round(rpm, 1),  # об/мин
            'feed': feed,  # мм/об
            'ap': round(safe_ap, 2),  # мм
            'power_kw': round(power, 2),  # кВт
            'passes_strategy': strategy,
            'total_passes': strategy['total_passes'],
            'warnings': warnings,
            'is_physically_possible': len(warnings) == 0,

            # Контекст для отладки
            'context': {
                'material': self.material.material_type,
                'diameter': self.geometry.diameter_current_mm,
                'stock_per_side': self.geometry.stock_per_side_mm,
                'operation': operation_type,
                'tool_material': self.tool.insert_material,
                'tool_radius': self.tool.insert_radius_mm,
            }
        }

    def get_alternative_recommendations(self) -> Dict[str, Dict[str, Any]]:
        """
        Получить альтернативные рекомендации для разных стратегий.
        """
        strategies = ['roughing', 'semi_finishing', 'finishing']

        results = {}
        for strategy in strategies:
            try:
                results[strategy] = self.get_recommendation(strategy)
            except Exception as e:
                results[strategy] = {'error': str(e)}

        return results


# ============================================================================
# УТИЛИТНЫЕ ФУНКЦИИ
# ============================================================================

def create_calculator_from_context(context: Dict[str, Any]) -> CuttingCalculator:
    """
    Создать калькулятор из контекста (как из бота).

    Пример контекста:
    {
        'material': 'steel',
        'diameter_start': 400,
        'diameter_end': 200,
        'length': 100,
        'machine_power': 15,
        'tool_material': 'carbide',
        'tool_radius': 0.8,
        'tool_overhang': 30,
    }
    """
    # Парсим контекст
    material_type = context.get('material', 'steel')

    # Свойства материала
    material = MaterialProperties(
        material_type=material_type,
        hardness_hb=context.get('hardness_hb'),
        tensile_strength_mpa=context.get('tensile_strength_mpa'),
        is_heat_treated=context.get('is_heat_treated', False)
    )

    # Ограничения
    limits = CuttingLimits(
        max_power_kw=context.get('machine_power', 15.0),
        max_rpm=context.get('max_rpm', 3000.0),
        max_ap_by_tool_mm=context.get('max_ap_by_tool', 6.0),
        max_feed_by_tool_mm_rev=context.get('max_feed', 0.4),
    )

    # Инструмент
    tool = ToolProperties(
        insert_material=context.get('tool_material', 'carbide'),
        insert_radius_mm=context.get('tool_radius', 0.8),
        tool_overhang_mm=context.get('tool_overhang', 30.0),
        is_coolant_used=context.get('is_coolant_used', True)
    )

    # Геометрия
    geometry = Geometry(
        diameter_start_mm=context.get('diameter_start', 100.0),
        diameter_end_mm=context.get('diameter_end', 90.0),
        length_mm=context.get('length', 50.0),
        is_external=context.get('is_external', True)
    )

    return CuttingCalculator(limits, material, tool, geometry)


def validate_recommendation_against_limits(
        recommendation: Dict[str, Any],
        limits: CuttingLimits
) -> List[str]:
    """
    Проверить рекомендацию на соответствие ограничениям.
    Возвращает список предупреждений.
    """
    warnings = []

    # Проверка глубины резания
    ap = recommendation.get('ap', 0)
    if ap > limits.max_ap_by_tool_mm:
        warnings.append(f"Глубина резания {ap} мм превышает ограничение инструмента {limits.max_ap_by_tool_mm} мм")

    if ap > 6:  # абсолютный максимум для токарки
        warnings.append(f"Глубина резания {ap} мм превышает типичные значения (2-6 мм)")

    # Проверка подачи
    feed = recommendation.get('feed', 0)
    if feed > limits.max_feed_by_tool_mm_rev:
        warnings.append(f"Подача {feed} мм/об превышает ограничение инструмента {limits.max_feed_by_tool_mm_rev} мм/об")

    # Проверка мощности
    power = recommendation.get('power_kw', 0)
    if power > limits.max_power_kw:
        warnings.append(f"Требуемая мощность {power} кВт превышает мощность станка {limits.max_power_kw} кВт")

    # Проверка количества проходов
    total_passes = recommendation.get('total_passes', 1)
    if total_passes > 20:
        warnings.append(f"{total_passes} проходов - слишком много для практической работы")

    if total_passes < 1:
        warnings.append("Нулевое количество проходов")

    return warnings


def format_recommendation_for_user(recommendation: Dict[str, Any]) -> str:
    """
    Форматировать рекомендацию для показа пользователю.
    """
    lines = []

    lines.append("📊 **Рекомендация по режимам резания:**")
    lines.append("")

    # Основные параметры
    lines.append(f"• Скорость резания: {recommendation['vc']} м/мин")
    lines.append(f"• Обороты шпинделя: {recommendation['rpm']} об/мин")
    lines.append(f"• Подача: {recommendation['feed']} мм/об")
    lines.append(f"• Глубина резания: {recommendation['ap']} мм")
    lines.append(f"• Расчетная мощность: {recommendation['power_kw']} кВт")

    # Стратегия проходов
    strategy = recommendation.get('passes_strategy', {})
    if strategy:
        lines.append("")
        lines.append(f"• Стратегия: {strategy.get('operation_type', 'roughing')}")
        lines.append(f"• Количество проходов: {strategy.get('total_passes', 1)}")
        lines.append(f"• Общий припуск: {strategy.get('total_stock_mm', 0):.1f} мм на сторону")

    # Предупреждения
    warnings = recommendation.get('warnings', [])
    if warnings:
        lines.append("")
        lines.append("⚠️ **Обратите внимание:**")
        for warning in warnings:
            lines.append(f"• {warning}")

    return "\n".join(lines)


# ============================================================================
# ТЕСТИРОВАНИЕ (пример использования)
# ============================================================================

if __name__ == "__main__":
    # Пример 1: Стандартная токарная обработка стали
    print("=" * 60)
    print("Пример 1: Токарная обработка стали")
    print("=" * 60)

    limits = CuttingLimits(max_power_kw=15.0)
    material = MaterialProperties(material_type='steel', hardness_hb=200)
    tool = ToolProperties(insert_material='carbide')
    geometry = Geometry(diameter_start_mm=400, diameter_end_mm=200, length_mm=100)

    calc = CuttingCalculator(limits, material, tool, geometry)

    rec = calc.get_recommendation('roughing')

    print(format_recommendation_for_user(rec))

    # Пример 2: Алюминий с большим припуском
    print("\n" + "=" * 60)
    print("Пример 2: Алюминий с большим припуском")
    print("=" * 60)

    limits2 = CuttingLimits(max_power_kw=11.0)
    material2 = MaterialProperties(material_type='aluminum')
    geometry2 = Geometry(diameter_start_mm=100, diameter_end_mm=80, length_mm=50)

    calc2 = CuttingCalculator(limits2, material2, tool, geometry2)

    rec2 = calc2.get_recommendation('roughing')

    print(format_recommendation_for_user(rec2))

    # Пример 3: Проверка на абсурдные значения (как в старом боте)
    print("\n" + "=" * 60)
    print("Пример 3: Проверка на абсурд (старый бот давал 100 мм ap)")
    print("=" * 60)

    geometry3 = Geometry(diameter_start_mm=400, diameter_end_mm=200, length_mm=100)
    calc3 = CuttingCalculator(limits, material, tool, geometry3)

    # Старый бот: ap = (400-200)/2 = 100 мм (АБСУРД!)
    # Наш калькулятор: ap ограничен 4-6 мм
    rec3 = calc3.get_recommendation('roughing')

    print(f"Припуск: {geometry3.stock_per_side_mm} мм на сторону")
    print(f"Старый бот сказал бы: ap = 100 мм (нереально!)")
    print(f"Наш калькулятор говорит: ap = {rec3['ap']} мм")
    print(f"Количество проходов: {rec3['total_passes']} (не 50!)")

    # Альтернативные стратегии
    print("\n" + "=" * 60)
    print("Альтернативные стратегии:")
    print("=" * 60)

    alternatives = calc.get_alternative_recommendations()
    for strat, alt_rec in alternatives.items():
        if 'error' not in alt_rec:
            print(f"\n{strat.upper()}:")
            print(f"  Обороты: {alt_rec.get('rpm', 0)} об/мин")
            print(f"  Подача: {alt_rec.get('feed', 0)} мм/об")
            print(f"  Глубина: {alt_rec.get('ap', 0)} мм")
            print(f"  Проходов: {alt_rec.get('total_passes', 0)}")