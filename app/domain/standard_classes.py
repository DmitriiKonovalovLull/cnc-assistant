"""
Классы стандартов - определение типа детали по номеру стандарта.
Это ЖЁСТКИЙ уровень знаний - не зависит от наличия YAML файлов.
"""

from typing import Dict, Any, Optional

# Классы стандартов по номерам
# Формат: "номер_стандарта": {"type": тип_детали, "name": название}
STANDARD_CLASSES: Dict[str, Dict[str, str]] = {
    # ГОСТ - Болты
    "7798": {
        "type": "bolt",
        "name": "Болт с шестигранной головкой класса точности А"
    },
    "7796": {
        "type": "bolt",
        "name": "Болт с шестигранной головкой класса точности В"
    },
    "7805": {
        "type": "bolt",
        "name": "Болт с шестигранной головкой класса точности С"
    },
    
    # ОСТ - Гайки авиационные
    "33056": {
        "type": "nut",
        "name": "Гайка шестигранная высокая самоконтрящаяся"
    },
    "33057": {
        "type": "nut",
        "name": "Гайка шестигранная высокая"
    },
    "33058": {
        "type": "nut",
        "name": "Гайка шестигранная низкая"
    },
    
    # ОСТ - Болты авиационные
    "33059": {
        "type": "bolt",
        "name": "Болт авиационный"
    },
    "33060": {
        "type": "bolt",
        "name": "Болт авиационный"
    },
    
    # ГОСТ - Винты
    "1491": {
        "type": "screw",
        "name": "Винт с цилиндрической головкой"
    },
    "11738": {
        "type": "screw",
        "name": "Винт с полукруглой головкой"
    },
    
    # ОСТ - Винты
    "31102": {
        "type": "screw",
        "name": "Винт с цилиндрической головкой под крестообразный шлиц"
    },
    
    # ГОСТ - Шпильки
    "22032": {
        "type": "stud",
        "name": "Шпилька"
    },
    "22034": {
        "type": "stud",
        "name": "Шпилька"
    },
    
    # ГОСТ - Валы
    "12080": {
        "type": "shaft",
        "name": "Вал"
    },
    
    # ГОСТ - Втулки
    "1139": {
        "type": "bushing",
        "name": "Втулка"
    },
    
    # DIN - Болты
    "912": {
        "type": "bolt",
        "name": "Болт с внутренним шестигранником (DIN 912)"
    },
    "933": {
        "type": "bolt",
        "name": "Болт с резьбой на всю длину (DIN 933)"
    },
    
    # ISO - Болты
    "4014": {
        "type": "bolt",
        "name": "Болт с шестигранной головкой (ISO 4014)"
    },
    "4017": {
        "type": "bolt",
        "name": "Болт с шестигранной головкой (ISO 4017)"
    },
}


def get_standard_class(standard_type: str, standard_number: str) -> Optional[Dict[str, str]]:
    """
    Получить класс стандарта по типу и номеру.
    
    Args:
        standard_type: Тип стандарта (ГОСТ, ОСТ, DIN, ISO)
        standard_number: Номер стандарта (например, "7798-30", "33056-80", "1 33056-80")
        
    Returns:
        Словарь с type и name или None
    """
    if not standard_number:
        return None
    
    # Нормализуем номер: убираем дефисы и пробелы в начале
    normalized = standard_number.strip().replace('-', ' ').replace('_', ' ')
    
    # Для ОСТ может быть формат "1 33056-80" или "1 33056 80" - берем последнюю часть
    # Это основной номер стандарта
    parts = normalized.split()
    
    # Пробуем разные варианты извлечения номера
    candidates = []
    
    # 1. Последняя часть (для "1 33056-80" -> "33056")
    if len(parts) > 1:
        last_part = parts[-1]
        candidates.append(last_part)
    
    # 2. Вторая часть (для "1 33056-80" -> "33056")
    if len(parts) > 1:
        candidates.append(parts[1])
    
    # 3. Первая часть (для "33056-80" -> "33056")
    first_part = parts[0]
    candidates.append(first_part)
    
    # Ищем в классах по приоритету
    for candidate in candidates:
        if candidate in STANDARD_CLASSES:
            return STANDARD_CLASSES[candidate]
    
    return None


def get_part_type_from_standard(standard_type: str, standard_number: str) -> Optional[str]:
    """
    Получить тип детали из стандарта.
    
    Args:
        standard_type: Тип стандарта
        standard_number: Номер стандарта
        
    Returns:
        Тип детали (bolt, screw, stud, shaft, bushing) или None
    """
    standard_class = get_standard_class(standard_type, standard_number)
    if standard_class:
        return standard_class.get('type')
    return None
