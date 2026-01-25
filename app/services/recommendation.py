"""
Сервис расчёта режимов резания с геометрическим анализом.
Версия 4.2: интегрированный анализ геометрии заготовки и инструмента
"""

import math
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# GEOMETRY ANALYSIS MODULE
# ============================================================================

@dataclass
class WorkpieceGeometry:
    """Геометрия заготовки для анализа."""
    start_diameter: float
    finish_diameter: float
    length: float = 50.0  # предположительная длина обработки в мм

    @property
    def difference(self) -> float:
        """Разница диаметров в мм."""
        return abs(self.start_diameter - self.finish_diameter)

    @property
    def ratio(self) -> float:
        """Отношение диаметров (finish/start)."""
        if self.start_diameter > 0:
            return self.finish_diameter / self.start_diameter
        return 0.0

    @property
    def avg_diameter(self) -> float:
        """Средний диаметр."""
        return (self.start_diameter + self.finish_diameter) / 2

    @property
    def depth_of_cut(self) -> float:
        """Глубина резания (радиальная)."""
        return self.difference / 2

    @property
    def removed_volume_cm3(self) -> float:
        """Объём удаляемого материала в см³."""
        r1 = self.start_diameter / 2
        r2 = self.finish_diameter / 2
        return math.pi * self.length * (r1 ** 2 - r2 ** 2) / 1000


@dataclass
class ToolGeometry:
    """Геометрия инструмента."""
    type: str
    angle: float  # угол при вершине в градусах
    radius: float  # радиус закругления в мм
    material: str
    overhang: float  # вылет инструмента в мм

    @property
    def is_cnc_style(self) -> bool:
        """Является ли геометрия ЧПУ стилем."""
        return self.angle >= 80  # ЧПУ: 80-95°, обычная: 35-55°


@dataclass
class GeometryAnalysis:
    """Результат анализа геометрии."""
    # Основные метрики
    difference_mm: float
    diameter_ratio: float
    removed_volume_cm3: float
    depth_of_cut_mm: float

    # Рекомендации
    suggested_mode: str
    suggested_passes: int
    tool_strength_required: str  # low, medium, high

    # Анализ безопасности
    is_safe: bool
    safety_warnings: List[str]
    geometry_complexity: str  # simple, medium, complex

    # Рекомендации по инструменту
    tool_recommendations: Dict[str, Any]

    def __str__(self) -> str:
        return (f"Geometry Analysis: {self.difference_mm:.1f}mm diff, "
                f"{self.suggested_passes} passes, {self.suggested_mode} mode")


class GeometryAnalyzer:
    """Анализатор геометрии заготовки и инструмента."""

    # Пороги для классификации геометрии
    THRESHOLDS = {
        'SMALL_DIFF': 2.0,  # малая разница диаметров
        'MEDIUM_DIFF': 10.0,  # средняя разница
        'LARGE_DIFF': 30.0,  # большая разница
        'HUGE_DIFF': 50.0,  # очень большая разница

        'SAFE_RATIO': 0.7,  # безопасное отношение диаметров
        'DANGER_RATIO': 0.3,  # опасное отношение

        'SMALL_VOLUME': 10.0,  # малый объём удаления (см³)
        'MEDIUM_VOLUME': 50.0,  # средний объём
        'LARGE_VOLUME': 200.0,  # большой объём
    }

    @staticmethod
    def analyze_workpiece(geometry: WorkpieceGeometry) -> GeometryAnalysis:
        """Полный анализ геометрии заготовки."""
        diff = geometry.difference
        ratio = geometry.ratio
        volume = geometry.removed_volume_cm3

        # Определяем рекомендуемый режим
        suggested_mode = GeometryAnalyzer._suggest_mode_by_difference(diff)

        # Определяем количество проходов
        suggested_passes = GeometryAnalyzer._calculate_required_passes(diff)

        # Определяем требуемую прочность инструмента
        tool_strength = GeometryAnalyzer._determine_tool_strength(diff, ratio)

        # Проверяем безопасность
        is_safe, safety_warnings = GeometryAnalyzer._check_safety(geometry)

        # Определяем сложность обработки
        complexity = GeometryAnalyzer._determine_complexity(diff, ratio, volume)

        # Формируем рекомендации по инструменту
        tool_recommendations = GeometryAnalyzer._generate_tool_recommendations(
            geometry, suggested_mode
        )

        return GeometryAnalysis(
            difference_mm=diff,
            diameter_ratio=ratio,
            removed_volume_cm3=volume,
            depth_of_cut_mm=geometry.depth_of_cut,
            suggested_mode=suggested_mode,
            suggested_passes=suggested_passes,
            tool_strength_required=tool_strength,
            is_safe=is_safe,
            safety_warnings=safety_warnings,
            geometry_complexity=complexity,
            tool_recommendations=tool_recommendations
        )

    @classmethod
    def _suggest_mode_by_difference(cls, difference: float) -> str:
        """Предложить режим обработки на основе разницы диаметров."""
        if difference <= cls.THRESHOLDS['SMALL_DIFF']:
            return "чистовой"
        elif difference <= cls.THRESHOLDS['MEDIUM_DIFF']:
            return "получистовой"
        else:
            return "черновой"

    @classmethod
    def _calculate_required_passes(cls, difference: float) -> int:
        """Рассчитать рекомендуемое количество проходов."""
        depth = difference / 2

        if depth <= 1.0:
            return 1
        elif depth <= 3.0:
            return 2
        elif depth <= 6.0:
            return 3
        elif depth <= 10.0:
            return 4
        else:
            return max(5, math.ceil(depth / 2))

    @classmethod
    def _determine_tool_strength(cls, difference: float, ratio: float) -> str:
        """Определить требуемую прочность инструмента."""
        if difference > cls.THRESHOLDS['LARGE_DIFF'] or ratio < cls.THRESHOLDS['DANGER_RATIO']:
            return "high"
        elif difference > cls.THRESHOLDS['MEDIUM_DIFF']:
            return "medium"
        else:
            return "low"

    @classmethod
    def _check_safety(cls, geometry: WorkpieceGeometry) -> Tuple[bool, List[str]]:
        """Проверить безопасность геометрии."""
        warnings = []
        is_safe = True

        # Проверка отношения диаметров
        if geometry.ratio < cls.THRESHOLDS['DANGER_RATIO']:
            warnings.append("Очень большое съём материала! Высокая нагрузка на инструмент.")
            is_safe = False

        # Проверка глубины резания
        if geometry.depth_of_cut > 10:
            warnings.append("Большая глубина резания. Требуется много проходов.")

        # Проверка объёма удаления
        if geometry.removed_volume_cm3 > cls.THRESHOLDS['LARGE_VOLUME']:
            warnings.append("Большой объём удаляемого материала. Длительная обработка.")

        return is_safe, warnings

    @classmethod
    def _determine_complexity(cls, diff: float, ratio: float, volume: float) -> str:
        """Определить сложность обработки."""
        complexity_score = 0

        if diff > cls.THRESHOLDS['LARGE_DIFF']:
            complexity_score += 2
        elif diff > cls.THRESHOLDS['MEDIUM_DIFF']:
            complexity_score += 1

        if ratio < cls.THRESHOLDS['DANGER_RATIO']:
            complexity_score += 2
        elif ratio < cls.THRESHOLDS['SAFE_RATIO']:
            complexity_score += 1

        if volume > cls.THRESHOLDS['LARGE_VOLUME']:
            complexity_score += 2
        elif volume > cls.THRESHOLDS['MEDIUM_VOLUME']:
            complexity_score += 1

        if complexity_score >= 4:
            return "complex"
        elif complexity_score >= 2:
            return "medium"
        else:
            return "simple"

    @staticmethod
    def analyze_tool_geometry(tool: ToolGeometry, machine_is_cnc: bool) -> Dict[str, Any]:
        """Анализ геометрии инструмента."""
        analysis = {
            'is_compatible': True,
            'warnings': [],
            'recommendations': [],
            'geometry_score': 0.0
        }

        # Проверка совместимости геометрии со станком
        if machine_is_cnc and not tool.is_cnc_style:
            analysis['warnings'].append("Инструмент с геометрией 35° не оптимален для ЧПУ")
            analysis['geometry_score'] -= 0.3
        elif not machine_is_cnc and tool.is_cnc_style:
            analysis['warnings'].append("Инструмент с геометрией 80° не оптимален для обычного станка")
            analysis['geometry_score'] -= 0.3
        else:
            analysis['geometry_score'] += 0.3

        # Проверка радиуса
        if machine_is_cnc:
            if tool.radius < 0.4:
                analysis['warnings'].append("Слишком малый радиус для ЧПУ")
                analysis['geometry_score'] -= 0.2
            elif tool.radius > 1.0:
                analysis['warnings'].append("Большой радиус для ЧПУ - снижение точности")
                analysis['geometry_score'] -= 0.1
        else:
            if tool.radius < 1.2:
                analysis['warnings'].append("Малый радиус для обычной токарки")
                analysis['geometry_score'] -= 0.2
            elif tool.radius > 2.4:
                analysis['warnings'].append("Очень большой радиус")
                analysis['geometry_score'] -= 0.1

        # Проверка вылета
        max_overhang = tool.radius * 100  # эмпирическое правило
        if tool.overhang > max_overhang:
            analysis['warnings'].append(f"Большой вылет инструмента ({tool.overhang}мм)")
            analysis['recommendations'].append("Уменьшите вылет для повышения жесткости")
            analysis['geometry_score'] -= 0.4

        # Расчёт итогового score
        analysis['geometry_score'] = max(0.0, min(1.0, analysis['geometry_score'] + 0.5))

        return analysis

    @staticmethod
    def _generate_tool_recommendations(geometry: WorkpieceGeometry, mode: str) -> Dict[str, Any]:
        """Сгенерировать рекомендации по инструменту."""
        recommendations = {
            'tool_type': 'проходной',
            'tool_angle': 80 if mode != "чистовой" else 55,
            'min_radius': 0.4,
            'max_radius': 1.0 if mode != "чистовой" else 0.8,
            'material_priority': ['твердый сплав', 'керамика', 'CBN'],
            'required_rigidity': 'high' if geometry.depth_of_cut > 5 else 'medium'
        }

        # Корректировка для больших диаметров
        if geometry.avg_diameter > 300:
            recommendations['tool_angle'] = 95
            recommendations['min_radius'] = 0.8
            recommendations['required_rigidity'] = 'very high'

        return recommendations


# ============================================================================
# ENUMS И КЛАССЫ ДАННЫХ ДЛЯ РЕЖИМОВ РЕЗАНИЯ
# ============================================================================

class MachineType(Enum):
    """Тип станка."""
    CNC_LATHE = "чпу_токарка"
    MANUAL_LATHE = "обычная_токарка"
    CNC_MILL = "чпу_фрезер"
    MANUAL_MILL = "обычная_фрезер"
    CNC_DRILL = "чпу_сверление"
    MANUAL_DRILL = "обычное_сверление"


class ProcessingMode(Enum):
    """Режим обработки."""
    ROUGH = "черновой"
    SEMI_FINISH = "получистовой"
    FINISH = "чистовой"


class ToolMaterial(Enum):
    """Материал режущего инструмента."""
    CARBIDE = "твердый сплав"
    HSS = "быстрорежущая сталь"
    CERAMIC = "керамика"
    CBN = "кубический нитрид бора"


@dataclass
class CuttingParameters:
    """Параметры резания с геометрическим анализом."""
    material: str
    operation: str
    mode: str
    machine_type: str

    # Основные параметры
    vc: float  # м/мин - скорость резания
    rpm: int  # об/мин - обороты шпинделя
    feed: float  # мм/об или мм/зуб
    ap: float  # мм - глубина резания

    # Геометрия заготовки
    start_diameter: Optional[float] = None
    finish_diameter: Optional[float] = None
    avg_diameter: Optional[float] = None
    geometry_analysis: Optional[GeometryAnalysis] = None

    # Геометрия инструмента
    tool_diameter: Optional[float] = None
    tool_type: Optional[str] = None
    tool_material: Optional[str] = None
    tool_overhang: Optional[float] = None
    tool_radius: Optional[float] = None
    tool_geometry_analysis: Optional[Dict[str, Any]] = None

    # Расчетные параметры
    power: Optional[float] = None  # кВт - мощность
    feed_rate: Optional[float] = None  # мм/мин - скорость подачи
    removal_rate: Optional[float] = None  # см³/мин - скорость съема материала

    # Флаги и предупреждения
    is_valid: bool = True
    warnings: List[str] = None
    adjustments: Dict[str, Any] = None
    geometry_score: float = 1.0  # оценка геометрии (0-1)

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.adjustments is None:
            self.adjustments = {}


# ============================================================================
# ОСНОВНОЙ КАЛЬКУЛЯТОР С ИНТЕГРИРОВАННЫМ АНАЛИЗОМ ГЕОМЕТРИИ
# ============================================================================

class CuttingModeCalculator:
    """Калькулятор режимов резания с геометрическим анализом."""

    # Константы для расчетов
    PI = math.pi
    MM_TO_M = 1000.0

    # ⚡ ОГРАНИЧЕНИЯ СТАНКОВ ПО ТИПАМ
    MACHINE_LIMITS = {
        MachineType.CNC_LATHE.value: {
            "max_rpm": 5000,
            "min_rpm": 20,
            "max_power": 22,
            "typical_diameters": (10, 800)
        },
        MachineType.MANUAL_LATHE.value: {
            "max_rpm": 1500,
            "min_rpm": 50,
            "max_power": 11,
            "typical_diameters": (20, 800)
        },
        MachineType.CNC_MILL.value: {
            "max_rpm": 8000,
            "min_rpm": 100,
            "max_power": 15,
            "typical_diameters": (1, 300)
        },
        MachineType.CNC_DRILL.value: {
            "max_rpm": 3000,
            "min_rpm": 50,
            "max_power": 7.5,
            "typical_diameters": (1, 100)
        }
    }

    # 🎯 БАЗОВАЯ ТАБЛИЦА СКОРОСТЕЙ РЕЗАНИЯ (Vc) с учётом геометрии
    VC_TABLE = {
        "сталь": {
            "токарка": {
                "черновой": {"чпу": 180, "обычная": 120},
                "получистовой": {"чпу": 220, "обычная": 150},
                "чистовой": {"чпу": 280, "обычная": 180}
            },
            "фрезерование": {
                "черновой": {"чпу": 150, "обычная": 100},
                "получистовой": {"чпу": 180, "обычная": 120},
                "чистовой": {"чпу": 220, "обычная": 150}
            },
            "сверление": {
                "черновой": {"чпу": 30, "обычная": 20},
                "получистовой": {"чпу": 35, "обычная": 25},
                "чистовой": {"чпу": 40, "обычная": 30}
            }
        },
        "алюминий": {
            "токарка": {
                "черновой": {"чпу": 500, "обычная": 350},
                "получистовой": {"чпу": 600, "обычная": 450},
                "чистовой": {"чпу": 800, "обычная": 600}
            },
            "фрезерование": {
                "черновой": {"чпу": 400, "обычная": 300},
                "получистовой": {"чпу": 500, "обычная": 400},
                "чистовой": {"чпу": 700, "обычная": 500}
            },
            "сверление": {
                "черновой": {"чпу": 80, "обычная": 60},
                "получистовой": {"чпу": 100, "обычная": 80},
                "чистовой": {"чпу": 120, "обычная": 100}
            }
        },
        "титан": {
            "токарка": {
                "черновой": {"чпу": 50, "обычная": 35},
                "получистовой": {"чпу": 60, "обычная": 45},
                "чистовой": {"чпу": 75, "обычная": 55}
            },
            "фрезерование": {
                "черновой": {"чпу": 40, "обычная": 30},
                "получистовой": {"чпу": 50, "обычная": 40},
                "чистовой": {"чпу": 60, "обычная": 50}
            },
            "сверление": {
                "черновой": {"чпу": 10, "обычная": 8},
                "получистовой": {"чпу": 12, "обычная": 10},
                "чистовой": {"чпу": 15, "обычная": 12}
            }
        },
        "нержавейка": {
            "токарка": {
                "черновой": {"чпу": 100, "обычная": 70},
                "получистовой": {"чпу": 120, "обычная": 90},
                "чистовой": {"чпу": 150, "обычная": 110}
            },
            "фрезерование": {
                "черновой": {"чпу": 80, "обычная": 60},
                "получистовой": {"чпу": 100, "обычная": 80},
                "чистовой": {"чпу": 130, "обычная": 100}
            },
            "сверление": {
                "черновой": {"чпу": 15, "обычная": 12},
                "получистовой": {"чпу": 18, "обычная": 15},
                "чистовой": {"чпу": 22, "обычная": 18}
            }
        },
        "чугун": {
            "токарка": {
                "черновой": {"чпу": 130, "обычная": 100},
                "получистовой": {"чпу": 150, "обычная": 120},
                "чистовой": {"чпу": 180, "обычная": 140}
            },
            "фрезерование": {
                "черновой": {"чпу": 110, "обычная": 80},
                "получистовой": {"чпу": 130, "обычная": 100},
                "чистовой": {"чпу": 160, "обычная": 120}
            },
            "сверление": {
                "черновой": {"чпу": 20, "обычная": 15},
                "получистовой": {"чпу": 25, "обычная": 20},
                "чистовой": {"чпу": 30, "обычная": 25}
            }
        }
    }

    # 🔧 КОЭФФИЦИЕНТЫ ДЛЯ ГЕОМЕТРИИ
    GEOMETRY_COEFFICIENTS = {
        # Коррекция на сложность геометрии
        "complexity": {
            "simple": 1.0,
            "medium": 0.9,
            "complex": 0.8
        },
        # Коррекция на требуемую прочность инструмента
        "tool_strength": {
            "low": 1.0,
            "medium": 0.9,
            "high": 0.8
        },
        # Коррекция на качество геометрии инструмента
        "tool_geometry": {
            0.8: 1.0,  # отличная геометрия
            0.6: 0.9,  # хорошая
            0.4: 0.8,  # удовлетворительная
            0.2: 0.7,  # плохая
            0.0: 0.6  # очень плохая
        }
    }

    # Коэффициенты для больших диаметров
    LARGE_DIAMETER_COEFF = {
        200: 1.0,
        300: 0.85,
        400: 0.70,
        500: 0.60,
        600: 0.50,
        700: 0.45,
        800: 0.40
    }

    # Коэффициенты для радиуса пластины
    TOOL_RADIUS_COEFF = {
        0.4: 1.1, 0.6: 1.0, 0.8: 0.9, 1.0: 0.8,  # ЧПУ
        1.2: 1.0, 1.6: 0.9, 2.0: 0.8, 2.4: 0.7  # Обычная
    }

    def __init__(self):
        self._cache = {}
        self.geometry_analyzer = GeometryAnalyzer()

    def calculate_cutting_modes(
            self,
            material: str,
            operation: str,
            machine_type: str,
            mode: str,
            # Параметры токарки с геометрией
            start_diameter: Optional[float] = None,
            finish_diameter: Optional[float] = None,
            tool_type: Optional[str] = None,
            tool_material: str = "твердый сплав",
            tool_overhang: Optional[float] = None,
            tool_radius: Optional[float] = None,
            # Параметры фрезерования/сверления
            tool_diameter: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Основная функция расчёта режимов резания с геометрическим анализом.
        """
        cache_key = f"{material}_{operation}_{machine_type}_{mode}_{start_diameter}_{finish_diameter}_{tool_diameter}_{tool_radius}"

        if cache_key in self._cache:
            return self._cache[cache_key].copy()

        try:
            self._validate_inputs(material, operation, machine_type, mode,
                                  start_diameter, finish_diameter, tool_diameter)

            # Анализ геометрии для токарки
            geometry_analysis = None
            tool_geometry_analysis = None
            geometry_score = 1.0

            if operation == "токарка" and start_diameter and finish_diameter:
                # Анализ геометрии заготовки
                workpiece_geom = WorkpieceGeometry(start_diameter, finish_diameter)
                geometry_analysis = self.geometry_analyzer.analyze_workpiece(workpiece_geom)

                # Анализ геометрии инструмента
                if tool_type and tool_radius is not None:
                    machine_is_cnc = "чпу" in machine_type.lower()
                    tool_angle = 80 if machine_is_cnc else 35
                    tool_geom = ToolGeometry(
                        type=tool_type,
                        angle=tool_angle,
                        radius=tool_radius,
                        material=tool_material,
                        overhang=tool_overhang or 50.0
                    )
                    tool_geometry_analysis = self.geometry_analyzer.analyze_tool_geometry(
                        tool_geom, machine_is_cnc
                    )
                    geometry_score = tool_geometry_analysis.get('geometry_score', 1.0)

            if operation == "токарка":
                result = self._calculate_turning_modes(
                    material, machine_type, mode, start_diameter, finish_diameter,
                    tool_type, tool_material, tool_overhang, tool_radius,
                    geometry_analysis, tool_geometry_analysis, geometry_score
                )
            elif operation == "фрезерование":
                result = self._calculate_milling_modes(
                    material, machine_type, mode, tool_diameter
                )
            elif operation in ["сверление", "растачивание"]:
                result = self._calculate_drilling_modes(
                    material, machine_type, mode, tool_diameter
                )
            else:
                raise ValueError(f"Неизвестная операция: {operation}")

            # Добавляем анализ геометрии в результат
            if geometry_analysis:
                result['geometry_analysis'] = {
                    'suggested_passes': geometry_analysis.suggested_passes,
                    'removed_volume': round(geometry_analysis.removed_volume_cm3, 2),
                    'complexity': geometry_analysis.geometry_complexity,
                    'tool_strength': geometry_analysis.tool_strength_required,
                    'difference_mm': round(geometry_analysis.difference_mm, 1),
                    'diameter_ratio': round(geometry_analysis.diameter_ratio, 2)
                }
                result['geometry_score'] = geometry_score

                # Добавляем рекомендации из анализа геометрии
                if 'recommendations' not in result:
                    result['recommendations'] = []
                result['recommendations'].extend([
                    f"Рекомендовано проходов: {geometry_analysis.suggested_passes}",
                    f"Сложность обработки: {geometry_analysis.geometry_complexity}"
                ])

            if tool_geometry_analysis:
                result['tool_geometry_analysis'] = tool_geometry_analysis

            self._cache[cache_key] = result.copy()
            return result

        except Exception as e:
            logger.error(f"Ошибка расчета режимов: {e}", exc_info=True)
            return self._get_safe_defaults(
                material, operation, machine_type, mode,
                start_diameter, finish_diameter, tool_diameter, str(e)
            )

    def _calculate_turning_modes(
            self,
            material: str,
            machine_type: str,
            mode: str,
            start_diameter: float,
            finish_diameter: float,
            tool_type: str,
            tool_material: str,
            tool_overhang: float,
            tool_radius: Optional[float],
            geometry_analysis: Optional[GeometryAnalysis],
            tool_geometry_analysis: Optional[Dict[str, Any]],
            geometry_score: float
    ) -> Dict[str, Any]:
        """Расчет режимов для токарной обработки с геометрическим анализом."""
        # Базовые проверки
        if start_diameter <= 0 or finish_diameter <= 0:
            raise ValueError("Диаметры должны быть положительными")
        if finish_diameter >= start_diameter:
            raise ValueError("Конечный диаметр должен быть меньше начального")

        depth_of_cut = (start_diameter - finish_diameter) / 2
        avg_diameter = (start_diameter + finish_diameter) / 2

        # Определяем тип станка
        is_cnc = "чпу" in machine_type.lower()
        machine_key = "чпу" if is_cnc else "обычная"

        # Базовая скорость резания
        base_vc = self._get_base_vc(material, "токарка", mode, machine_key)

        # Коррекции с учетом геометрии
        corrections = self._apply_geometry_corrections(
            base_vc, avg_diameter, tool_material, tool_overhang,
            tool_radius, is_cnc, geometry_analysis, tool_geometry_analysis
        )

        corrected_vc = corrections['corrected_vc']
        adjustments = corrections['adjustments']

        # Расчет оборотов
        calculated_rpm = self._calculate_rpm(corrected_vc, avg_diameter)

        # Проверка ограничений станка
        final_rpm, machine_warnings = self._check_machine_constraints(
            calculated_rpm, machine_type, avg_diameter
        )

        # Пересчет скорости резания
        final_vc = self._recalculate_vc(final_rpm, avg_diameter)

        # Расчет подачи с учетом геометрии
        feed = self._calculate_turning_feed_with_geometry(
            mode, depth_of_cut, material, is_cnc, tool_radius,
            geometry_analysis
        )

        # Расчет остальных параметров
        ap = depth_of_cut
        feed_rate = final_rpm * feed
        removal_rate = (feed_rate * ap * (avg_diameter / 10)) / 1000
        power = self._calculate_power(final_vc, feed, ap, material)

        # Формирование предупреждений
        warnings = machine_warnings.copy()

        # Добавляем предупреждения из анализа геометрии
        if geometry_analysis:
            warnings.extend(geometry_analysis.safety_warnings)
            if geometry_analysis.geometry_complexity == "complex":
                warnings.append("⚠️ Сложная геометрия - требуется особое внимание")

        if tool_geometry_analysis and 'warnings' in tool_geometry_analysis:
            warnings.extend(tool_geometry_analysis['warnings'])

        # Проверка радиуса для типа станка
        if is_cnc and tool_radius and tool_radius > 1.0:
            warnings.append("⚠️ Для ЧПУ рекомендуется радиус пластины 0.4-0.8 мм")
        elif not is_cnc and tool_radius and tool_radius < 1.2:
            warnings.append("⚠️ Для обычной токарки рекомендуется радиус пластины 1.2+ мм")

        # Формирование результата
        result = {
            "material": material,
            "operation": "токарка",
            "machine_type": machine_type,
            "mode": mode,
            "start_diameter": round(start_diameter, 1),
            "finish_diameter": round(finish_diameter, 1),
            "avg_diameter": round(avg_diameter, 1),
            "depth_of_cut": round(depth_of_cut, 2),
            "vc": round(final_vc, 1),
            "rpm": int(final_rpm),
            "feed": round(feed, 3),
            "ap": round(ap, 2),
            "feed_rate": round(feed_rate, 1),
            "removal_rate": round(removal_rate, 2),
            "tool_type": tool_type,
            "tool_material": tool_material,
            "tool_overhang": tool_overhang,
            "tool_radius": tool_radius,
            "power": round(power, 2) if power else None,
            "warnings": warnings,
            "is_valid": True,
            "adjustments": adjustments,
            "geometry_score": geometry_score
        }

        logger.info(f"Рассчитаны режимы токарки: {material}, Ø{start_diameter}→{finish_diameter}мм, "
                    f"геометрия: {geometry_analysis.geometry_complexity if geometry_analysis else 'н/д'}")

        return result

    def _apply_geometry_corrections(
            self,
            base_vc: float,
            avg_diameter: float,
            tool_material: str,
            tool_overhang: Optional[float],
            tool_radius: Optional[float],
            is_cnc: bool,
            geometry_analysis: Optional[GeometryAnalysis],
            tool_geometry_analysis: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Применение коррекций на основе геометрического анализа."""
        adjustments = {}
        corrected_vc = base_vc

        # Коррекция на большие диаметры
        if avg_diameter > 200:
            large_diam_correction = self._get_large_diameter_correction(avg_diameter)
            corrected_vc *= large_diam_correction
            adjustments['large_diameter_correction'] = round(large_diam_correction, 2)

        # Коррекция на материал инструмента
        tool_material_correction = self._get_tool_material_correction(tool_material)
        corrected_vc *= tool_material_correction
        adjustments['tool_material_correction'] = round(tool_material_correction, 2)

        # Коррекция на вылет инструмента
        if tool_overhang:
            overhang_correction = self._get_overhang_correction(tool_overhang, avg_diameter)
            corrected_vc *= overhang_correction
            adjustments['overhang_correction'] = round(overhang_correction, 2)

        # Коррекция на радиус пластины
        if tool_radius is not None:
            radius_correction = self._get_tool_radius_correction(tool_radius, is_cnc)
            corrected_vc *= radius_correction
            adjustments['tool_radius_correction'] = round(radius_correction, 2)

        # Коррекция на сложность геометрии
        if geometry_analysis:
            complexity_correction = self.GEOMETRY_COEFFICIENTS['complexity'].get(
                geometry_analysis.geometry_complexity, 1.0
            )
            corrected_vc *= complexity_correction
            adjustments['complexity_correction'] = round(complexity_correction, 2)

            # Коррекция на требуемую прочность
            strength_correction = self.GEOMETRY_COEFFICIENTS['tool_strength'].get(
                geometry_analysis.tool_strength_required, 1.0
            )
            corrected_vc *= strength_correction
            adjustments['strength_correction'] = round(strength_correction, 2)

        # Коррекция на качество геометрии инструмента
        if tool_geometry_analysis and 'geometry_score' in tool_geometry_analysis:
            score = tool_geometry_analysis['geometry_score']
            # Округляем score до ближайшего ключа
            rounded_score = round(score * 5) / 5
            geometry_correction = self.GEOMETRY_COEFFICIENTS['tool_geometry'].get(
                rounded_score, 1.0
            )
            corrected_vc *= geometry_correction
            adjustments['tool_geometry_correction'] = round(geometry_correction, 2)

        adjustments['total_correction'] = round(corrected_vc / base_vc, 2)

        return {
            'corrected_vc': corrected_vc,
            'adjustments': adjustments
        }

    def _calculate_turning_feed_with_geometry(
            self,
            mode: str,
            depth_of_cut: float,
            material: str,
            is_cnc: bool,
            tool_radius: Optional[float],
            geometry_analysis: Optional[GeometryAnalysis]
    ) -> float:
        """Расчет подачи с учетом геометрического анализа."""
        # Базовая подача
        base_feeds = {
            "черновой": 0.3,
            "получистовой": 0.15,
            "чистовой": 0.08
        }

        feed = base_feeds.get(mode, 0.2)

        # Коррекция на глубину резания
        if depth_of_cut > 3:
            feed *= 0.8

        # Коррекция на материал
        if material.lower() == "алюминий":
            feed *= 1.5
        elif material.lower() == "титан":
            feed *= 0.7

        # Коррекция на тип станка
        if is_cnc:
            feed *= 1.2

        # Коррекция на радиус пластины
        if tool_radius:
            if is_cnc:
                if tool_radius <= 0.6:
                    feed *= 1.1
                elif tool_radius <= 0.8:
                    feed *= 1.0
                else:
                    feed *= 0.9
            else:
                if tool_radius <= 1.6:
                    feed *= 1.0
                elif tool_radius <= 2.0:
                    feed *= 0.9
                else:
                    feed *= 0.8

        # Коррекция на сложность геометрии
        if geometry_analysis and geometry_analysis.geometry_complexity == "complex":
            feed *= 0.7  # Уменьшаем подачу для сложной геометрии

        return max(feed, 0.05)

    def _validate_inputs(
            self,
            material: str,
            operation: str,
            machine_type: str,
            mode: str,
            start_diameter: Optional[float],
            finish_diameter: Optional[float],
            tool_diameter: Optional[float]
    ):
        """Валидация входных параметров."""
        valid_materials = ["сталь", "алюминий", "титан", "нержавейка", "чугун"]
        if material.lower() not in valid_materials:
            raise ValueError(f"Материал должен быть одним из: {valid_materials}")

        valid_operations = ["токарка", "фрезерование", "сверление", "растачивание"]
        if operation.lower() not in valid_operations:
            raise ValueError(f"Операция должна быть одной из: {valid_operations}")

        valid_modes = ["черновой", "получистовой", "чистовой"]
        if mode.lower() not in valid_modes:
            raise ValueError(f"Режим должен быть одним из: {valid_modes}")

        # Проверка диаметров для токарки
        if operation == "токарка":
            if start_diameter is None or finish_diameter is None:
                raise ValueError("Для токарки требуются начальный и конечный диаметры")
            if start_diameter > 800:
                raise ValueError(f"Начальный диаметр не может превышать 800 мм")
            if finish_diameter <= 0:
                raise ValueError("Конечный диаметр должен быть положительным")

        # Проверка диаметра инструмента для фрезерования/сверления
        elif operation in ["фрезерование", "сверление", "растачивание"]:
            if tool_diameter is None or tool_diameter <= 0:
                raise ValueError(f"Для {operation} требуется положительный диаметр инструмента")
            if tool_diameter > 300 and operation == "фрезерование":
                raise ValueError(f"Диаметр фрезы не может превышать 300 мм")

    def _get_base_vc(self, material: str, operation: str, mode: str, machine_key: str) -> float:
        """Получение базовой скорости резания из таблицы."""
        material_lower = material.lower()

        # Приведение к ключам таблицы
        material_key = material_lower
        if "нержавеющая" in material_lower or "нержавейка" in material_lower:
            material_key = "нержавейка"

        operation_key = "токарка" if "токар" in operation.lower() else operation.lower()
        if "фрезер" in operation.lower():
            operation_key = "фрезерование"
        if "сверл" in operation.lower() or "растач" in operation.lower():
            operation_key = "сверление"

        # Получение значения из таблицы
        try:
            vc = self.VC_TABLE[material_key][operation_key][mode][machine_key]
            return float(vc)
        except KeyError:
            logger.warning(f"Не найдено значение Vc для {material_key}/{operation_key}/{mode}/{machine_key}")
            return 100.0  # Значение по умолчанию

    def _get_large_diameter_correction(self, diameter: float) -> float:
        """Коэффициент коррекции для больших диаметров."""
        if diameter <= 200:
            return 1.0

        # Находим ближайший ключ в таблице
        for diam_limit in sorted(self.LARGE_DIAMETER_COEFF.keys()):
            if diameter <= diam_limit:
                return self.LARGE_DIAMETER_COEFF[diam_limit]

        # Если диаметр больше максимального в таблице
        return self.LARGE_DIAMETER_COEFF[max(self.LARGE_DIAMETER_COEFF.keys())]

    def _get_tool_material_correction(self, tool_material: str) -> float:
        """Коэффициент коррекции на материал инструмента."""
        corrections = {
            "твердый сплав": 1.0,
            "быстрорежущая сталь": 0.4,
            "керамика": 1.8,
            "кубический нитрид бора": 2.5,
            "алмаз": 3.0
        }
        return corrections.get(tool_material.lower(), 1.0)

    def _get_tool_radius_correction(self, radius: float, is_cnc: bool) -> float:
        """Коэффициент коррекции на радиус пластины."""
        # Находим ближайший радиус в таблице
        available_radii = list(self.TOOL_RADIUS_COEFF.keys())
        closest_radius = min(available_radii, key=lambda x: abs(x - radius))

        # Для ЧПУ используем только малые радиусы, для обычной - большие
        if is_cnc and closest_radius > 1.0:
            closest_radius = 0.8  # Дефолт для ЧПУ
        elif not is_cnc and closest_radius < 1.2:
            closest_radius = 1.6  # Дефолт для обычной

        return self.TOOL_RADIUS_COEFF.get(closest_radius, 1.0)

    def _get_overhang_correction(self, overhang: float, diameter: float) -> float:
        """Коэффициент коррекции на вылет инструмента."""
        # Нормализованный вылет (отношение вылета к диаметру)
        normalized_overhang = overhang / diameter if diameter > 0 else 0

        if normalized_overhang <= 0.5:
            return 1.0
        elif normalized_overhang <= 1.0:
            return 0.8
        elif normalized_overhang <= 1.5:
            return 0.6
        else:
            return 0.4

    def _calculate_rpm(self, vc: float, diameter: float) -> float:
        """Расчет оборотов: n = (1000 * Vc) / (π * D)."""
        if diameter <= 0:
            return 0

        rpm = (self.MM_TO_M * vc) / (self.PI * diameter)
        return max(rpm, 10)  # Минимум 10 об/мин

    def _check_machine_constraints(
            self,
            calculated_rpm: float,
            machine_type: str,
            diameter: float
    ) -> Tuple[float, list]:
        """Проверка ограничений станка."""
        warnings = []
        final_rpm = calculated_rpm

        # Получаем ограничения для станка
        limits = self.MACHINE_LIMITS.get(machine_type, self.MACHINE_LIMITS[MachineType.CNC_LATHE.value])
        max_rpm = limits["max_rpm"]
        min_rpm = limits["min_rpm"]

        # Проверка максимальных оборотов
        if calculated_rpm > max_rpm:
            warnings.append(f"⚠️ Рассчитанные обороты ({int(calculated_rpm)}) превышают "
                            f"максимальные для станка ({max_rpm}). Ограничено до {max_rpm} об/мин.")
            final_rpm = max_rpm

        # Проверка минимальных оборотов
        if calculated_rpm < min_rpm:
            warnings.append(f"⚠️ Рассчитанные обороты ({int(calculated_rpm)}) меньше "
                            f"минимальных для станка ({min_rpm}). Установлено {min_rpm} об/мин.")
            final_rpm = min_rpm

        # Специальная проверка для больших диаметров
        if diameter > 300 and final_rpm > 500:
            warnings.append("ℹ️ Для больших диаметров (>300 мм) рекомендуется снижать обороты для уменьшения вибраций.")

        return final_rpm, warnings

    def _recalculate_vc(self, rpm: float, diameter: float) -> float:
        """Пересчет скорости резания после корректировки оборотов: Vc = (π * D * n) / 1000."""
        if diameter <= 0:
            return 0

        vc = (self.PI * diameter * rpm) / self.MM_TO_M
        return vc

    def _calculate_milling_modes(
            self,
            material: str,
            machine_type: str,
            mode: str,
            tool_diameter: float
    ) -> Dict[str, Any]:
        """Расчет режимов для фрезерования."""
        is_cnc = "чпу" in machine_type.lower()
        machine_key = "чпу" if is_cnc else "обычная"

        # Базовая скорость резания
        base_vc = self._get_base_vc(material, "фрезерование", mode, machine_key)

        # Расчет оборотов
        calculated_rpm = self._calculate_rpm(base_vc, tool_diameter)

        # Проверка ограничений станка
        final_rpm, machine_warnings = self._check_machine_constraints(
            calculated_rpm, machine_type, tool_diameter
        )

        # Пересчет скорости резания
        final_vc = self._recalculate_vc(final_rpm, tool_diameter)

        # Расчет подачи
        feed_per_tooth = self._calculate_milling_feed_per_tooth(mode, tool_diameter, material)
        teeth_count = 4  # Стандартное количество зубьев
        feed = feed_per_tooth * teeth_count * final_rpm  # мм/мин

        # Расчет остальных параметров
        ap = self._calculate_milling_depth_of_cut(mode, tool_diameter)  # Глубина резания
        removal_rate = (feed * ap * (tool_diameter / 10)) / 1000  # см³/мин
        power = self._calculate_power(final_vc, feed_per_tooth, ap, material)

        result = {
            "material": material,
            "operation": "фрезерование",
            "machine_type": machine_type,
            "mode": mode,
            "tool_diameter": round(tool_diameter, 1),
            "vc": round(final_vc, 1),  # м/мин
            "rpm": int(final_rpm),  # об/мин
            "feed_per_tooth": round(feed_per_tooth, 3),  # мм/зуб
            "feed": round(feed, 1),  # мм/мин
            "ap": round(ap, 2),  # мм
            "teeth_count": teeth_count,
            "removal_rate": round(removal_rate, 2),  # см³/мин
            "power": round(power, 2) if power else None,  # кВт
            "warnings": machine_warnings,
            "is_valid": True
        }

        return result

    def _calculate_milling_feed_per_tooth(self, mode: str, diameter: float, material: str) -> float:
        """Расчет подачи на зуб для фрезерования."""
        base_feeds = {
            "черновой": min(diameter / 100, 0.15),
            "получистовой": min(diameter / 150, 0.1),
            "чистовой": min(diameter / 200, 0.06)
        }

        feed_per_tooth = base_feeds.get(mode, 0.1)

        # Коррекция на материал
        if material.lower() == "алюминий":
            feed_per_tooth *= 1.5
        elif material.lower() == "титан":
            feed_per_tooth *= 0.6

        return max(feed_per_tooth, 0.02)  # Минимум 0.02 мм/зуб

    def _calculate_milling_depth_of_cut(self, mode: str, diameter: float) -> float:
        """Расчет глубины резания для фрезерования."""
        if mode == "черновой":
            return min(diameter * 0.5, 6.0)
        elif mode == "получистовой":
            return min(diameter * 0.3, 3.0)
        else:  # чистовой
            return min(diameter * 0.1, 1.0)

    def _calculate_drilling_modes(
            self,
            material: str,
            machine_type: str,
            mode: str,
            tool_diameter: float
    ) -> Dict[str, Any]:
        """Расчет режимов для сверления/растачивания."""
        is_cnc = "чпу" in machine_type.lower()
        machine_key = "чпу" if is_cnc else "обычная"

        # Базовая скорость резания
        base_vc = self._get_base_vc(material, "сверление", mode, machine_key)

        # Расчет оборотов
        calculated_rpm = self._calculate_rpm(base_vc, tool_diameter)

        # Проверка ограничений станка
        final_rpm, machine_warnings = self._check_machine_constraints(
            calculated_rpm, machine_type, tool_diameter
        )

        # Пересчет скорости резания
        final_vc = self._recalculate_vc(final_rpm, tool_diameter)

        # Расчет подачи
        feed = self._calculate_drilling_feed(mode, tool_diameter, material)
        feed_rate = final_rpm * feed  # мм/мин

        result = {
            "material": material,
            "operation": "сверление",
            "machine_type": machine_type,
            "mode": mode,
            "tool_diameter": round(tool_diameter, 1),
            "vc": round(final_vc, 1),  # м/мин
            "rpm": int(final_rpm),  # об/мин
            "feed": round(feed, 3),  # мм/об
            "feed_rate": round(feed_rate, 1),  # мм/мин
            "warnings": machine_warnings,
            "is_valid": True
        }

        return result

    def _calculate_drilling_feed(self, mode: str, diameter: float, material: str) -> float:
        """Расчет подачи для сверления."""
        base_feeds = {
            "черновой": min(diameter / 50, 0.4),
            "получистовой": min(diameter / 80, 0.25),
            "чистовой": min(diameter / 120, 0.15)
        }

        feed = base_feeds.get(mode, 0.2)

        # Коррекция на материал
        if material.lower() == "алюминий":
            feed *= 1.5
        elif material.lower() == "титан":
            feed *= 0.6

        return max(feed, 0.05)  # Минимум 0.05 мм/об

    def _calculate_power(self, vc: float, feed: float, ap: float, material: str) -> Optional[float]:
        """Расчет требуемой мощности."""
        try:
            # Удельная сила резания (Н/мм²)
            specific_force = {
                "сталь": 2500,
                "алюминий": 800,
                "титан": 3500,
                "нержавейка": 2800,
                "чугун": 1800
            }

            material_lower = material.lower()
            if "нержавеющая" in material_lower or "нержавейка" in material_lower:
                material_key = "нержавейка"
            elif "алюмин" in material_lower:
                material_key = "алюминий"
            elif "титан" in material_lower:
                material_key = "титан"
            elif "чугун" in material_lower:
                material_key = "чугун"
            else:
                material_key = "сталь"

            kc = specific_force.get(material_key, 2000)

            # P = (kc * ap * f * Vc) / 60000 [кВт]
            power = (kc * ap * feed * vc) / 60000

            # КПД станка
            efficiency = 0.8
            power /= efficiency

            return power

        except Exception as e:
            logger.warning(f"Не удалось рассчитать мощность: {e}")
            return None

    def _get_safe_defaults(
            self,
            material: str,
            operation: str,
            machine_type: str,
            mode: str,
            start_diameter: Optional[float],
            finish_diameter: Optional[float],
            tool_diameter: Optional[float],
            error_message: str
    ) -> Dict[str, Any]:
        """Безопасные значения по умолчанию при ошибке."""
        # Безопасные значения в зависимости от операции
        if operation == "токарка" and start_diameter:
            safe_rpm = min(500, max(50, int(2000 / start_diameter)))
        elif operation in ["фрезерование", "сверление"] and tool_diameter:
            safe_rpm = min(1000, max(100, int(3000 / tool_diameter)))
        else:
            safe_rpm = 500

        return {
            "material": material,
            "operation": operation,
            "machine_type": machine_type,
            "mode": mode,
            "start_diameter": start_diameter,
            "finish_diameter": finish_diameter,
            "tool_diameter": tool_diameter,
            "vc": 50.0,
            "rpm": safe_rpm,
            "feed": 0.15,
            "ap": 1.0,
            "feed_rate": safe_rpm * 0.15,
            "removal_rate": (safe_rpm * 0.15 * 1.0) / 1000,
            "power": None,
            "is_valid": False,
            "warnings": [f"⚠️ Ошибка расчета: {error_message}. Используются безопасные значения."],
            "adjustments": {"error": error_message}
        }


# ============================================================================
# ФУНКЦИИ ДЛЯ ИНТЕГРАЦИИ С TELEGRAM БОТОМ
# ============================================================================

def calculate_cutting_modes_turning_for_bot(
        material: str,
        machine_type: str,
        mode: str,
        start_diameter: float,
        finish_diameter: float,
        tool_type: str = "проходной (80°)",
        tool_material: str = "твердый сплав",
        tool_overhang: float = 50.0,
        tool_radius: Optional[float] = None
) -> Dict[str, Any]:
    """
    Упрощенная функция для Telegram бота с геометрическим анализом.
    """
    calculator = CuttingModeCalculator()

    return calculator.calculate_cutting_modes(
        material=material,
        operation="токарка",
        machine_type=machine_type,
        mode=mode,
        start_diameter=start_diameter,
        finish_diameter=finish_diameter,
        tool_type=tool_type,
        tool_material=tool_material,
        tool_overhang=tool_overhang,
        tool_radius=tool_radius
    )


def calculate_cutting_modes_milling_for_bot(
        material: str,
        machine_type: str,
        mode: str,
        tool_diameter: float
) -> Dict[str, Any]:
    """
    Упрощенная функция для Telegram бота.
    """
    calculator = CuttingModeCalculator()

    return calculator.calculate_cutting_modes(
        material=material,
        operation="фрезерование",
        machine_type=machine_type,
        mode=mode,
        tool_diameter=tool_diameter
    )


def calculate_cutting_modes_drilling_for_bot(
        material: str,
        machine_type: str,
        mode: str,
        tool_diameter: float
) -> Dict[str, Any]:
    """
    Упрощенная функция для Telegram бота.
    """
    calculator = CuttingModeCalculator()

    return calculator.calculate_cutting_modes(
        material=material,
        operation="сверление",
        machine_type=machine_type,
        mode=mode,
        tool_diameter=tool_diameter
    )


# Экспорт калькулятора и анализатора
calculator = CuttingModeCalculator()
geometry_analyzer = GeometryAnalyzer()

# ============================================================================
# ТЕСТИРОВАНИЕ С ГЕОМЕТРИЧЕСКИМ АНАЛИЗОМ
# ============================================================================

if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)

    print("\n" + "=" * 60)
    print("ТЕСТ ГЕОМЕТРИЧЕСКОГО АНАЛИЗА И РАСЧЕТА РЕЖИМОВ v4.2")
    print("=" * 60)

    # Тест анализа геометрии
    print("\n🔍 ТЕСТ АНАЛИЗА ГЕОМЕТРИИ ЗАГОТОВКИ")
    workpiece = WorkpieceGeometry(start_diameter=100.0, finish_diameter=90.0)
    analysis = geometry_analyzer.analyze_workpiece(workpiece)

    print(f"Диаметры: {workpiece.start_diameter}→{workpiece.finish_diameter} мм")
    print(f"Разница: {analysis.difference_mm:.1f} мм")
    print(f"Объём удаления: {analysis.removed_volume_cm3:.1f} см³")
    print(f"Рекомендованный режим: {analysis.suggested_mode}")
    print(f"Количество проходов: {analysis.suggested_passes}")
    print(f"Сложность обработки: {analysis.geometry_complexity}")
    print(f"Требуемая прочность инструмента: {analysis.tool_strength_required}")

    if analysis.safety_warnings:
        print("Предупреждения безопасности:")
        for warning in analysis.safety_warnings:
            print(f"  ⚠️ {warning}")

    # Тест анализа геометрии инструмента
    print("\n🔧 ТЕСТ АНАЛИЗА ГЕОМЕТРИИ ИНСТРУМЕНТА")
    tool = ToolGeometry(
        type="проходной (80°)",
        angle=80,
        radius=0.8,
        material="твердый сплав",
        overhang=50.0
    )
    tool_analysis = geometry_analyzer.analyze_tool_geometry(tool, machine_is_cnc=True)

    print(f"Тип инструмента: {tool.type}")
    print(f"Угол: {tool.angle}°, радиус: {tool.radius} мм")
    print(f"Вылет: {tool.overhang} мм")
    print(f"Оценка геометрии: {tool_analysis['geometry_score']:.2f}")

    if tool_analysis['warnings']:
        print("Предупреждения по инструменту:")
        for warning in tool_analysis['warnings']:
            print(f"  ⚠️ {warning}")

    # Тест полного расчёта с геометрическим анализом
    print("\n🎯 ТЕСТ ПОЛНОГО РАСЧЕТА С ГЕОМЕТРИЧЕСКИМ АНАЛИЗОМ")
    result = calculate_cutting_modes_turning_for_bot(
        material="сталь",
        machine_type="чпу_токарка",
        mode="черновой",
        start_diameter=100.0,
        finish_diameter=90.0,
        tool_type="проходной (80°)",
        tool_material="твердый сплав",
        tool_overhang=50.0,
        tool_radius=0.8
    )

    print(f"Материал: {result['material']}")
    print(f"Станок: {result['machine_type']}")
    print(f"Диаметры: {result['start_diameter']}→{result['finish_diameter']} мм")
    print(f"Vc: {result['vc']} м/мин")
    print(f"Обороты: {result['rpm']} об/мин")
    print(f"Подача: {result['feed']} мм/об")

    if 'geometry_analysis' in result:
        print(f"\n📊 Анализ геометрии:")
        for key, value in result['geometry_analysis'].items():
            print(f"  {key}: {value}")

    print(f"\n🎯 Итоговая оценка геометрии: {result.get('geometry_score', 1.0):.2f}")

    if result['warnings']:
        print("\n⚠️ Предупреждения:")
        for warning in result['warnings'][:5]:  # Показываем только первые 5
            print(f"  {warning}")

    print("\n" + "=" * 60)
    print("✅ Тестирование геометрического анализа завершено успешно!")
    print("=" * 60)
