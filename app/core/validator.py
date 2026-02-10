"""
Валидация ввода пользователя для CNC Assistant.
Архитектурно чистый модуль валидации с разделением данных и логики.
Версия 3.0 с унифицированными проверками и адаптивными допусками.
"""

from typing import Dict, Any, Tuple, Optional, List, Union
from enum import Enum
from dataclasses import dataclass, field
import re
from decimal import Decimal, InvalidOperation
import math


# ============================================================================
# ТИПЫ ДАННЫХ И СТРУКТУРЫ
# ============================================================================

class ValidationLevel(Enum):
    """Уровни строгости валидации."""
    LENIENT = "lenient"  # Минимальная проверка
    STANDARD = "standard"  # Стандартная проверка (по умолчанию)
    STRICT = "strict"  # Строгая проверка
    EXPERT = "expert"  # Экспертная проверка


class ValidationResult:
    """Результат валидации с поддержкой ошибок и предупреждений."""

    def __init__(self, is_valid: bool = True):
        self.is_valid = is_valid
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []

    def add_error(self, field: str, message: str, value: Any = None):
        self.errors.append({'field': field, 'message': message, 'value': value})
        self.is_valid = False

    def add_warning(self, field: str, message: str, value: Any = None):
        self.warnings.append({'field': field, 'message': message, 'value': value})

    def to_dict(self) -> Dict[str, Any]:
        return {
            'is_valid': self.is_valid,
            'errors': self.errors,
            'warnings': self.warnings,
            'has_errors': len(self.errors) > 0,
            'has_warnings': len(self.warnings) > 0
        }


# ============================================================================
# МОДЕЛИ ДАННЫХ (вынесены в отдельные структуры)
# ============================================================================

@dataclass
class MaterialInfo:
    """Информация о материале."""
    name: str
    aliases: List[str]
    difficulty_range: Tuple[float, float]
    typical_speed_range: Tuple[float, float]  # м/мин
    valid_grades: List[str] = field(default_factory=list)
    types: List[str] = field(default_factory=list)


@dataclass
class OperationInfo:
    """Информация об операции."""
    name: str
    aliases: List[str]
    typical_rpm_range: Tuple[float, float]
    typical_diameter_range: Tuple[float, float]
    complexity: float = 1.0


@dataclass
class ModeInfo:
    """Информация о режиме обработки."""
    name: str
    feed_multiplier: float
    speed_multiplier: float
    description: str = ""


@dataclass
class SafetyRange:
    """Безопасный диапазон параметра."""
    min_val: float
    max_val: float
    warning_min: Optional[float] = None
    warning_max: Optional[float] = None


# ============================================================================
# БАЗА ДАННЫХ ДЛЯ ВАЛИДАЦИИ (вынесена, можно загружать из JSON)
# ============================================================================

class ValidationDatabase:
    """База данных для валидации с унифицированным доступом."""

    def __init__(self):
        self._materials: Dict[str, MaterialInfo] = {}
        self._operations: Dict[str, OperationInfo] = {}
        self._modes: Dict[str, ModeInfo] = {}
        self._safety_ranges: Dict[str, SafetyRange] = {}

        self._init_default_data()

    def _init_default_data(self):
        """Инициализация данных по умолчанию."""
        # Материалы
        self.register_material(MaterialInfo(
            name="сталь",
            aliases=["сталь", "steel", "стали", "железо"],
            difficulty_range=(0.8, 1.5),
            typical_speed_range=(50, 300),
            types=["углеродистая", "легированная", "инструментальная"],
            valid_grades=["Ст3", "Ст45", "40Х", "30ХГСА"]
        ))

        self.register_material(MaterialInfo(
            name="алюминий",
            aliases=["алюминий", "aluminum", "ал", "д16"],
            difficulty_range=(0.5, 1.0),
            typical_speed_range=(100, 1000),
            types=["технический", "дюралюминий", "силумин"],
            valid_grades=["АД0", "АД1", "Д16Т"]
        ))

        self.register_material(MaterialInfo(
            name="титан",
            aliases=["титан", "titanium", "тита", "вт"],
            difficulty_range=(1.5, 2.0),
            typical_speed_range=(10, 60),
            types=["чистый", "сплав", "жаропрочный"],
            valid_grades=["ВТ1", "ВТ6", "ВТ8"]
        ))

        self.register_material(MaterialInfo(
            name="нержавейка",
            aliases=["нержавейка", "нерж", "stainless"],
            difficulty_range=(1.2, 1.8),
            typical_speed_range=(30, 100),
            types=["аустенитная", "ферритная", "мартенситная"],
            valid_grades=["12Х18Н10Т", "304", "316", "321"]
        ))

        # Операции
        self.register_operation(OperationInfo(
            name="токарка",
            aliases=["точение", "обтачивание", "токарный"],
            typical_rpm_range=(50, 5000),
            typical_diameter_range=(0.5, 500),
            complexity=1.0
        ))

        self.register_operation(OperationInfo(
            name="фрезерование",
            aliases=["фрезеровка", "фреза", "milling"],
            typical_rpm_range=(500, 15000),
            typical_diameter_range=(1, 100),
            complexity=1.2
        ))

        self.register_operation(OperationInfo(
            name="сверление",
            aliases=["сверло", "отверстие", "drilling"],
            typical_rpm_range=(100, 8000),
            typical_diameter_range=(0.1, 50),
            complexity=0.8
        ))

        # Режимы
        self.register_mode(ModeInfo(
            name="черновой",
            feed_multiplier=1.5,
            speed_multiplier=0.8,
            description="Максимальный съём металла"
        ))

        self.register_mode(ModeInfo(
            name="получистовой",
            feed_multiplier=1.0,
            speed_multiplier=1.0,
            description="Баланс производительности и качества"
        ))

        self.register_mode(ModeInfo(
            name="чистовой",
            feed_multiplier=0.7,
            speed_multiplier=1.2,
            description="Максимальное качество поверхности"
        ))

        # Безопасные диапазоны
        self.register_safety_range("diameter_mm", SafetyRange(0.05, 2000, 0.1, 1500))
        self.register_safety_range("rpm", SafetyRange(10, 30000, 50, 20000))
        self.register_safety_range("cutting_speed_m_min", SafetyRange(1, 2000, 10, 1500))
        self.register_safety_range("feed_mm_per_rev", SafetyRange(0.01, 5.0, 0.05, 3.0))

    def register_material(self, material: MaterialInfo):
        """Зарегистрировать новый материал."""
        self._materials[material.name] = material

    def register_operation(self, operation: OperationInfo):
        """Зарегистрировать новую операцию."""
        self._operations[operation.name] = operation

    def register_mode(self, mode: ModeInfo):
        """Зарегистрировать новый режим."""
        self._modes[mode.name] = mode

    def register_safety_range(self, param_name: str, safety_range: SafetyRange):
        """Зарегистрировать безопасный диапазон параметра."""
        self._safety_ranges[param_name] = safety_range

    def get_material(self, name: str) -> Optional[MaterialInfo]:
        """Получить информацию о материале по имени или алиасу."""
        name_lower = name.lower()

        # Прямое совпадение
        if name_lower in self._materials:
            return self._materials[name_lower]

        # Поиск по алиасам
        for material in self._materials.values():
            if name_lower in material.aliases or any(alias in name_lower for alias in material.aliases):
                return material

        # Поиск по названию в строке
        for material in self._materials.values():
            if material.name in name_lower:
                return material

        return None

    def get_operation(self, name: str) -> Optional[OperationInfo]:
        """Получить информацию об операции по имени или алиасу."""
        name_lower = name.lower()

        if name_lower in self._operations:
            return self._operations[name_lower]

        for operation in self._operations.values():
            if name_lower in operation.aliases or any(alias in name_lower for alias in operation.aliases):
                return operation

        return None

    def get_mode(self, name: str) -> Optional[ModeInfo]:
        """Получить информацию о режиме."""
        name_lower = name.lower()
        return self._modes.get(name_lower)

    def get_safety_range(self, param_name: str) -> Optional[SafetyRange]:
        """Получить безопасный диапазон параметра."""
        return self._safety_ranges.get(param_name)

    @property
    def materials_list(self) -> List[str]:
        """Список поддерживаемых материалов."""
        return list(self._materials.keys())

    @property
    def operations_list(self) -> List[str]:
        """Список поддерживаемых операций."""
        return list(self._operations.keys())

    @property
    def modes_list(self) -> List[str]:
        """Список поддерживаемых режимов."""
        return list(self._modes.keys())


# ============================================================================
# УТИЛИТНЫЕ ФУНКЦИИ
# ============================================================================

def _to_decimal(value: Any) -> Optional[Decimal]:
    """Конвертировать значение в Decimal безопасно."""
    if value is None:
        return None

    try:
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        elif isinstance(value, str):
            cleaned = value.replace(',', '.').strip()
            return Decimal(cleaned)
        elif isinstance(value, Decimal):
            return value
        else:
            return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _calculate_cutting_speed(diameter_mm: float, rpm: float) -> float:
    """Рассчитать скорость резания."""
    return math.pi * diameter_mm * rpm / 1000


def _adaptive_tolerance(value: float, base_tolerance: float = 0.1, min_abs: float = 1.0) -> float:
    """Адаптивный допуск для маленьких значений."""
    return max(base_tolerance * abs(value), min_abs)


# ============================================================================
# ОСНОВНОЙ КЛАСС ВАЛИДАТОРА
# ============================================================================

class Validator:
    """Основной класс валидации с архитектурно чистой структурой."""

    def __init__(self, level: ValidationLevel = ValidationLevel.STANDARD):
        self.level = level
        self.db = ValidationDatabase()

    def validate_material(self, material: str) -> ValidationResult:
        """Валидация материала."""
        result = ValidationResult()

        if not material or not isinstance(material, str):
            result.add_error("material", "Материал должен быть строкой", material)
            return result

        material_info = self.db.get_material(material)
        if not material_info:
            supported = ", ".join(self.db.materials_list)
            result.add_error("material", f"Материал '{material}' не поддерживается", material)
            return result

        # Проверка типа/марки материала для строгих уровней
        if self.level in [ValidationLevel.STRICT, ValidationLevel.EXPERT]:
            has_type_or_grade = False
            material_lower = material.lower()

            # Проверяем тип
            for mat_type in material_info.types:
                if mat_type.lower() in material_lower:
                    has_type_or_grade = True
                    break

            # Проверяем марку
            for grade in material_info.valid_grades:
                if grade.lower() in material_lower.replace(' ', ''):
                    has_type_or_grade = True
                    break

            if not has_type_or_grade:
                result.add_warning("material",
                                   f"Рекомендуется уточнить тип или марку материала {material_info.name}")

        return result

    def validate_operation(self, operation: str) -> ValidationResult:
        """Валидация операции."""
        result = ValidationResult()

        if not operation or not isinstance(operation, str):
            result.add_error("operation", "Операция должна быть строкой", operation)
            return result

        operation_info = self.db.get_operation(operation)
        if not operation_info:
            supported = ", ".join(self.db.operations_list)
            result.add_error("operation", f"Операция '{operation}' не поддерживается", operation)
            return result

        return result

    def validate_mode(self, mode: str) -> ValidationResult:
        """Валидация режима обработки."""
        result = ValidationResult()

        if not mode or not isinstance(mode, str):
            result.add_error("mode", "Режим должен быть строкой", mode)
            return result

        mode_info = self.db.get_mode(mode)
        if not mode_info:
            supported = ", ".join(self.db.modes_list)
            result.add_error("mode", f"Режим '{mode}' не поддерживается", mode)
            return result

        return result

    def validate_number(self, value: Any, param_name: str, safety_range_name: str,
                        context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Универсальная валидация числового параметра."""
        result = ValidationResult()

        # Конвертация
        decimal_value = _to_decimal(value)
        if decimal_value is None:
            result.add_error(param_name, f"Параметр {param_name} должен быть числом", value)
            return result

        float_value = float(decimal_value)

        # Проверка безопасного диапазона
        safety_range = self.db.get_safety_range(safety_range_name)
        if not safety_range:
            result.add_error(param_name, f"Не найден диапазон безопасности для {param_name}", float_value)
            return result

        # Проверка минимума и максимума
        if float_value < safety_range.min_val:
            result.add_error(param_name,
                             f"{param_name} слишком мал (мин. {safety_range.min_val})",
                             float_value)

        elif float_value > safety_range.max_val:
            result.add_error(param_name,
                             f"{param_name} слишком велик (макс. {safety_range.max_val})",
                             float_value)

        # Проверка предупреждений
        if safety_range.warning_min and float_value < safety_range.warning_min:
            result.add_warning(param_name,
                               f"{param_name} очень мал ({float_value})")

        if safety_range.warning_max and float_value > safety_range.warning_max:
            result.add_warning(param_name,
                               f"{param_name} очень велик ({float_value})")

        # Контекстные проверки
        if context:
            # Проверка типичного диапазона для операции
            if 'operation' in context:
                operation_info = self.db.get_operation(context['operation'])
                if operation_info and param_name == 'diameter_mm':
                    if (float_value < operation_info.typical_diameter_range[0] or
                            float_value > operation_info.typical_diameter_range[1]):
                        result.add_warning(param_name,
                                           f"Диаметр {float_value} мм выходит за типичный диапазон для операции")

        return result

    def validate_diameter(self, diameter: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Валидация диаметра."""
        return self.validate_number(diameter, 'diameter_mm', 'diameter_mm', context)

    def validate_rpm(self, rpm: Any, diameter: Optional[float] = None,
                     material: Optional[str] = None) -> ValidationResult:
        """Валидация оборотов с проверкой скорости резания."""
        result = self.validate_number(rpm, 'rpm', 'rpm')

        if not result.is_valid:
            return result

        float_rpm = float(_to_decimal(rpm))

        # Проверка скорости резания если есть диаметр
        if diameter and diameter > 0:
            vc = _calculate_cutting_speed(diameter, float_rpm)

            # Проверка безопасного диапазона Vc
            vc_result = self.validate_number(vc, 'cutting_speed', 'cutting_speed_m_min')
            for error in vc_result.errors:
                result.add_error('rpm', error['message'].replace('cutting_speed', 'скорость резания'), float_rpm)
            for warning in vc_result.warnings:
                result.add_warning('rpm', warning['message'].replace('cutting_speed', 'скорость резания'), float_rpm)

            # Проверка типичной скорости для материала
            if material:
                material_info = self.db.get_material(material)
                if material_info:
                    if vc < material_info.typical_speed_range[0]:
                        result.add_warning('rpm',
                                           f"Низкая скорость резания для {material}: {vc:.1f} м/мин")
                    elif vc > material_info.typical_speed_range[1]:
                        result.add_warning('rpm',
                                           f"Высокая скорость резания для {material}: {vc:.1f} м/мин")

        return result

    def validate_cutting_speed(self, vc: Any, material: Optional[str] = None) -> ValidationResult:
        """Валидация скорости резания."""
        result = self.validate_number(vc, 'cutting_speed', 'cutting_speed_m_min')

        if not result.is_valid:
            return result

        float_vc = float(_to_decimal(vc))

        # Проверка типичной скорости для материала
        if material:
            material_info = self.db.get_material(material)
            if material_info:
                if float_vc < material_info.typical_speed_range[0]:
                    result.add_warning('cutting_speed',
                                       f"Низкая скорость резания для {material}")
                elif float_vc > material_info.typical_speed_range[1]:
                    result.add_warning('cutting_speed',
                                       f"Высокая скорость резания для {material}")

        return result

    def validate_feed(self, feed: Any, operation: Optional[str] = None) -> ValidationResult:
        """Валидация подачи."""
        return self.validate_number(feed, 'feed', 'feed_mm_per_rev')

    def validate_context_consistency(self, context: Dict[str, Any]) -> ValidationResult:
        """Проверка логической согласованности контекста."""
        result = ValidationResult()

        # Проверка соответствия Vc, диаметра и RPM
        if all(k in context for k in ['diameter', 'rpm', 'vc']):
            try:
                diameter = float(_to_decimal(context['diameter']))
                rpm = float(_to_decimal(context['rpm']))
                vc = float(_to_decimal(context['vc']))

                calculated_vc = _calculate_cutting_speed(diameter, rpm)

                # Адаптивный допуск
                tolerance = _adaptive_tolerance(vc, 0.1, 0.5)

                if abs(calculated_vc - vc) > tolerance:
                    result.add_warning('consistency',
                                       f"Небольшое несоответствие параметров: "
                                       f"Vc расчётная={calculated_vc:.1f} м/мин, "
                                       f"Vc введённая={vc:.1f} м/мин")
            except (TypeError, ValueError):
                pass

        # Проверка типичных RPM для операции и диаметра
        if all(k in context for k in ['operation', 'rpm', 'diameter']):
            operation_info = self.db.get_operation(context['operation'])
            if operation_info:
                try:
                    rpm = float(_to_decimal(context['rpm']))
                    if (rpm < operation_info.typical_rpm_range[0] or
                            rpm > operation_info.typical_rpm_range[1]):
                        result.add_warning('rpm',
                                           f"Обороты выходят за типичный диапазон для операции")
                except (TypeError, ValueError):
                    pass

        return result

    def validate_full_context(self, context: Dict[str, Any]) -> ValidationResult:
        """Полная валидация контекста."""
        result = ValidationResult()

        # Валидация обязательных полей
        required_fields = ['material', 'operation', 'mode']
        for field in required_fields:
            if field not in context:
                result.add_error(field, f"Отсутствует обязательное поле: {field}")

        if not result.is_valid:
            return result

        # Валидация отдельных полей
        validators = [
            ('material', lambda: self.validate_material(context['material'])),
            ('operation', lambda: self.validate_operation(context['operation'])),
            ('mode', lambda: self.validate_mode(context['mode'])),
        ]

        # Условные поля
        if 'diameter' in context:
            validators.append(('diameter',
                               lambda: self.validate_diameter(context['diameter'], context)))

        if 'rpm' in context:
            diameter = float(_to_decimal(context.get('diameter', 0))) if 'diameter' in context else None
            validators.append(('rpm',
                               lambda: self.validate_rpm(context['rpm'], diameter, context.get('material'))))

        if 'vc' in context:
            validators.append(('vc',
                               lambda: self.validate_cutting_speed(context['vc'], context.get('material'))))

        if 'feed' in context:
            validators.append(('feed',
                               lambda: self.validate_feed(context['feed'], context.get('operation'))))

        # Выполнение валидаций
        for field_name, validator in validators:
            field_result = validator()
            if not field_result.is_valid:
                for error in field_result.errors:
                    result.add_error(field_name, error['message'], error.get('value'))
            for warning in field_result.warnings:
                result.add_warning(field_name, warning['message'], warning.get('value'))

        # Проверка согласованности
        if result.is_valid:
            consistency_result = self.validate_context_consistency(context)
            for warning in consistency_result.warnings:
                result.add_warning('consistency', warning['message'])

        return result