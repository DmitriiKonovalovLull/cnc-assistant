"""
Конечный автомат для управления диалогом.
Отделяет логику диалога от бота.
"""
from enum import Enum
from typing import Dict, Any, Optional, Tuple
import re


class UserState(Enum):
    """Состояния пользователя в диалоге."""
    waiting_material = "waiting_material"
    waiting_operation = "waiting_operation"
    waiting_mode = "waiting_mode"
    waiting_diameter = "waiting_diameter"
    waiting_recommendation = "waiting_recommendation"
    waiting_user_choice = "waiting_user_choice"


# Валидные значения
VALID_MATERIALS = {
    "сталь", "алюминий", "титан", "нержавейка",
    "чугун", "латунь", "медь", "бронза"
}

VALID_OPERATIONS = {
    "токарка", "фрезерование", "сверление",
    "растачивание", "протягивание", "шлифование"
}

VALID_MODES = {
    "черновой", "получистовой", "чистовой"
}


async def get_next_state(
        current_state: Optional[str],
        user_input: str,
        user_data: Dict[str, Any]
) -> Tuple[Optional[UserState], Dict[str, Any]]:
    """
    Определяет следующее состояние на основе текущего и ввода пользователя.

    Returns:
        Tuple[следующее состояние, обновлённые данные]
    """
    updated_data = user_data.copy()

    if not current_state or current_state == UserState.waiting_material.value:
        # Проверяем материал
        if user_input in VALID_MATERIALS:
            updated_data['material'] = user_input
            return UserState.waiting_operation, updated_data

    elif current_state == UserState.waiting_operation.value:
        # Проверяем операцию
        if user_input in VALID_OPERATIONS:
            updated_data['operation'] = user_input
            return UserState.waiting_mode, updated_data

    elif current_state == UserState.waiting_mode.value:
        # Проверяем режим
        if user_input in VALID_MODES:
            updated_data['mode'] = user_input
            return UserState.waiting_diameter, updated_data

    elif current_state == UserState.waiting_diameter.value:
        # Проверяем диаметр
        if re.match(r'^\d+(\.\d+)?$', user_input):
            diameter = float(user_input)
            if 0.1 <= diameter <= 10000:  # разумные пределы
                updated_data['diameter'] = diameter
                return UserState.waiting_recommendation, updated_data

    elif current_state == UserState.waiting_recommendation.value:
        # Ждём рекомендации (переход происходит автоматически)
        pass

    elif current_state == UserState.waiting_user_choice.value:
        # Пользователь вводит свои обороты
        if re.match(r'^\d+(\.\d+)?$', user_input):
            updated_data['user_rpm'] = float(user_input)
            return None, updated_data  # Конец диалога

    # Если не нашли подходящего перехода
    return None, updated_data


async def update_user_data(
        state: UserState,
        user_input: str,
        current_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Обновляет данные пользователя."""
    updated = current_data.copy()

    if state == UserState.waiting_material:
        updated['material'] = user_input

    elif state == UserState.waiting_operation:
        updated['operation'] = user_input

    elif state == UserState.waiting_mode:
        updated['mode'] = user_input

    elif state == UserState.waiting_diameter:
        updated['diameter'] = float(user_input)

    elif state == UserState.waiting_user_choice:
        updated['user_rpm'] = float(user_input)

    return updated