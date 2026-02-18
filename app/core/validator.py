"""
Валидация ввода пользователя для CNC Assistant.
Архитектурно чистый модуль валидации с разделением данных и логики.
Версия 3.0 с унифицированными проверками и адаптивными допусками.
"""

from typing import Dict, Any, Tuple, Optional, List, Union, Callable
from enum import Enum
from dataclasses import dataclass, field
from functools import lru_cache
from collections import defaultdict
import re
from decimal import Decimal, InvalidOperation
import math
import hashlib
import json
from datetime import datetime


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
    """База данных для валидации с унифицированным доступом и оптимизированным поиском."""

    def __init__(self):
        self._materials: Dict[str, MaterialInfo] = {}
        self._operations: Dict[str, OperationInfo] = {}
        self._modes: Dict[str, ModeInfo] = {}
        self._safety_ranges: Dict[str, SafetyRange] = {}
        
        # Индекс алиасов для быстрого поиска
        self._alias_index: Dict[str, str] = {}  # alias -> material_name

        self._init_default_data()
        self._build_alias_index()

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
    
    def _build_alias_index(self):
        """Построить индекс алиасов для быстрого поиска."""
        self._alias_index.clear()
        for material_name, material in self._materials.items():
            for alias in material.aliases:
                self._alias_index[alias.lower()] = material_name

    def get_material(self, name: str) -> Optional[MaterialInfo]:
        """
        Получить информацию о материале по имени или алиасу.
        Оптимизированная версия с индексом алиасов.
        """
        name_lower = name.lower()

        # Прямое совпадение
        if name_lower in self._materials:
            return self._materials[name_lower]

        # Поиск по индексу алиасов (быстро)
        if name_lower in self._alias_index:
            material_name = self._alias_index[name_lower]
            return self._materials[material_name]
        
        # Поиск подстроки в алиасах (менее эффективно, но нужно для частичных совпадений)
        for alias, material_name in self._alias_index.items():
            if alias in name_lower:
                return self._materials[material_name]
        
        # Поиск по названию в строке
        for material_name, material in self._materials.items():
            if material_name in name_lower:
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
    """
    Рассчитать скорость резания с защитой от переполнения.
    
    Args:
        diameter_mm: Диаметр в мм
        rpm: Обороты в об/мин
        
    Returns:
        Скорость резания в м/мин (0.0 при ошибке)
    """
    # Защита от переполнения
    if diameter_mm > 1e6 or rpm > 1e6:
        return 0.0
    
    # Защита от очень маленьких значений
    if diameter_mm < 1e-6 or rpm < 1e-6:
        return 0.0
    
    try:
        vc = math.pi * diameter_mm * rpm / 1000
        # Проверка на NaN/Inf
        if math.isnan(vc) or math.isinf(vc):
            return 0.0
        return vc
    except OverflowError:
        return 0.0


# ============================================================================
# КОНФИГУРАЦИЯ ДОПУСКОВ
# ============================================================================

class ToleranceConfig:
    """Конфигурация допусков для разных типов параметров."""
    
    # Базовые допуски для разных типов параметров (в процентах)
    BASE_TOLERANCE = {
        'diameter': 0.1,      # 10% для диаметра
        'rpm': 0.15,          # 15% для оборотов
        'cutting_speed': 0.1, # 10% для скорости резания
        'feed': 0.2,          # 20% для подачи
        'depth': 0.15,        # 15% для глубины резания
    }
    
    # Минимальные абсолютные допуски
    MIN_ABSOLUTE = {
        'diameter': 1.0,      # 1 мм
        'rpm': 50,            # 50 об/мин
        'cutting_speed': 1.0, # 1 м/мин
        'feed': 0.05,         # 0.05 мм/об
        'depth': 0.1,         # 0.1 мм
    }
    
    @classmethod
    def get_tolerance(cls, param_type: str, value: float) -> float:
        """
        Получить адаптивный допуск для параметра.
        
        Args:
            param_type: Тип параметра ('diameter', 'rpm', и т.д.)
            value: Значение параметра
            
        Returns:
            Адаптивный допуск
        """
        base = cls.BASE_TOLERANCE.get(param_type, 0.1)
        min_abs = cls.MIN_ABSOLUTE.get(param_type, 1.0)
        
        # Защита от отрицательных и очень маленьких значений
        abs_value = abs(value)
        if abs_value < 1e-6:
            return min_abs
        
        return max(base * abs_value, min_abs)


def _adaptive_tolerance(value: float, base_tolerance: float = 0.1, min_abs: float = 1.0) -> float:
    """
    Адаптивный допуск для маленьких значений с защитой от отрицательных.
    
    Args:
        value: Значение
        base_tolerance: Базовый допуск (в процентах)
        min_abs: Минимальный абсолютный допуск
        
    Returns:
        Адаптивный допуск
    """
    abs_value = abs(value)
    # Защита от очень маленьких значений
    if abs_value < 1e-6:
        return min_abs
    return max(base_tolerance * abs_value, min_abs)


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
        """
        Универсальная валидация числового параметра с проверкой единиц измерения.
        """
        result = ValidationResult()

        # Конвертация
        decimal_value = _to_decimal(value)
        if decimal_value is None:
            result.add_error(param_name, f"Параметр {param_name} должен быть числом", value)
            return result

        float_value = float(decimal_value)
        
        # Проверка на NaN/Inf
        if math.isnan(float_value) or math.isinf(float_value):
            result.add_error(param_name, f"Параметр {param_name} не может быть NaN или бесконечностью", value)
            return result

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

        # Проверка единиц измерения (UnitValidator определен ниже в файле)
        # Выполняется условно, чтобы избежать циклических зависимостей
        try:
            UnitValidator.add_unit_warning(result, param_name, float_value)
        except NameError:
            # UnitValidator еще не определен, пропускаем проверку
            pass

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

    def validate_mutual_relations(self, context: Dict[str, Any]) -> ValidationResult:
        """
        Проверить взаимосвязи между параметрами.
        
        Args:
            context: Контекст с параметрами
            
        Returns:
            Результат валидации взаимосвязей
        """
        result = ValidationResult()
        
        # Глубина резания vs припуск
        if all(k in context for k in ['diameter_start', 'diameter_end', 'ap']):
            try:
                start = float(_to_decimal(context['diameter_start']))
                end = float(_to_decimal(context['diameter_end']))
                ap = float(_to_decimal(context['ap']))
                
                stock_per_side = abs(start - end) / 2
                
                tolerance = ToleranceConfig.get_tolerance('depth', stock_per_side)
                
                if ap > stock_per_side + tolerance:
                    result.add_error('ap',
                        f"Глубина резания ({ap:.2f} мм) больше припуска ({stock_per_side:.2f} мм)")
                elif ap > stock_per_side * 0.9:
                    result.add_warning('ap',
                        f"Глубина резания близка к припуску ({ap:.2f} из {stock_per_side:.2f} мм)")
            except (TypeError, ValueError):
                pass
        
        # Подача vs радиус пластины
        if all(k in context for k in ['tool_radius', 'feed']):
            try:
                radius = float(_to_decimal(context['tool_radius']))
                feed = float(_to_decimal(context['feed']))
                
                if feed > radius * 0.8:
                    result.add_warning('feed',
                        f"Подача ({feed:.3f} мм/об) велика для радиуса пластины {radius:.2f} мм")
            except (TypeError, ValueError):
                pass
        
        return result

    def validate_context_consistency(self, context: Dict[str, Any]) -> ValidationResult:
        """
        Проверка логической согласованности контекста.
        Включает проверку взаимосвязей параметров.
        """
        result = ValidationResult()

        # Проверка соответствия Vc, диаметра и RPM
        if all(k in context for k in ['diameter', 'rpm', 'vc']):
            try:
                diameter = float(_to_decimal(context['diameter']))
                rpm = float(_to_decimal(context['rpm']))
                vc = float(_to_decimal(context['vc']))

                calculated_vc = _calculate_cutting_speed(diameter, rpm)
                
                # Проверка на ошибку расчета
                if calculated_vc == 0.0:
                    result.add_error('consistency', "Не удалось рассчитать скорость резания из диаметра и оборотов")
                else:
                    # Адаптивный допуск (используем конфигурацию)
                    tolerance = ToleranceConfig.get_tolerance('cutting_speed', vc)

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
        
        # Проверка взаимосвязей параметров
        mutual_result = self.validate_mutual_relations(context)
        for error in mutual_result.errors:
            result.add_error(error['field'], error['message'], error.get('value'))
        for warning in mutual_result.warnings:
            result.add_warning(warning['field'], warning['message'], warning.get('value'))

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


# ============================================================================
# ВАЛИДАЦИЯ ЕДИНИЦ ИЗМЕРЕНИЯ
# ============================================================================

class UnitValidator:
    """Валидатор единиц измерения."""
    
    # Ожидаемые диапазоны для разных единиц
    UNIT_RANGES = {
        'feed_mm_per_rev': (0.01, 5.0),     # мм/об
        'feed_mm_per_min': (10, 5000),      # мм/мин
        'rpm': (10, 30000),                  # об/мин
        'cutting_speed_m_min': (1, 2000),    # м/мин
        'cutting_speed_m_per_sec': (0.016, 33.33),  # м/с (примерно 1-2000 м/мин)
    }
    
    @classmethod
    def detect_possible_unit_mismatch(cls, value: float, param_name: str) -> Optional[str]:
        """
        Определить, не перепутал ли пользователь единицы измерения.
        
        Args:
            value: Значение параметра
            param_name: Имя параметра
            
        Returns:
            Предполагаемая единица или None
        """
        if param_name == 'feed' or param_name == 'feed_mm_per_rev':
            # Проверяем, не указана ли подача в мм/мин вместо мм/об
            if cls.UNIT_RANGES['feed_mm_per_min'][0] <= value <= cls.UNIT_RANGES['feed_mm_per_min'][1]:
                return "mm_per_min"
            elif cls.UNIT_RANGES['feed_mm_per_rev'][0] <= value <= cls.UNIT_RANGES['feed_mm_per_rev'][1]:
                return "mm_per_rev"
        
        elif param_name == 'cutting_speed' or param_name == 'vc':
            # Проверяем, не указана ли скорость в м/с вместо м/мин
            if cls.UNIT_RANGES['cutting_speed_m_per_sec'][0] <= value <= cls.UNIT_RANGES['cutting_speed_m_per_sec'][1]:
                return "m_per_sec"
            elif cls.UNIT_RANGES['cutting_speed_m_min'][0] <= value <= cls.UNIT_RANGES['cutting_speed_m_min'][1]:
                return "m_per_min"
        
        return None
    
    @classmethod
    def add_unit_warning(cls, result: ValidationResult, param_name: str, value: float):
        """
        Добавить предупреждение о возможной ошибке в единицах.
        
        Args:
            result: Результат валидации
            param_name: Имя параметра
            value: Значение параметра
        """
        mismatch = cls.detect_possible_unit_mismatch(value, param_name)
        if mismatch:
            warnings = {
                'mm_per_min': "Возможно, вы указали подачу в мм/мин. Обычно подача указывается в мм/об.",
                'm_per_sec': "Возможно, вы указали скорость в м/с. Обычно скорость резания в м/мин."
            }
            result.add_warning(param_name, warnings.get(mismatch, "Проверьте единицы измерения"), value)


# ============================================================================
# ПАКЕТНАЯ ВАЛИДАЦИЯ
# ============================================================================

class BatchValidator:
    """Валидатор для пакетной обработки."""
    
    def __init__(self, validator: Validator):
        """
        Инициализация пакетного валидатора.
        
        Args:
            validator: Базовый валидатор
        """
        self.validator = validator
        self.results: List[Tuple[int, ValidationResult]] = []
    
    def validate_batch(self, contexts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Валидировать пакет контекстов.
        
        Args:
            contexts: Список контекстов для валидации
            
        Returns:
            Статистика валидации
        """
        self.results.clear()
        
        for idx, context in enumerate(contexts):
            result = self.validator.validate_full_context(context)
            self.results.append((idx, result))
        
        valid_count = sum(1 for _, r in self.results if r.is_valid)
        warning_count = sum(1 for _, r in self.results if r.warnings)
        error_count = sum(1 for _, r in self.results if not r.is_valid)
        
        return {
            'total': len(contexts),
            'valid': valid_count,
            'with_warnings': warning_count,
            'with_errors': error_count,
            'success_rate': valid_count / len(contexts) if contexts else 0,
            'details': [
                {
                    'index': idx,
                    'is_valid': r.is_valid,
                    'errors': len(r.errors),
                    'warnings': len(r.warnings)
                }
                for idx, r in self.results
            ]
        }
    
    def get_invalid_indices(self) -> List[int]:
        """Получить индексы невалидных контекстов."""
        return [idx for idx, r in self.results if not r.is_valid]
    
    def get_invalid_contexts(self, contexts: List[Dict]) -> List[Tuple[int, Dict, ValidationResult]]:
        """Получить невалидные контексты с результатами."""
        return [(idx, contexts[idx], r) for idx, r in self.results if not r.is_valid]


# ============================================================================
# ПОЛЬЗОВАТЕЛЬСКИЕ ПРАВИЛА ВАЛИДАЦИИ
# ============================================================================

class ValidationRule:
    """Пользовательское правило валидации."""
    
    def __init__(self, name: str, 
                 condition: Callable[[Dict[str, Any]], bool],
                 error_message: str,
                 severity: str = 'error'):
        """
        Инициализация правила валидации.
        
        Args:
            name: Имя правила
            condition: Функция условия (возвращает True если правило нарушено)
            error_message: Сообщение об ошибке
            severity: Уровень серьезности ('error' или 'warning')
        """
        self.name = name
        self.condition = condition
        self.error_message = error_message
        self.severity = severity
    
    def validate(self, context: Dict[str, Any]) -> Optional[Tuple[str, str]]:
        """
        Применить правило.
        
        Args:
            context: Контекст для проверки
            
        Returns:
            (severity, message) если нарушено, иначе None
        """
        if not self.condition(context):
            return (self.severity, self.error_message)
        return None


class ExtendableValidator(Validator):
    """Валидатор с поддержкой пользовательских правил."""
    
    def __init__(self, level: ValidationLevel = ValidationLevel.STANDARD):
        super().__init__(level)
        self.custom_rules: List[ValidationRule] = []
    
    def add_rule(self, rule: ValidationRule):
        """Добавить пользовательское правило."""
        self.custom_rules.append(rule)
    
    def validate_full_context(self, context: Dict[str, Any]) -> ValidationResult:
        result = super().validate_full_context(context)
        
        # Применяем пользовательские правила
        for rule in self.custom_rules:
            violation = rule.validate(context)
            if violation:
                severity, message = violation
                if severity == 'error':
                    result.add_error(rule.name, message)
                else:
                    result.add_warning(rule.name, message)
        
        return result


# ============================================================================
# КЭШИРОВАНИЕ РЕЗУЛЬТАТОВ ВАЛИДАЦИИ
# ============================================================================

class CachedValidator(Validator):
    """Валидатор с кэшированием результатов."""
    
    def __init__(self, level: ValidationLevel = ValidationLevel.STANDARD, cache_size: int = 1000):
        super().__init__(level)
        self.cache_size = cache_size
    
    def _make_cache_key(self, context: Dict[str, Any]) -> str:
        """
        Создать ключ кэша из контекста.
        
        Args:
            context: Контекст для валидации
            
        Returns:
            Хеш-ключ для кэша
        """
        # Нормализуем контекст для кэширования
        normalized = {
            k: v for k, v in sorted(context.items()) 
            if v is not None and k not in ['timestamp', 'session_id', 'dialog_history']
        }
        # Добавляем уровень валидации
        normalized['_level'] = self.level.value
        # Создаем хеш
        data = json.dumps(normalized, sort_keys=True, default=str)
        return hashlib.md5(data.encode()).hexdigest()
    
    @lru_cache(maxsize=1000)
    def _cached_validate(self, cache_key: str, context_json: str) -> str:
        """
        Кэшированная валидация.
        
        Args:
            cache_key: Ключ кэша
            context_json: JSON представление контекста
            
        Returns:
            JSON представление результата валидации
        """
        context = json.loads(context_json)
        result = super().validate_full_context(context)
        return json.dumps(result.to_dict())
    
    def validate_full_context(self, context: Dict[str, Any]) -> ValidationResult:
        """
        Валидация с кэшированием результатов.
        
        Args:
            context: Контекст для валидации
            
        Returns:
            Результат валидации
        """
        cache_key = self._make_cache_key(context)
        context_json = json.dumps(context, default=str)
        
        result_json = self._cached_validate(cache_key, context_json)
        result_dict = json.loads(result_json)
        
        # Восстанавливаем объект ValidationResult
        result = ValidationResult(result_dict['is_valid'])
        for error in result_dict.get('errors', []):
            result.add_error(error['field'], error['message'], error.get('value'))
        for warning in result_dict.get('warnings', []):
            result.add_warning(warning['field'], warning['message'], warning.get('value'))
        
        return result


# ============================================================================
# МНОГОЯЗЫЧНЫЕ СООБЩЕНИЯ
# ============================================================================

class I18nValidator(Validator):
    """Валидатор с поддержкой многоязычных сообщений."""
    
    def __init__(self, level: ValidationLevel = ValidationLevel.STANDARD, lang: str = 'ru'):
        super().__init__(level)
        self.lang = lang
        
        self.messages = {
            'ru': {
                'material_required': "Материал должен быть строкой",
                'material_not_supported': "Материал '{material}' не поддерживается",
                'diameter_too_small': "Диаметр слишком мал (мин. {min})",
                'diameter_too_large': "Диаметр слишком велик (макс. {max})",
                'number_required': "Параметр {param_name} должен быть числом",
                'range_not_found': "Не найден диапазон безопасности для {param_name}",
            },
            'en': {
                'material_required': "Material must be a string",
                'material_not_supported': "Material '{material}' not supported",
                'diameter_too_small': "Diameter too small (min {min})",
                'diameter_too_large': "Diameter too large (max {max})",
                'number_required': "Parameter {param_name} must be a number",
                'range_not_found': "Safety range not found for {param_name}",
            }
        }
    
    def _t(self, key: str, **kwargs) -> str:
        """
        Получить переведенное сообщение.
        
        Args:
            key: Ключ сообщения
            **kwargs: Параметры для подстановки
            
        Returns:
            Переведенное сообщение
        """
        msg = self.messages.get(self.lang, self.messages['ru']).get(key, key)
        try:
            return msg.format(**kwargs)
        except (KeyError, ValueError):
            return msg
    
    def validate_material(self, material: str) -> ValidationResult:
        result = ValidationResult()
        
        if not material or not isinstance(material, str):
            result.add_error("material", self._t('material_required'), material)
            return result
        
        material_info = self.db.get_material(material)
        if not material_info:
            supported = ", ".join(self.db.materials_list)
            result.add_error("material", 
                self._t('material_not_supported', material=material), material)
        
        return result
    
    def validate_number(self, value: Any, param_name: str, safety_range_name: str,
                        context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        result = ValidationResult()

        # Конвертация
        decimal_value = _to_decimal(value)
        if decimal_value is None:
            result.add_error(param_name, self._t('number_required', param_name=param_name), value)
            return result

        float_value = float(decimal_value)
        
        # Проверка на NaN/Inf
        if math.isnan(float_value) or math.isinf(float_value):
            result.add_error(param_name, self._t('number_required', param_name=param_name), value)
            return result

        # Проверка безопасного диапазона
        safety_range = self.db.get_safety_range(safety_range_name)
        if not safety_range:
            result.add_error(param_name, self._t('range_not_found', param_name=param_name), float_value)
            return result

        # Проверка минимума и максимума
        if float_value < safety_range.min_val:
            result.add_error(param_name,
                             self._t('diameter_too_small', min=safety_range.min_val),
                             float_value)

        elif float_value > safety_range.max_val:
            result.add_error(param_name,
                             self._t('diameter_too_large', max=safety_range.max_val),
                             float_value)

        # Проверка предупреждений
        if safety_range.warning_min and float_value < safety_range.warning_min:
            result.add_warning(param_name,
                               f"{param_name} очень мал ({float_value})")

        if safety_range.warning_max and float_value > safety_range.warning_max:
            result.add_warning(param_name,
                               f"{param_name} очень велик ({float_value})")

        # Проверка единиц измерения
        UnitValidator.add_unit_warning(result, param_name, float_value)

        # Контекстные проверки
        if context:
            if 'operation' in context:
                operation_info = self.db.get_operation(context['operation'])
                if operation_info and param_name == 'diameter_mm':
                    if (float_value < operation_info.typical_diameter_range[0] or
                            float_value > operation_info.typical_diameter_range[1]):
                        result.add_warning(param_name,
                                           f"Диаметр {float_value} мм выходит за типичный диапазон для операции")

        return result


# ============================================================================
# ВЗВЕШЕННЫЕ ПРАВИЛА ДЛЯ ML
# ============================================================================

@dataclass
class WeightedValidationRule:
    """Правило валидации с весом для ML."""
    
    name: str
    weight: float  # Важность правила от 0 до 1
    condition: Callable[[Dict[str, Any]], float]  # Возвращает степень нарушения (0-1)
    description: str


class MLValidator(Validator):
    """Валидатор с поддержкой взвешенных правил для ML."""
    
    def __init__(self, level: ValidationLevel = ValidationLevel.STANDARD):
        super().__init__(level)
        self.weighted_rules: List[WeightedValidationRule] = []
    
    def add_weighted_rule(self, rule: WeightedValidationRule):
        """Добавить взвешенное правило."""
        self.weighted_rules.append(rule)
    
    def calculate_validation_score(self, context: Dict[str, Any]) -> float:
        """
        Рассчитать общую оценку валидности контекста (0-1).
        Используется для ML моделей.
        
        Args:
            context: Контекст для оценки
            
        Returns:
            Оценка валидности от 0 до 1 (1 = полностью валиден)
        """
        total_weight = sum(rule.weight for rule in self.weighted_rules)
        if total_weight == 0:
            return 1.0
        
        score = 0.0
        for rule in self.weighted_rules:
            violation = rule.condition(context)
            score += rule.weight * (1 - violation)
        
        return score / total_weight
    
    def get_validation_factors(self, context: Dict[str, Any]) -> Dict[str, float]:
        """
        Получить факторы валидации для каждого правила.
        Полезно для объяснения решений.
        
        Args:
            context: Контекст для анализа
            
        Returns:
            Словарь с факторами валидации
        """
        factors = {}
        for rule in self.weighted_rules:
            violation = rule.condition(context)
            factors[rule.name] = {
                'violation': violation,
                'weight': rule.weight,
                'contribution': rule.weight * (1 - violation),
                'description': rule.description
            }
        return factors


# ============================================================================
# ОБУЧЕНИЕ НА ОБРАТНОЙ СВЯЗИ
# ============================================================================

class FeedbackAwareValidator(Validator):
    """Валидатор, который учится на обратной связи."""
    
    def __init__(self, level: ValidationLevel = ValidationLevel.STANDARD):
        super().__init__(level)
        self.feedback_history: List[Dict] = []
        self.adjustment_factors: Dict[str, float] = {}
    
    def record_feedback(self, context: Dict[str, Any], 
                        validation_result: ValidationResult,
                        user_accepted: bool):
        """
        Записать обратную связь по результатам валидации.
        
        Args:
            context: Контекст валидации
            validation_result: Результат валидации
            user_accepted: Принял ли пользователь результат
        """
        self.feedback_history.append({
            'context': context,
            'validation': validation_result.to_dict(),
            'user_accepted': user_accepted,
            'timestamp': datetime.now().isoformat()
        })
        
        # Анализируем и корректируем правила
        self._adjust_rules()
    
    def _adjust_rules(self):
        """Скорректировать правила на основе обратной связи."""
        if len(self.feedback_history) < 10:
            return
        
        # Анализируем последние 100 записей
        recent = self.feedback_history[-100:]
        
        # Для каждого типа предупреждения смотрим, как часто пользователь соглашался
        warning_stats = defaultdict(lambda: {'total': 0, 'accepted': 0})
        
        for feedback in recent:
            validation = feedback['validation']
            accepted = feedback['user_accepted']
            
            for warning in validation.get('warnings', []):
                field = warning['field']
                warning_stats[field]['total'] += 1
                if accepted:
                    warning_stats[field]['accepted'] += 1
        
        # Корректируем пороги для предупреждений
        for field, stats in warning_stats.items():
            if stats['total'] >= 5:
                acceptance_rate = stats['accepted'] / stats['total']
                
                if acceptance_rate < 0.3:
                    # Пользователи часто игнорируют - повышаем порог
                    self.adjustment_factors[field] = self.adjustment_factors.get(field, 1.0) * 1.1
                elif acceptance_rate > 0.8:
                    # Пользователи часто соглашаются - понижаем порог
                    self.adjustment_factors[field] = self.adjustment_factors.get(field, 1.0) * 0.9
    
    def get_adjusted_range(self, param_name: str, base_range: SafetyRange) -> SafetyRange:
        """
        Получить скорректированный диапазон на основе обратной связи.
        
        Args:
            param_name: Имя параметра
            base_range: Базовый диапазон
            
        Returns:
            Скорректированный диапазон
        """
        factor = self.adjustment_factors.get(param_name, 1.0)
        
        return SafetyRange(
            min_val=base_range.min_val,
            max_val=base_range.max_val,
            warning_min=base_range.warning_min * factor if base_range.warning_min else None,
            warning_max=base_range.warning_max / factor if base_range.warning_max else None
        )
