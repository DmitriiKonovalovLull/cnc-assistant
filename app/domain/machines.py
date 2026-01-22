"""
Модель станков с ограничениями.
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class Machine:
    """Модель станка."""
    name: str
    type: str  # "CNC", "универсальный", "специальный"
    max_rpm: float  # максимальные обороты
    max_power: float  # мощность, кВт
    rigidity_class: str  # класс жёсткости

    # Ограничения
    constraints: Dict[str, Any]


# База станков (можно расширять)
MACHINES_DB = {
    "universal": Machine(
        name="Универсальный токарный",
        type="универсальный",
        max_rpm=2000,
        max_power=10,
        rigidity_class="medium",
        constraints={
            "min_rpm": 50,
            "feed_steps": True,  # ступенчатая подача
        }
    ),

    "cnc_lathe": Machine(
        name="Токарный CNC",
        type="CNC",
        max_rpm=5000,
        max_power=15,
        rigidity_class="high",
        constraints={
            "min_rpm": 10,
            "continuous_control": True,
        }
    ),

    "machining_center": Machine(
        name="Обрабатывающий центр",
        type="CNC",
        max_rpm=10000,
        max_power=20,
        rigidity_class="very_high",
        constraints={
            "min_rpm": 100,
            "high_speed": True,
        }
    ),
}


def get_machine_constraints(machine_type: str) -> Dict[str, Any]:
    """Получить ограничения станка."""
    machine = MACHINES_DB.get(machine_type.lower())
    if machine:
        return machine.constraints
    return {}


def check_rpm_constraints(
        calculated_rpm: float,
        machine_type: str
) -> tuple:
    """
    Проверяет, укладываются ли обороты в ограничения станка.
    Возвращает (is_valid, corrected_rpm, message)
    """
    machine = MACHINES_DB.get(machine_type.lower())

    if not machine:
        # Если станок неизвестен, принимаем как есть
        return True, calculated_rpm, "Станок неизвестен, ограничения не проверены"

    # Проверка максимальных оборотов
    if calculated_rpm > machine.max_rpm:
        return False, machine.max_rpm, f"Обороты превышают максимум станка ({machine.max_rpm} об/мин)"

    # Проверка минимальных оборотов
    min_rpm = machine.constraints.get("min_rpm", 0)
    if calculated_rpm < min_rpm:
        return False, min_rpm, f"Обороты ниже минимума станка ({min_rpm} об/мин)"

    return True, calculated_rpm, "OK"


def estimate_machine_type_by_strategy(
        user_rpm: float,
        recommended_rpm: float,
        deviation: float
) -> str:
    """
    Пытается определить тип станка по стратегии оператора.
    """
    if deviation > 0.5:  # Сильное отклонение вверх
        return "high_speed_cnc"  # Возможно высокоскоростной

    elif deviation < -0.5:  # Сильное отклонение вниз
        return "universal"  # Возможно универсальный с ограничениями

    elif abs(user_rpm - recommended_rpm) < 10:  # Почти точно по рекомендации
        return "cnc_modern"  # Современный CNC

    else:
        return "unknown"