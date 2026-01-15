"""
Rules Engine - двигатель правил резания с таблицами и расчетами.
Основан на данных из cutting_modes.yaml.
"""

import yaml
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import numpy as np
from dataclasses import dataclass


@dataclass
class CuttingParameters:
    """Параметры резания."""
    cutting_speed: float  # м/мин
    feed_per_tooth: float  # мм/зуб (фрезер) или мм/об (токар)
    depth_of_cut: float  # мм
    spindle_speed: Optional[float] = None  # об/мин
    feed_rate: Optional[float] = None  # мм/мин

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cutting_speed": self.cutting_speed,
            "feed_per_tooth": self.feed_per_tooth,
            "depth_of_cut": self.depth_of_cut,
            "spindle_speed": self.spindle_speed,
            "feed_rate": self.feed_rate
        }


class RulesEngine:
    """Движок правил резания."""

    def __init__(self, rules_file: str = "data/rules/cutting_modes.yaml"):
        self.rules_file = Path(rules_file)
        self.rules = self._load_rules()

        # Коэффициенты для разных режимов
        self.mode_coefficients = {
            "roughing": {
                "feed_multiplier": 1.0,
                "speed_multiplier": 0.9,
                "depth_multiplier": 1.0
            },
            "finishing": {
                "feed_multiplier": 0.5,
                "speed_multiplier": 1.2,
                "depth_multiplier": 0.3
            },
            "semi_finishing": {
                "feed_multiplier": 0.7,
                "speed_multiplier": 1.0,
                "depth_multiplier": 0.5
            }
        }

        # Коэффициенты для разных материалов
        self.material_adjustments = {
            "сталь": {"hardness_factor": 1.0, "toughness_factor": 1.0},
            "алюминий": {"hardness_factor": 0.3, "toughness_factor": 0.5},
            "титан": {"hardness_factor": 1.5, "toughness_factor": 2.0},
            "нержавеющая сталь": {"hardness_factor": 1.3, "toughness_factor": 1.8},
            "латунь": {"hardness_factor": 0.5, "toughness_factor": 0.7},
            "медь": {"hardness_factor": 0.6, "toughness_factor": 0.8},
            "чугун": {"hardness_factor": 0.8, "toughness_factor": 0.4}
        }

        # Коэффициенты для операций
        self.operation_adjustments = {
            "токарная": {
                "speed_multiplier": 1.0,
                "feed_multiplier": 1.0,
                "tool_type": "токарный резец"
            },
            "фрезерная": {
                "speed_multiplier": 0.8,
                "feed_multiplier": 0.7,
                "tool_type": "концевая фреза"
            },
            "расточная": {
                "speed_multiplier": 0.7,
                "feed_multiplier": 0.6,
                "tool_type": "расточной резец"
            },
            "сверление": {
                "speed_multiplier": 0.5,
                "feed_multiplier": 0.3,
                "tool_type": "сверло"
            }
        }

    def _load_rules(self) -> Dict[str, Any]:
        """Загружает правила из YAML файла."""
        if not self.rules_file.exists():
            # Возвращаем стандартные правила, если файла нет
            return self._get_default_rules()

        try:
            with open(self.rules_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Ошибка загрузки правил: {e}")
            return self._get_default_rules()

    def _get_default_rules(self) -> Dict[str, Any]:
        """Возвращает правила по умолчанию."""
        return {
            "materials": {
                "сталь": {
                    "name": "Сталь",
                    "cutting_speed": {"min": 80, "max": 150},
                    "feed": {"min": 0.1, "max": 0.3},
                    "depth_of_cut": {"min": 1.0, "max": 3.0}
                },
                "алюминий": {
                    "name": "Алюминий",
                    "cutting_speed": {"min": 200, "max": 400},
                    "feed": {"min": 0.2, "max": 0.4},
                    "depth_of_cut": {"min": 1.5, "max": 4.0}
                },
                "титан": {
                    "name": "Титан",
                    "cutting_speed": {"min": 40, "max": 80},
                    "feed": {"min": 0.08, "max": 0.15},
                    "depth_of_cut": {"min": 0.5, "max": 1.5}
                },
                "нержавеющая сталь": {
                    "name": "Нержавеющая сталь",
                    "cutting_speed": {"min": 60, "max": 100},
                    "feed": {"min": 0.08, "max": 0.2},
                    "depth_of_cut": {"min": 0.8, "max": 2.0}
                },
                "латунь": {
                    "name": "Латунь",
                    "cutting_speed": {"min": 150, "max": 300},
                    "feed": {"min": 0.15, "max": 0.3},
                    "depth_of_cut": {"min": 1.0, "max": 3.0}
                },
                "медь": {
                    "name": "Медь",
                    "cutting_speed": {"min": 120, "max": 250},
                    "feed": {"min": 0.12, "max": 0.25},
                    "depth_of_cut": {"min": 1.0, "max": 2.5}
                },
                "чугун": {
                    "name": "Чугун",
                    "cutting_speed": {"min": 70, "max": 120},
                    "feed": {"min": 0.15, "max": 0.25},
                    "depth_of_cut": {"min": 1.0, "max": 3.0}
                }
            },
            "operations": {
                "токарная": {
                    "name": "Токарная обработка",
                    "default_tool": "токарный резец",
                    "feed_unit": "мм/об"
                },
                "фрезерная": {
                    "name": "Фрезерование",
                    "default_tool": "концевая фреза",
                    "feed_unit": "мм/зуб"
                },
                "расточная": {
                    "name": "Расточка",
                    "default_tool": "расточной резец",
                    "feed_unit": "мм/об"
                },
                "сверление": {
                    "name": "Сверление",
                    "default_tool": "спиральное сверло",
                    "feed_unit": "мм/об"
                }
            },
            "surface_quality": {
                "rough": {
                    "name": "Черновая",
                    "ra_min": 6.3,
                    "ra_max": 12.5,
                    "feed_factor": 1.0,
                    "speed_factor": 0.8
                },
                "finish": {
                    "name": "Чистовая",
                    "ra_min": 0.8,
                    "ra_max": 3.2,
                    "feed_factor": 0.5,
                    "speed_factor": 1.2
                },
                "precision": {
                    "name": "Прецизионная",
                    "ra_min": 0.1,
                    "ra_max": 0.8,
                    "feed_factor": 0.3,
                    "speed_factor": 1.5
                }
            }
        }

    def get_cutting_parameters(self,
                               material: str,
                               operation: str,
                               diameter: float,
                               mode: str = "roughing",
                               surface_roughness: Optional[float] = None,
                               tool_type: Optional[str] = None) -> CuttingParameters:
        """
        Рассчитывает параметры резания.

        Args:
            material: Материал заготовки
            operation: Тип операции
            diameter: Диаметр заготовки (мм)
            mode: Режим обработки (roughing, finishing, semi_finishing)
            surface_roughness: Требуемая шероховатость Ra (мкм)
            tool_type: Тип инструмента

        Returns:
            CuttingParameters: Параметры резания
        """
        # Нормализуем входные данные
        material_lower = material.lower().strip()
        operation_lower = operation.lower().strip()
        mode_lower = mode.lower().strip()

        # Определяем базовые параметры материала
        if material_lower not in self.rules["materials"]:
            # Пытаемся найти похожий материал
            material_lower = self._find_similar_material(material_lower)
            if not material_lower:
                material_lower = "сталь"  # По умолчанию

        material_rules = self.rules["materials"][material_lower]

        # Определяем операцию
        if operation_lower not in self.rules["operations"]:
            operation_lower = "токарная"  # По умолчанию

        # Определяем режим на основе шероховатости
        if surface_roughness:
            mode_lower = self._determine_mode_by_roughness(surface_roughness)

        # Получаем коэффициенты режима
        if mode_lower not in self.mode_coefficients:
            mode_lower = "roughing"

        mode_coeffs = self.mode_coefficients[mode_lower]

        # Получаем поправки материала
        material_adj = self.material_adjustments.get(material_lower,
                                                     self.material_adjustments["сталь"])

        # Получаем поправки операции
        operation_adj = self.operation_adjustments.get(operation_lower,
                                                       self.operation_adjustments["токарная"])

        # Рассчитываем скорость резания
        speed_min = material_rules["cutting_speed"]["min"]
        speed_max = material_rules["cutting_speed"]["max"]

        # Усредняем с учетом режима
        base_speed = (speed_min + speed_max) / 2
        adjusted_speed = base_speed * mode_coeffs["speed_multiplier"]
        adjusted_speed *= operation_adj["speed_multiplier"]

        # Корректируем по твердости материала
        hardness_factor = material_adj["hardness_factor"]
        adjusted_speed *= (1.0 / hardness_factor)  # Чем тверже, тем меньше скорость

        # Рассчитываем подачу
        feed_min = material_rules["feed"]["min"]
        feed_max = material_rules["feed"]["max"]

        base_feed = (feed_min + feed_max) / 2
        adjusted_feed = base_feed * mode_coeffs["feed_multiplier"]
        adjusted_feed *= operation_adj["feed_multiplier"]

        # Рассчитываем глубину резания
        depth_min = material_rules.get("depth_of_cut", {"min": 1.0, "max": 3.0})["min"]
        depth_max = material_rules.get("depth_of_cut", {"min": 1.0, "max": 3.0})["max"]

        base_depth = (depth_min + depth_max) / 2
        adjusted_depth = base_depth * mode_coeffs["depth_multiplier"]

        # Дополнительная корректировка для чистовой обработки
        if mode_lower == "finishing":
            # Уменьшаем глубину для чистовой
            adjusted_depth = min(0.5, adjusted_depth * 0.3)

            # Увеличиваем скорость для лучшей чистоты
            adjusted_speed *= 1.1

            # Уменьшаем подачу для лучшей чистоты
            adjusted_feed *= 0.7

        # Рассчитываем обороты шпинделя
        spindle_speed = None
        if diameter > 0:
            # n = (1000 * V) / (π * D)
            spindle_speed = (1000 * adjusted_speed) / (3.14159 * diameter)

            # Ограничиваем разумными пределами
            if operation_lower == "токарная":
                spindle_speed = min(max(spindle_speed, 200), 3000)
            elif operation_lower == "фрезерная":
                spindle_speed = min(max(spindle_speed, 1000), 10000)

        # Рассчитываем минутную подачу
        feed_rate = None
        if spindle_speed and adjusted_feed:
            if operation_lower == "токарная":
                # Для токарки: F = f * n
                feed_rate = adjusted_feed * spindle_speed
            elif operation_lower == "фрезерная":
                # Для фрезеровки: F = f * z * n (предполагаем 4 зуба)
                feed_rate = adjusted_feed * 4 * spindle_speed

        # Определяем тип инструмента
        if not tool_type:
            tool_type = operation_adj["tool_type"]

        return CuttingParameters(
            cutting_speed=round(adjusted_speed, 1),
            feed_per_tooth=round(adjusted_feed, 3),
            depth_of_cut=round(adjusted_depth, 2),
            spindle_speed=round(spindle_speed, 0) if spindle_speed else None,
            feed_rate=round(feed_rate, 1) if feed_rate else None
        )

    def get_recommendation_text(self,
                                material: str,
                                operation: str,
                                diameter: float,
                                parameters: CuttingParameters,
                                context: Optional[Dict[str, Any]] = None) -> str:
        """Формирует текстовую рекомендацию."""

        # Получаем правила для операции
        operation_rules = self.rules["operations"].get(
            operation.lower(),
            self.rules["operations"]["токарная"]
        )

        feed_unit = operation_rules.get("feed_unit", "мм/об")
        tool_type = operation_rules.get("default_tool", "инструмент")

        # Формируем заголовок
        if context and context.get("has_goal"):
            start_dia = context.get("start_diameter")
            target_dia = context.get("target_diameter")
            roughness = context.get("surface_roughness")

            header = f"🎯 **Рекомендации для {material}:**\n"
            header += f"• Цель: с Ø{start_dia} до Ø{target_dia} мм\n"
            if roughness:
                header += f"• Чистота: Ra {roughness}\n"
            header += f"• Операция: {operation}\n"
        else:
            header = f"⚙️ **Рекомендации для {material} (Ø{diameter} мм):**\n"
            header += f"• Операция: {operation}\n"

        # Основные параметры
        main_params = (
            f"• Скорость резания: **{parameters.cutting_speed} м/мин**\n"
            f"• Подача: **{parameters.feed_per_tooth} {feed_unit}**\n"
            f"• Глубина резания: **{parameters.depth_of_cut} мм**\n"
        )

        # Рассчитанные параметры
        calc_params = ""
        if parameters.spindle_speed:
            calc_params += f"• Обороты шпинделя: **{int(parameters.spindle_speed)} об/мин**\n"
        if parameters.feed_rate:
            calc_params += f"• Минутная подача: **{parameters.feed_rate:.1f} мм/мин**\n"

        # Инструмент
        tool_info = f"• Инструмент: **{tool_type}**\n"

        # Рекомендации
        recommendations = ""

        if material.lower() == "титан":
            recommendations += "🔹 **Важно для титана:**\n"
            recommendations += "   • Обязательно охлаждение\n"
            recommendations += "   • Жёсткая система\n"
            recommendations += "   • Острый инструмент\n"

        elif material.lower() == "алюминий":
            recommendations += "🔹 **Важно для алюминия:**\n"
            recommendations += "   • Острый инструмент\n"
            recommendations += "   • Высокие обороты\n"
            recommendations += "   • Следить за налипанием\n"

        elif material.lower() == "сталь":
            recommendations += "🔹 **Важно для стали:**\n"
            recommendations += "   • Требуется охлаждение\n"
            recommendations += "   • Контроль стружки\n"

        # Предупреждения
        warnings = ""
        if parameters.depth_of_cut > 2.0:
            warnings += "⚠️ **Большая глубина резания:**\n"
            warnings += "   • Проверьте жёсткость системы\n"
            warnings += "   • Убедитесь в мощности станка\n"

        if parameters.cutting_speed > 300:
            warnings += "⚠️ **Высокая скорость резания:**\n"
            warnings += "   • Проверьте стойкость инструмента\n"
            warnings += "   • Усильте охлаждение\n"

        # Собираем всё вместе
        response = header + "\n"
        response += "**Основные параметры:**\n" + main_params + "\n"

        if calc_params:
            response += "**Рассчитанные значения:**\n" + calc_params + "\n"

        response += tool_info + "\n"

        if recommendations:
            response += recommendations + "\n"

        if warnings:
            response += warnings + "\n"

        response += "**Если что-то не подходит — скажите!** Я научусь."

        return response

    def _find_similar_material(self, material: str) -> Optional[str]:
        """Находит похожий материал."""
        material = material.lower()

        # Проверяем частичные совпадения
        for known_material in self.rules["materials"].keys():
            if known_material in material or material in known_material:
                return known_material

        # Проверяем по ключевым словам
        if "тит" in material:
            return "титан"
        elif "алюм" in material or "ал" in material:
            return "алюминий"
        elif "сталь" in material or "steel" in material:
            return "сталь"
        elif "нерж" in material:
            return "нержавеющая сталь"

        return None

    def _determine_mode_by_roughness(self, roughness: float) -> str:
        """Определяет режим обработки по шероховатости."""
        if roughness <= 0.8:
            return "finishing"
        elif roughness <= 3.2:
            return "semi_finishing"
        else:
            return "roughing"

    def validate_parameters(self,
                            material: str,
                            parameters: CuttingParameters) -> List[str]:
        """Проверяет параметры на безопасность."""
        warnings = []

        material_lower = material.lower()
        if material_lower not in self.rules["materials"]:
            warnings.append(f"Неизвестный материал: {material}")
            return warnings

        material_rules = self.rules["materials"][material_lower]

        # Проверяем скорость резания
        speed_min = material_rules["cutting_speed"]["min"]
        speed_max = material_rules["cutting_speed"]["max"]

        if parameters.cutting_speed < speed_min * 0.7:
            warnings.append(f"Скорость резания ({parameters.cutting_speed} м/мин) "
                            f"ниже рекомендуемой ({speed_min}-{speed_max} м/мин)")
        elif parameters.cutting_speed > speed_max * 1.3:
            warnings.append(f"Скорость резания ({parameters.cutting_speed} м/мин) "
                            f"выше рекомендуемой ({speed_min}-{speed_max} м/мин)")

        # Проверяем подачу
        feed_min = material_rules["feed"]["min"]
        feed_max = material_rules["feed"]["max"]

        if parameters.feed_per_tooth < feed_min * 0.5:
            warnings.append(f"Подача ({parameters.feed_per_tooth} мм/зуб) "
                            f"ниже рекомендуемой ({feed_min}-{feed_max} мм/зуб)")
        elif parameters.feed_per_tooth > feed_max * 1.5:
            warnings.append(f"Подача ({parameters.feed_per_tooth} мм/зуб) "
                            f"выше рекомендуемой ({feed_min}-{feed_max} мм/зуб)")

        # Проверяем глубину резания
        if "depth_of_cut" in material_rules:
            depth_min = material_rules["depth_of_cut"]["min"]
            depth_max = material_rules["depth_of_cut"]["max"]

            if parameters.depth_of_cut < depth_min * 0.5:
                warnings.append(f"Глубина резания ({parameters.depth_of_cut} мм) "
                                f"ниже рекомендуемой ({depth_min}-{depth_max} мм)")
            elif parameters.depth_of_cut > depth_max * 1.5:
                warnings.append(f"Глубина резания ({parameters.depth_of_cut} мм) "
                                f"выше рекомендуемой ({depth_min}-{depth_max} мм)")

        return warnings


# Синглтон
_rules_engine = None


def get_rules_engine() -> RulesEngine:
    """Возвращает глобальный экземпляр движка правил."""
    global _rules_engine
    if _rules_engine is None:
        _rules_engine = RulesEngine()
    return _rules_engine


# Тестирование
if __name__ == "__main__":
    print("🧪 Тестирование Rules Engine")
    print("=" * 60)

    engine = RulesEngine()

    test_cases = [
        ("сталь", "токарная", 50, "roughing"),
        ("алюминий", "фрезерная", 20, "finishing"),
        ("титан", "токарная", 100, "roughing", 1.6),
        ("нержавеющая сталь", "токарная", 75, "semi_finishing")
    ]

    for i, test in enumerate(test_cases, 1):
        print(f"\n📝 Тест {i}: {test[:4]}")

        if len(test) == 5:
            material, operation, diameter, mode, roughness = test
            params = engine.get_cutting_parameters(
                material, operation, diameter, mode, roughness
            )
        else:
            material, operation, diameter, mode = test
            params = engine.get_cutting_parameters(
                material, operation, diameter, mode
            )

        print(f"   • Материал: {material}")
        print(f"   • Операция: {operation}")
        print(f"   • Диаметр: Ø{diameter} мм")
        print(f"   • Режим: {mode}")
        print(f"   • Скорость резания: {params.cutting_speed} м/мин")
        print(f"   • Подача: {params.feed_per_tooth} мм/зуб")
        print(f"   • Глубина: {params.depth_of_cut} мм")
        if params.spindle_speed:
            print(f"   • Обороты: {params.spindle_speed:.0f} об/мин")
        if params.feed_rate:
            print(f"   • Минутная подача: {params.feed_rate:.1f} мм/мин")

        # Проверяем валидность
        warnings = engine.validate_parameters(material, params)
        if warnings:
            print(f"   ⚠️  Предупреждения: {warnings}")

    print("\n" + "=" * 60)
    print("✅ Rules Engine готов к работе!")