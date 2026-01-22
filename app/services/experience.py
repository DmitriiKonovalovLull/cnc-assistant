"""
Сервис расчёта коэффициента опыта (пассивный сбор).
НЕ оценивает пользователя, а собирает данные для будущего ML.
"""
import numpy as np
from typing import Dict, Any, Optional, Tuple
from datetime import datetime


def calculate_deviation_score(
        user_rpm: float,
        recommended_rpm: float,
        material: Optional[str] = None,
        operation: Optional[str] = None
) -> float:
    """
    Рассчитывает относительное отклонение пользователя от рекомендации.

    Returns:
        От -1.0 (сильное занижение) до +1.0 (сильное завышение)
        0 - точное соответствие
    """
    if recommended_rpm == 0:
        return 0.0

    deviation = (user_rpm - recommended_rpm) / recommended_rpm

    # Ограничиваем диапазон
    deviation = max(min(deviation, 1.0), -1.0)

    return round(deviation, 3)


def calculate_context_aware_score(
        user_rpm: float,
        recommended_rpm: float,
        context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Расчёт с учётом контекста.

    Args:
        context: {
            "material": str,
            "operation": str,
            "diameter": float,
            "machine_type": str,
            "mode": str,
            "previous_decisions": list
        }
    """
    # Базовое отклонение
    base_deviation = calculate_deviation_score(user_rpm, recommended_rpm)

    # Корректировка на сложность материала
    material = context.get("material", "")
    material_difficulty = {
        "алюминий": 0.5,
        "латунь": 0.6,
        "сталь": 1.0,
        "чугун": 1.2,
        "нержавейка": 1.5,
        "титан": 1.8,
    }.get(material, 1.0)

    # Корректировка на операцию
    operation = context.get("operation", "")
    operation_complexity = {
        "токарка": 1.0,
        "фрезерование": 1.2,
        "сверление": 0.8,
        "растачивание": 1.3,
    }.get(operation, 1.0)

    # Комбинированный коэффициент сложности
    complexity = material_difficulty * operation_complexity

    # Взвешенное отклонение (чем сложнее, тем меньше штраф за отклонение)
    weighted_deviation = base_deviation / complexity if complexity > 0 else base_deviation

    # Определение стратегии
    strategy = "adaptive"
    if abs(base_deviation) < 0.1:
        strategy = "precise"
    elif base_deviation > 0.3:
        strategy = "aggressive"
    elif base_deviation < -0.3:
        strategy = "conservative"

    # Определение предполагаемого типа станка по стратегии
    machine_type = "unknown"
    if strategy == "aggressive" and user_rpm > 3000:
        machine_type = "high_speed_cnc"
    elif strategy == "conservative" and user_rpm < 1000:
        machine_type = "universal"
    elif strategy == "precise":
        machine_type = "cnc_precise"

    result = {
        "base_deviation": base_deviation,
        "weighted_deviation": weighted_deviation,
        "complexity_factor": complexity,
        "strategy": strategy,
        "inferred_machine": machine_type,
        "context_snapshot": {
            "material": material,
            "operation": operation,
            "diameter": context.get("diameter"),
            "mode": context.get("mode"),
        }
    }

    return result


def calculate_consistency_score(
        user_decisions: list,
        time_window_days: int = 30
) -> Optional[float]:
    """
    Оценка согласованности решений пользователя.

    Args:
        user_decisions: список dict с решениями
        time_window_days: окно для анализа

    Returns:
        Коэффициент согласованности от 0 до 1
        None если недостаточно данных
    """
    if len(user_decisions) < 3:
        return None

    # Извлекаем отклонения
    deviations = []
    for decision in user_decisions:
        if "deviation_score" in decision:
            deviations.append(decision["deviation_score"])

    if len(deviations) < 2:
        return None

    # Рассчитываем стандартное отклонение (чем меньше, тем согласованнее)
    std_dev = np.std(np.abs(deviations))

    # Преобразуем в шкалу 0-1 (0 - полная согласованность)
    # эмпирическая формула
    consistency = 1.0 / (1.0 + std_dev * 5)

    return round(consistency, 3)


def generate_learning_features(
        interaction_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Генерация фич для будущего ML обучения.
    """
    features = {
        # Базовые фичи
        "material": interaction_data.get("material"),
        "operation": interaction_data.get("operation"),
        "diameter": interaction_data.get("diameter"),
        "mode": interaction_data.get("mode"),

        # Режимы
        "recommended_rpm": interaction_data.get("recommended_rpm"),
        "recommended_vc": interaction_data.get("recommended_vc"),
        "user_rpm": interaction_data.get("user_rpm"),

        # Отклонения
        "deviation_abs": abs(interaction_data.get("user_rpm", 0) - interaction_data.get("recommended_rpm", 0)),
        "deviation_rel": interaction_data.get("deviation_score", 0),

        # Контекстные
        "is_titanium": 1 if interaction_data.get("material") == "титан" else 0,
        "is_aluminum": 1 if interaction_data.get("material") == "алюминий" else 0,
        "is_turning": 1 if interaction_data.get("operation") == "токарка" else 0,
        "is_finishing": 1 if interaction_data.get("mode") == "чистовой" else 0,

        # Геометрия
        "diameter_category": categorize_diameter(interaction_data.get("diameter", 0)),

        # Время (для временных рядов)
        "timestamp": datetime.now().isoformat(),

        # Мета-информация
        "source": interaction_data.get("context", {}).get("source", "telegram"),
    }

    return features


def categorize_diameter(diameter: float) -> str:
    """Категоризация диаметра."""
    if diameter < 10:
        return "small"
    elif diameter < 50:
        return "medium"
    elif diameter < 200:
        return "large"
    else:
        return "xlarge"