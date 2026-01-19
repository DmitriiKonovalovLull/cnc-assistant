"""
validators.py
Проверка инженерной адекватности данных (НЕ пользователя)
День 3 проекта CNC Assistant
"""

from typing import Optional, Dict


# -----------------------------
# Базовые физические пределы
# -----------------------------

MIN_DIAMETER_MM = 0.1
MAX_DIAMETER_MM = 5000

MIN_RPM = 1
MAX_RPM = 50000


# -----------------------------
# Диаметр
# -----------------------------

def diameter_is_reasonable(diameter: float) -> bool:
    """
    Проверяет, имеет ли диаметр физический смысл
    """
    return MIN_DIAMETER_MM <= diameter <= MAX_DIAMETER_MM


# -----------------------------
# Обороты шпинделя
# -----------------------------

def rpm_is_reasonable(
    material: str,
    diameter: float,
    rpm: int,
    machine_limits: Optional[Dict] = None
) -> bool:
    """
    Проверяет:
    - rpm > 0
    - rpm не превышает лимиты станка
    - rpm не абсурден для данного диаметра
    """

    if rpm < MIN_RPM or rpm > MAX_RPM:
        return False

    if not diameter_is_reasonable(diameter):
        return False

    # Ограничения станка (если переданы)
    if machine_limits:
        max_rpm = machine_limits.get("max_rpm")
        if max_rpm and rpm > max_rpm:
            return False

    # Примитивная физика: слишком большой диаметр + большие обороты
    surface_speed = (3.1416 * diameter * rpm) / 1000  # м/мин

    if surface_speed > 2000:  # условный физический потолок
        return False

    return True


# -----------------------------
# Подача
# -----------------------------

def feed_is_reasonable(feed: float) -> bool:
    """
    Проверка подачи (мм/об)
    """
    return 0.001 <= feed <= 5.0


# -----------------------------
# Комплексная проверка решения
# -----------------------------

def validate_user_decision(
    context: Dict,
    user_choice: Dict,
    machine_limits: Optional[Dict] = None
) -> Dict:
    """
    Возвращает НЕ оценку человека,
    а оценку ПРИМЕНИМОСТИ данных
    """

    valid = True
    reasons = []

    diameter = context.get("diameter")
    material = context.get("material")

    rpm = user_choice.get("rpm")
    feed = user_choice.get("feed")

    if rpm is not None:
        if not rpm_is_reasonable(material, diameter, rpm, machine_limits):
            valid = False
            reasons.append("rpm_out_of_physical_bounds")

    if feed is not None:
        if not feed_is_reasonable(feed):
            valid = False
            reasons.append("feed_out_of_bounds")

    return {
        "valid": valid,
        "reasons": reasons
    }
