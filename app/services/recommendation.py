"""
Сервис расчёта режимов резания.
Rule-based система рекомендаций.
"""
import math
from typing import Dict, Any, Optional

from app.domain.materials import get_recommended_vc, get_material_properties
from app.domain.operations import get_recommended_feed
from app.domain.machines import check_rpm_constraints


def calculate_cutting_modes(
        material: str,
        operation: str,
        mode: str,
        diameter: float,  # мм
        machine_type: str = "universal",
        tool_material: str = "твердый сплав"
) -> Dict[str, Any]:
    """
    Основная функция расчёта режимов резания.

    Returns:
        Dict с рекомендациями
    """
    # 1. Скорость резания (Vc)
    vc = get_recommended_vc(material, operation, mode)

    # 2. Обороты (n)
    # n = (1000 * Vc) / (π * D)
    if diameter > 0:
        rpm = (1000 * vc) / (math.pi * diameter)
        rpm = round(rpm)
    else:
        rpm = 0

    # 3. Проверка ограничений станка
    is_valid, corrected_rpm, message = check_rpm_constraints(rpm, machine_type)
    if not is_valid:
        rpm = corrected_rpm
        # Пересчитываем Vc с учётом ограничений станка
        vc = (math.pi * diameter * rpm) / 1000

    # 4. Подача (f)
    feed = get_recommended_feed(operation, mode, diameter)

    # 5. Глубина резания (ap) - упрощённо
    if mode == "черновой":
        ap = min(diameter / 10, 5)  # не более 5 мм
    elif mode == "получистовой":
        ap = min(diameter / 20, 2)
    else:  # чистовой
        ap = min(diameter / 50, 0.5)

    # 6. Мощность резания (оценочно)
    # P = (kc * ap * f * vc) / 60000
    material_props = get_material_properties(material)
    if material_props:
        kc = material_props.hardness_hb * 3  # удельная сила резания Н/мм²
        power = (kc * ap * feed * vc) / 60000  # кВт
        power = round(power, 2)
    else:
        power = None

    # 7. Собираем результат
    result = {
        "vc": round(vc, 1),  # м/мин
        "rpm": int(rpm),  # об/мин
        "feed": feed,  # мм/об
        "ap": round(ap, 2),  # мм
        "power": power,  # кВт
        "material": material,
        "operation": operation,
        "mode": mode,
        "diameter": diameter,
        "constraints_check": {
            "is_valid": is_valid,
            "message": message,
            "machine_type": machine_type
        }
    }

    return result


def adjust_for_tool_wear(
        base_modes: Dict[str, Any],
        tool_wear_level: float = 0.0
) -> Dict[str, Any]:
    """
    Корректировка режимов в зависимости от износа инструмента.

    Args:
        tool_wear_level: от 0 (новый) до 1 (полностью изношен)
    """
    adjusted = base_modes.copy()

    if tool_wear_level > 0:
        # С изношенным инструментом снижаем скорость
        wear_factor = 1.0 - (tool_wear_level * 0.3)  # до 30% снижения
        adjusted["vc"] = round(adjusted["vc"] * wear_factor, 1)

        # Пересчитываем обороты
        if adjusted["diameter"] > 0:
            adjusted["rpm"] = int((1000 * adjusted["vc"]) / (math.pi * adjusted["diameter"]))

    return adjusted


def calculate_productivity(
        rpm: float,
        feed: float,
        ap: float,
        efficiency: float = 0.8
) -> Dict[str, float]:
    """
    Расчёт производительности.

    Returns:
        dict с метриками производительности
    """
    # Скорость подачи (мм/мин)
    feed_rate = rpm * feed  # мм/мин

    # Объём снимаемого материала (см³/мин)
    # Упрощённо для токарной обработки
    removal_rate = feed_rate * ap * efficiency  # мм³/мин

    return {
        "feed_rate": round(feed_rate, 1),  # мм/мин
        "removal_rate": round(removal_rate / 1000, 2),  # см³/мин
        "efficiency": efficiency
    }