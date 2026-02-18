"""
Интерактивный CLI модуль для работы со стандартами.
Используется из main.py для режима работы со стандартами.
"""

import sys
import re
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

# Добавляем корневую директорию в путь для импортов
sys.path.insert(0, str(Path(__file__).parent))

from standards.registry.world_registry import WorldStandardRegistry
from standards.equivalence.equivalence_engine import EquivalenceEngine
from standards.api.designation_handler import process_designation
from standards.models import StandardEntity, StandardSource
from standards.normalization.universal_normalizer import UniversalNormalizer

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# Глобальные объекты
_registry = WorldStandardRegistry()
_equivalence_engine = EquivalenceEngine()
_normalizer = UniversalNormalizer()

# Текущие региональные настройки
_current_region: Optional[str] = None
_region_preferences: Dict[str, List[str]] = {
    "RU": ["GOST", "OST", "ISO"],
    "CN": ["GB", "ISO"],
    "EU": ["ISO", "DIN", "EN"],
    "US": ["ANSI", "ASME", "ISO"],
    "JP": ["JIS", "ISO"],
    "GB": ["BS", "ISO"],
    "GLOBAL": ["ISO"],
}


def show_welcome() -> None:
    """Показать приветствие и меню выбора системы."""
    print("\n" + "=" * 60)
    print("  CNC Assistant - Работа со стандартами")
    print("=" * 60)
    print("\nВыберите систему стандартов:")
    print("  1. ГОСТ (Россия/СНГ)")
    print("  2. ISO (международный)")
    print("  3. DIN (Германия)")
    print("  4. GB (Китай)")
    print("  5. JIS (Япония)")
    print("  6. ANSI (США)")
    print("  7. BS (Британия)")
    print("  8. Автоопределение")
    print("  9. Настройки региона")
    print("  0. Выход")
    print()


def get_system_choice() -> Optional[str]:
    """Получить выбор системы от пользователя."""
    choice = input("Ваш выбор (1-9, 0 для выхода): ").strip()
    
    system_map = {
        "1": "GOST",
        "2": "ISO",
        "3": "DIN",
        "4": "GB",
        "5": "JIS",
        "6": "ANSI",
        "7": "BS",
        "8": "AUTO",
        "9": "SETTINGS",
        "0": "EXIT",
    }
    
    return system_map.get(choice)


def auto_detect_system(designation: str) -> Optional[str]:
    """Автоматически определить систему стандартов по обозначению."""
    if not designation:
        return None
    
    designation_upper = designation.upper().strip()
    
    # Метрические резьбы (M, Tr, S) - обычно ГОСТ/ISO/DIN/GB/JIS
    if designation_upper.startswith("M") or designation_upper.startswith("TR") or designation_upper.startswith("S"):
        if _current_region and _current_region in _region_preferences:
            return _region_preferences[_current_region][0]
        return "ISO"
    
    # Дюймовые резьбы (1/4-20, UNC, UNF, NPT) - ANSI/ASME
    if "/" in designation_upper or "UNC" in designation_upper or "UNF" in designation_upper or "NPT" in designation_upper:
        return "ANSI"
    
    # Допуски (H7, g6, IT7) - обычно ISO/GOST/GB/JIS
    if re.match(r'^[A-Z]?\d+[A-Z]?$', designation_upper) or designation_upper.startswith("IT"):
        if _current_region and _current_region in _region_preferences:
            return _region_preferences[_current_region][0]
        return "ISO"
    
    # Шероховатость (Ra, Rz)
    if designation_upper.startswith("RA") or designation_upper.startswith("RZ"):
        if _current_region and _current_region in _region_preferences:
            return _region_preferences[_current_region][0]
        return "ISO"
    
    # Используем нормализатор для определения
    try:
        detected = _normalizer._detect_system(designation)
        if detected:
            return detected
    except:
        pass
    
    # По умолчанию используем региональные предпочтения или ISO
    if _current_region and _current_region in _region_preferences:
        return _region_preferences[_current_region][0]
    
    return "ISO"


def process_with_system(designation: str, system: str) -> Optional[Dict[str, Any]]:
    """Обработать обозначение с указанной системой стандартов."""
    if not designation or not system:
        return None
    
    # Если система AUTO, определяем автоматически
    if system == "AUTO":
        system = auto_detect_system(designation) or "ISO"
        print(f"  → Автоопределена система: {system}")
    
    # Пробуем найти стандарт в указанной системе
    entities = _registry.search_by_designation(designation, system)
    
    if not entities:
        # Если не найдено, пробуем без указания системы
        entities = _registry.search_by_designation(designation)
    
    if not entities:
        return None
    
    # Берем первую найденную сущность
    entity = entities[0]
    
    # Используем designation_handler для получения требований и ограничений
    result = process_designation(designation)
    
    if result:
        result["system"] = system
        result["entity"] = entity
    else:
        # Если handler не вернул результат, создаем базовый
        result = {
            "message": f"Стандарт найден: {designation} ({system})",
            "entity": entity,
            "system": system,
        }
    
    return result


def show_equivalents(designation: str, system: str) -> None:
    """Показать аналоги стандарта в других системах с процентами совпадения."""
    print(f"\n📊 Аналоги стандарта {designation} ({system}):")
    print("-" * 60)
    
    # Ищем аналоги через registry
    equivalents = _registry.find_equivalents(designation, system)
    
    if not equivalents:
        print("  Аналоги не найдены.")
        return
    
    # Группируем по системам и сортируем по уверенности
    equivalents_by_system: Dict[str, List[Dict[str, Any]]] = {}
    for eq in equivalents:
        eq_system = eq.get("system", "UNKNOWN")
        if eq_system not in equivalents_by_system:
            equivalents_by_system[eq_system] = []
        equivalents_by_system[eq_system].append(eq)
    
    # Выводим аналоги
    for eq_system, eq_list in sorted(equivalents_by_system.items()):
        # Берем лучший результат для каждой системы
        best_eq = max(eq_list, key=lambda x: x.get("confidence", 0))
        confidence = best_eq.get("confidence", 0)
        eq_designation = best_eq.get("designation", "")
        note = best_eq.get("note", "")
        
        percentage = int(confidence * 100)
        bar = "█" * (percentage // 5) + "░" * (20 - percentage // 5)
        
        print(f"  {eq_system:6s} {eq_designation:15s} [{bar}] {percentage:3d}%", end="")
        if note:
            print(f"  ({note})")
        else:
            print()


def print_result(result: Dict[str, Any]) -> None:
    """Вывести результат обработки стандарта."""
    print("\n" + "=" * 60)
    
    if "message" in result:
        # Убираем HTML теги для CLI
        message = result["message"]
        message = message.replace("<b>", "").replace("</b>", "")
        message = message.replace("📐", "[Допуск]")
        message = message.replace("🔩", "[Резьба]")
        message = message.replace("📏", "[Шероховатость]")
        print(message)
    
    entity = result.get("entity")
    if entity:
        print(f"\nСистема: {result.get('system', 'UNKNOWN')}")
        print(f"Категория: {entity.category}")
        if entity.raw_designation:
            print(f"Обозначение: {entity.raw_designation}")
    
    constraints = result.get("constraints", [])
    if constraints:
        print("\nОграничения технологии:")
        for constraint in constraints:
            if constraint.description:
                print(f"  • {constraint.description}")
    
    print("=" * 60)


def set_region(region_code: str) -> None:
    """Установить региональные настройки."""
    global _current_region
    
    if region_code.upper() in _region_preferences:
        _current_region = region_code.upper()
        preferred = _region_preferences[_current_region]
        print(f"\n✓ Регион установлен: {_current_region}")
        print(f"  Приоритет систем: {' → '.join(preferred)}")
    else:
        print(f"\n✗ Неизвестный регион: {region_code}")
        print(f"  Доступные: {', '.join(_region_preferences.keys())}")


def show_region_settings() -> None:
    """Показать меню настроек региона."""
    print("\n" + "=" * 60)
    print("  Настройки региона")
    print("=" * 60)
    print("\nВыберите регион:")
    print("  1. RU (Россия/СНГ) - приоритет ГОСТ")
    print("  2. CN (Китай) - приоритет GB")
    print("  3. EU (Европа) - приоритет ISO/DIN")
    print("  4. US (США) - приоритет ANSI")
    print("  5. JP (Япония) - приоритет JIS")
    print("  6. GB (Британия) - приоритет BS")
    print("  7. GLOBAL (Международный) - приоритет ISO")
    print("  0. Назад")
    
    choice = input("\nВаш выбор: ").strip()
    
    region_map = {
        "1": "RU",
        "2": "CN",
        "3": "EU",
        "4": "US",
        "5": "JP",
        "6": "GB",
        "7": "GLOBAL",
    }
    
    region = region_map.get(choice)
    if region:
        set_region(region)
    elif choice == "0":
        return
    else:
        print("Неверный выбор.")


def interactive_mode() -> None:
    """Интерактивный режим работы со стандартами."""
    global _current_region
    
    while True:
        show_welcome()
        choice = get_system_choice()
        
        if choice == "EXIT":
            print("\nДо свидания!")
            break
        
        if choice == "SETTINGS":
            show_region_settings()
            input("\nНажмите Enter для продолжения...")
            continue
        
        if not choice:
            print("Неверный выбор. Попробуйте снова.")
            continue
        
        # Получаем обозначение от пользователя
        designation = input("\nВведите обозначение стандарта: ").strip()
        
        if not designation:
            print("Обозначение не может быть пустым.")
            continue
        
        # Определяем систему
        if choice == "AUTO":
            system = auto_detect_system(designation) or "ISO"
            print(f"\n→ Автоопределена система: {system}")
        else:
            system = choice
        
        # Обрабатываем обозначение
        print(f"\nОбработка: {designation} ({system})...")
        result = process_with_system(designation, system)
        
        if result:
            print_result(result)
            show_equivalents(designation, system)
        else:
            print(f"\n✗ Стандарт '{designation}' не найден в системе {system}.")
            print("  Попробуйте другую систему или используйте автоопределение.")
        
        input("\nНажмите Enter для продолжения...")
