"""
Валидация ввода пользователя.
"""
from typing import Dict, Any, Tuple, Optional


def validate_material(material: str) -> Tuple[bool, Optional[str]]:
    """Проверяет корректность материала."""
    valid_materials = {
        'сталь', 'алюминий', 'титан', 'нержавейка',
        'чугун', 'латунь', 'медь', 'бронза'
    }

    if material.lower() in valid_materials:
        return True, None
    return False, f"Материал '{material}' не поддерживается. Доступные: {', '.join(valid_materials)}"


def validate_operation(operation: str) -> Tuple[bool, Optional[str]]:
    """Проверяет корректность операции."""
    valid_operations = {
        'токарка', 'фрезерование', 'сверление',
        'растачивание', 'протягивание', 'шлифование'
    }

    if operation.lower() in valid_operations:
        return True, None
    return False, f"Операция '{operation}' не поддерживается."


def validate_diameter(diameter: Any) -> Tuple[bool, Optional[str]]:
    """Проверяет корректность диаметра."""
    try:
        d = float(diameter)
        if d <= 0:
            return False, "Диаметр должен быть положительным числом."
        if d > 10000:  # 10 метров - разумный предел
            return False, "Диаметр слишком большой (макс. 10000 мм)."
        return True, None
    except (ValueError, TypeError):
        return False, "Диаметр должен быть числом."


def validate_rpm(rpm: Any) -> Tuple[bool, Optional[str]]:
    """Проверяет корректность оборотов."""
    try:
        r = float(rpm)
        if r <= 0:
            return False, "Обороты должны быть положительными."
        if r > 100000:  # 100к об/мин - разумный предел
            return False, "Слишком высокие обороты."
        return True, None
    except (ValueError, TypeError):
        return False, "Обороты должны быть числом."


def validate_full_context(context: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Проверяет полный контекст на корректность."""
    required_fields = ['material', 'operation', 'mode', 'diameter']

    for field in required_fields:
        if field not in context:
            return False, f"Отсутствует поле: {field}"

    # Проверяем каждое поле
    validators = {
        'material': validate_material,
        'operation': validate_operation,
        'diameter': validate_diameter,
    }

    for field, validator in validators.items():
        if field in context:
            is_valid, error = validator(context[field])
            if not is_valid:
                return False, error

    return True, None