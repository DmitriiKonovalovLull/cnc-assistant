"""
Валидация ввода пользователя для CNC Assistant.
Расширенная система валидации с поддержкой всех типов данных.
Версия 2.0 с улучшенными сообщениями об ошибках и гибкими настройками.
"""

from typing import Dict, Any, Tuple, Optional, List, Union, Callable
from enum import Enum
import re
from decimal import Decimal, InvalidOperation


class ValidationLevel(Enum):
    """Уровни строгости валидации."""
    LENIENT = "lenient"  # Минимальная проверка
    STANDARD = "standard"  # Стандартная проверка (по умолчанию)
    STRICT = "strict"  # Строгая проверка
    EXPERT = "expert"  # Экспертная проверка с дополнительными правилами


class ValidationError(Enum):
    """Типы ошибок валидации."""
    INVALID_TYPE = "invalid_type"
    OUT_OF_RANGE = "out_of_range"
    UNSUPPORTED_VALUE = "unsupported_value"
    FORMAT_ERROR = "format_error"
    MISSING_REQUIRED = "missing_required"
    INVALID_PATTERN = "invalid_pattern"
    LOGICAL_ERROR = "logical_error"
    SAFETY_VIOLATION = "safety_violation"


# ============================================================================
# БАЗЫ ДАННЫХ ДЛЯ ВАЛИДАЦИИ
# ============================================================================

class ValidationDatabase:
    """База данных для валидации с поддержкой конфигурации."""

    def __init__(self):
        # Поддерживаемые материалы
        self.materials = {
            # Основные материалы
            'сталь': {
                'types': [
                    'углеродистая', 'легированная', 'инструментальная',
                    'конструкционная', 'пружинная', 'быстрорежущая'
                ],
                'aliases': ['сталь', 'steel', 'стали', 'железо'],
                'difficulty_range': (0.8, 1.5),
                'valid_grades': ['Ст3', 'Ст45', '40Х', '30ХГСА', 'У8', 'Р6М5']
            },
            'алюминий': {
                'types': ['технический', 'дюралюминий', 'силумин', 'чистый'],
                'aliases': ['алюминий', 'aluminum', 'ал', 'д16', 'ад1'],
                'difficulty_range': (0.5, 1.0),
                'valid_grades': ['АД0', 'АД1', 'Д16Т', 'АК4', 'АК8']
            },
            'титан': {
                'types': ['чистый', 'сплав', 'жаропрочный'],
                'aliases': ['титан', 'titanium', 'тита', 'вт', 'oti'],
                'difficulty_range': (1.5, 2.0),
                'valid_grades': ['ВТ1', 'ВТ6', 'ВТ8', 'ОТ4', 'ПТ3М']
            },
            'нержавейка': {
                'types': ['аустенитная', 'ферритная', 'мартенситная', 'дуплекс'],
                'aliases': ['нержавейка', 'нерж', 'stainless', 'коррозион'],
                'difficulty_range': (1.2, 1.8),
                'valid_grades': ['12Х18Н10Т', '304', '316', '321', '430']
            },
            'чугун': {
                'types': ['серый', 'белый', 'ковкий', 'высокопрочный'],
                'aliases': ['чугун', 'cast iron', 'чугу', 'сч', 'вч'],
                'difficulty_range': (0.9, 1.4),
                'valid_grades': ['СЧ20', 'СЧ25', 'ВЧ35', 'ВЧ50', 'КЧ30']
            },
            'латунь': {
                'types': ['деформируемая', 'литейная', 'специальная'],
                'aliases': ['латунь', 'brass', 'лату', 'лс', 'л'],
                'difficulty_range': (0.6, 0.9),
                'valid_grades': ['Л63', 'ЛС59', 'ЛАЖ60', 'ЛМц58']
            },
            'медь': {
                'types': ['техническая', 'электролитическая', 'бескислородная'],
                'aliases': ['медь', 'copper', 'мед', 'м', 'cu'],
                'difficulty_range': (0.7, 1.0),
                'valid_grades': ['М1', 'М2', 'М3', 'М0']
            },
            'бронза': {
                'types': ['оловянная', 'алюминиевая', 'кремнистая', 'бериллиевая'],
                'aliases': ['бронз', 'bronze', 'бр', 'брс', 'бро'],
                'difficulty_range': (0.8, 1.2),
                'valid_grades': ['БрОФ', 'БрАЖ', 'БрКМц', 'БрБ2']
            },
            'инконель': {
                'types': ['жаростойкий', 'жаропрочный', 'коррозионностойкий'],
                'aliases': ['инконель', 'inconel', 'инкон', 'жаропроч'],
                'difficulty_range': (1.8, 2.2),
                'valid_grades': ['718', '625', '600', 'X750']
            }
        }

        # Поддерживаемые операции
        self.operations = {
            'токарка': {
                'variants': ['точение', 'обтачивание', 'наружное точение', 'растачивание'],
                'aliases': ['токарка', 'turning', 'токарный'],
                'complexity': 1.0,
                'typical_diameter_range': (0.5, 500),  # мм
                'typical_rpm_range': (50, 5000)  # об/мин
            },
            'фрезерование': {
                'variants': ['торцовое', 'контурное', 'объемное', 'фасонное'],
                'aliases': ['фрезерование', 'milling', 'фрезеровка', 'фреза'],
                'complexity': 1.2,
                'typical_diameter_range': (1, 100),  # мм
                'typical_rpm_range': (500, 15000)  # об/мин
            },
            'сверление': {
                'variants': ['глубокое', 'многоступенчатое', 'зенкование', 'развертывание'],
                'aliases': ['сверление', 'drilling', 'сверло', 'отверстие'],
                'complexity': 0.8,
                'typical_diameter_range': (0.1, 50),  # мм
                'typical_rpm_range': (100, 8000)  # об/мин
            },
            'растачивание': {
                'variants': ['тонкое', 'чистовое', 'калибрующее'],
                'aliases': ['растачивание', 'boring', 'расточка', 'расточной'],
                'complexity': 1.1,
                'typical_diameter_range': (5, 500),  # мм
                'typical_rpm_range': (100, 3000)  # об/мин
            },
            'нарезание резьбы': {
                'variants': ['внутренняя', 'наружная', 'метрическая', 'трубная'],
                'aliases': ['резьба', 'threading', 'нарезание', 'резьбонарезание'],
                'complexity': 1.3,
                'typical_diameter_range': (1, 100),  # мм
                'typical_rpm_range': (50, 2000)  # об/мин
            }
        }

        # Поддерживаемые режимы обработки
        self.modes = {
            'черновой': {
                'description': 'Максимальный съём металла',
                'feed_multiplier': 1.5,
                'speed_multiplier': 0.8,
                'surface_quality': 'Ra 12.5-25'
            },
            'получистовой': {
                'description': 'Баланс производительности и качества',
                'feed_multiplier': 1.0,
                'speed_multiplier': 1.0,
                'surface_quality': 'Ra 3.2-6.3'
            },
            'чистовой': {
                'description': 'Максимальное качество поверхности',
                'feed_multiplier': 0.7,
                'speed_multiplier': 1.2,
                'surface_quality': 'Ra 0.8-1.6'
            },
            'тонкий': {
                'description': 'Прецизионная обработка',
                'feed_multiplier': 0.5,
                'speed_multiplier': 1.5,
                'surface_quality': 'Ra 0.1-0.4'
            }
        }

        # Безопасные диапазоны
        self.safety_ranges = {
            'diameter_mm': {
                'min': 0.05,  # 0.05 мм - микросверла
                'max': 2000,  # 2000 мм - крупные детали
                'warning_threshold': 0.1,  # Предупреждение ниже 0.1 мм
                'danger_threshold': 1500  # Опасность выше 1500 мм
            },
            'rpm': {
                'min': 10,  # 10 об/мин - очень медленно
                'max': 30000,  # 30000 об/мин - высокоскоростные станки
                'warning_threshold': 50,  # Предупреждение ниже 50 об/мин
                'danger_threshold': 20000  # Опасность выше 20000 об/мин
            },
            'cutting_speed_m_min': {
                'min': 1,  # 1 м/мин - очень медленно
                'max': 2000,  # 2000 м/мин - сверхвысокие скорости
                'warning_threshold': 10,  # Предупреждение ниже 10 м/мин
                'danger_threshold': 1500  # Опасность выше 1500 м/мин
            },
            'feed_mm_per_rev': {
                'min': 0.01,  # 0.01 мм/об - очень мелкая подача
                'max': 5.0,  # 5.0 мм/об - грубая обработка
                'warning_threshold': 0.05,  # Предупреждение ниже 0.05 мм/об
                'danger_threshold': 3.0  # Опасность выше 3.0 мм/об
            }
        }


# ============================================================================
# ОСНОВНОЙ КЛАСС ВАЛИДАТОРА
# ============================================================================

class Validator:
    """Основной класс валидации с поддержкой разных уровней строгости."""

    def __init__(self, level: ValidationLevel = ValidationLevel.STANDARD):
        self.level = level
        self.db = ValidationDatabase()
        self.last_errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []

    def clear_errors(self):
        """Очистить историю ошибок и предупреждений."""
        self.last_errors.clear()
        self.warnings.clear()

    def add_error(self, field: str, error_type: ValidationError, message: str, value: Any = None):
        """Добавить ошибку в историю."""
        self.last_errors.append({
            'field': field,
            'type': error_type,
            'message': message,
            'value': value,
            'level': 'error'
        })

    def add_warning(self, field: str, message: str, value: Any = None):
        """Добавить предупреждение в историю."""
        self.warnings.append({
            'field': field,
            'message': message,
            'value': value,
            'level': 'warning'
        })

    def validate_material(self, material: str, check_type: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Валидация материала.

        Args:
            material: Название материала
            check_type: Проверять ли конкретный тип материала

        Returns:
            Tuple[bool, Optional[str]]: Результат валидации и сообщение об ошибке
        """
        self.clear_errors()

        if not material or not isinstance(material, str):
            self.add_error('material', ValidationError.INVALID_TYPE,
                           "Материал должен быть строкой", material)
            return False, "Материал должен быть строкой"

        material_lower = material.lower().strip()

        # Проверяем базовый материал
        base_material = None
        for mat_name, mat_data in self.db.materials.items():
            if (material_lower == mat_name or
                    material_lower in mat_data['aliases'] or
                    any(alias in material_lower for alias in mat_data['aliases'])):
                base_material = mat_name
                break

        if not base_material:
            # Проверяем, содержит ли строка название материала
            for mat_name, mat_data in self.db.materials.items():
                if mat_name in material_lower:
                    base_material = mat_name
                    break

        if not base_material:
            supported = ", ".join(self.db.materials.keys())
            self.add_error('material', ValidationError.UNSUPPORTED_VALUE,
                           f"Материал '{material}' не поддерживается", material)
            return False, f"Материал '{material}' не поддерживается. Доступные: {supported}"

        # Проверяем тип материала если нужно
        if check_type and self.level in [ValidationLevel.STRICT, ValidationLevel.EXPERT]:
            mat_data = self.db.materials[base_material]
            has_valid_type = False

            # Проверяем, содержит ли строка тип материала
            for mat_type in mat_data['types']:
                if mat_type in material_lower:
                    has_valid_type = True
                    break

            # Проверяем марку/сорт
            has_valid_grade = False
            if 'valid_grades' in mat_data:
                for grade in mat_data['valid_grades']:
                    if grade.lower() in material_lower.replace(' ', ''):
                        has_valid_grade = True
                        break

            if not has_valid_type and not has_valid_grade:
                self.add_warning('material',
                                 f"Рекомендуется уточнить тип или марку материала {base_material}")

        return True, None

    def validate_operation(self, operation: str) -> Tuple[bool, Optional[str]]:
        """
        Валидация операции.

        Args:
            operation: Название операции

        Returns:
            Tuple[bool, Optional[str]]: Результат валидации и сообщение об ошибке
        """
        if not operation or not isinstance(operation, str):
            self.add_error('operation', ValidationError.INVALID_TYPE,
                           "Операция должна быть строкой", operation)
            return False, "Операция должна быть строкой"

        operation_lower = operation.lower().strip()

        # Проверяем операцию
        valid_operation = None
        for op_name, op_data in self.db.operations.items():
            if (operation_lower == op_name or
                    operation_lower in op_data['aliases'] or
                    any(alias in operation_lower for alias in op_data['aliases'])):
                valid_operation = op_name
                break

        if not valid_operation:
            # Проверяем, содержит ли строка название операции
            for op_name, op_data in self.db.operations.items():
                if op_name in operation_lower:
                    valid_operation = op_name
                    break

        if not valid_operation:
            supported = ", ".join(self.db.operations.keys())
            self.add_error('operation', ValidationError.UNSUPPORTED_VALUE,
                           f"Операция '{operation}' не поддерживается", operation)
            return False, f"Операция '{operation}' не поддерживается. Доступные: {supported}"

        return True, None

    def validate_mode(self, mode: str) -> Tuple[bool, Optional[str]]:
        """
        Валидация режима обработки.

        Args:
            mode: Название режима

        Returns:
            Tuple[bool, Optional[str]]: Результат валидации и сообщение об ошибке
        """
        if not mode or not isinstance(mode, str):
            self.add_error('mode', ValidationError.INVALID_TYPE,
                           "Режим должен быть строкой", mode)
            return False, "Режим должен быть строкой"

        mode_lower = mode.lower().strip()

        if mode_lower not in self.db.modes:
            supported = ", ".join(self.db.modes.keys())
            self.add_error('mode', ValidationError.UNSUPPORTED_VALUE,
                           f"Режим '{mode}' не поддерживается", mode)
            return False, f"Режим '{mode}' не поддерживается. Доступные: {supported}"

        return True, None

    def validate_diameter(self, diameter: Any, context: Dict[str, Any] = None) -> Tuple[bool, Optional[str]]:
        """
        Валидация диаметра с учётом контекста.

        Args:
            diameter: Диаметр для проверки
            context: Контекст (материал, операция и т.д.)

        Returns:
            Tuple[bool, Optional[str]]: Результат валидации и сообщение об ошибке
        """
        # Пытаемся преобразовать в число
        try:
            if isinstance(diameter, str):
                # Заменяем запятые на точки
                diameter_str = diameter.replace(',', '.').strip()
                d = Decimal(diameter_str)
            else:
                d = Decimal(str(diameter))
        except (InvalidOperation, ValueError, TypeError):
            self.add_error('diameter', ValidationError.INVALID_TYPE,
                           "Диаметр должен быть числом", diameter)
            return False, "Диаметр должен быть числом"

        # Проверяем диапазон безопасности
        safety = self.db.safety_ranges['diameter_mm']
        d_float = float(d)

        if d_float < safety['min']:
            self.add_error('diameter', ValidationError.SAFETY_VIOLATION,
                           f"Диаметр слишком мал (мин. {safety['min']} мм)", d_float)
            return False, f"Диаметр слишком мал. Минимальное значение: {safety['min']} мм"

        elif d_float > safety['max']:
            self.add_error('diameter', ValidationError.SAFETY_VIOLATION,
                           f"Диаметр слишком велик (макс. {safety['max']} мм)", d_float)
            return False, f"Диаметр слишком велик. Максимальное значение: {safety['max']} мм"

        # Проверяем пороги предупреждений
        if d_float < safety['warning_threshold']:
            self.add_warning('diameter',
                             f"Очень маленький диаметр ({d_float} мм). Требуется высокая точность и осторожность.")

        elif d_float > safety['danger_threshold']:
            self.add_warning('diameter',
                             f"Очень большой диаметр ({d_float} мм). Проверьте возможности станка.")

        # Проверяем типичный диапазон для операции если есть контекст
        if context and context.get('operation'):
            operation = context['operation'].lower()
            if operation in self.db.operations:
                op_range = self.db.operations[operation]['typical_diameter_range']
                if d_float < op_range[0] or d_float > op_range[1]:
                    self.add_warning('diameter',
                                     f"Диаметр {d_float} мм выходит за типичный диапазон для {operation} "
                                     f"({op_range[0]}-{op_range[1]} мм)")

        return True, None

    def validate_rpm(self, rpm: Any, diameter: Optional[float] = None,
                     material: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Валидация оборотов с учётом диаметра и материала.

        Args:
            rpm: Обороты для проверки
            diameter: Диаметр инструмента (опционально)
            material: Материал (опционально)

        Returns:
            Tuple[bool, Optional[str]]: Результат валидации и сообщение об ошибке
        """
        # Пытаемся преобразовать в число
        try:
            if isinstance(rpm, str):
                rpm_str = rpm.replace(',', '.').strip()
                r = Decimal(rpm_str)
            else:
                r = Decimal(str(rpm))
        except (InvalidOperation, ValueError, TypeError):
            self.add_error('rpm', ValidationError.INVALID_TYPE,
                           "Обороты должны быть числом", rpm)
            return False, "Обороты должны быть числом"

        # Проверяем диапазон безопасности
        safety = self.db.safety_ranges['rpm']
        r_float = float(r)

        if r_float < safety['min']:
            self.add_error('rpm', ValidationError.SAFETY_VIOLATION,
                           f"Обороты слишком низкие (мин. {safety['min']} об/мин)", r_float)
            return False, f"Обороты слишком низкие. Минимальное значение: {safety['min']} об/мин"

        elif r_float > safety['max']:
            self.add_error('rpm', ValidationError.SAFETY_VIOLATION,
                           f"Обороты слишком высокие (макс. {safety['max']} об/мин)", r_float)
            return False, f"Обороты слишком высокие. Максимальное значение: {safety['max']} об/мин"

        # Проверяем пороги предупреждений
        if r_float < safety['warning_threshold']:
            self.add_warning('rpm',
                             f"Очень низкие обороты ({r_float} об/мин). Проверьте правильность ввода.")

        elif r_float > safety['danger_threshold']:
            self.add_warning('rpm',
                             f"Очень высокие обороты ({r_float} об/мин). Убедитесь в безопасности.")

        # Проверяем скорость резания если есть диаметр
        if diameter and diameter > 0:
            # Рассчитываем скорость резания: Vc = π × D × n / 1000
            import math
            cutting_speed = math.pi * diameter * r_float / 1000

            # Проверяем безопасный диапазон скорости резания
            vc_safety = self.db.safety_ranges['cutting_speed_m_min']

            if cutting_speed < vc_safety['min']:
                self.add_warning('rpm',
                                 f"Очень низкая скорость резания: {cutting_speed:.1f} м/мин")

            elif cutting_speed > vc_safety['max']:
                self.add_error('rpm', ValidationError.SAFETY_VIOLATION,
                               f"Опасная скорость резания: {cutting_speed:.1f} м/мин", r_float)
                return False, f"Опасная скорость резания: {cutting_speed:.1f} м/мин"

            # Типичные скорости для разных материалов
            if material:
                material_lower = material.lower()
                typical_speeds = {
                    'алюминий': (100, 1000),
                    'сталь': (50, 300),
                    'титан': (10, 60),
                    'нержавейка': (30, 100),
                    'чугун': (40, 120),
                }

                for mat, speed_range in typical_speeds.items():
                    if mat in material_lower:
                        if cutting_speed < speed_range[0]:
                            self.add_warning('rpm',
                                             f"Низкая скорость резания для {material}: "
                                             f"{cutting_speed:.1f} м/мин (типично {speed_range[0]}-{speed_range[1]} м/мин)")
                        elif cutting_speed > speed_range[1]:
                            self.add_warning('rpm',
                                             f"Высокая скорость резания для {material}: "
                                             f"{cutting_speed:.1f} м/мин (типично {speed_range[0]}-{speed_range[1]} м/мин)")
                        break

        return True, None

    def validate_feed(self, feed: Any, operation: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Валидация подачи.

        Args:
            feed: Подача для проверки
            operation: Операция (для контекстной проверки)

        Returns:
            Tuple[bool, Optional[str]]: Результат валидации и сообщение об ошибке
        """
        try:
            if isinstance(feed, str):
                feed_str = feed.replace(',', '.').strip()
                f = Decimal(feed_str)
            else:
                f = Decimal(str(feed))
        except (InvalidOperation, ValueError, TypeError):
            self.add_error('feed', ValidationError.INVALID_TYPE,
                           "Подача должна быть числом", feed)
            return False, "Подача должна быть числом"

        # Проверяем диапазон безопасности
        safety = self.db.safety_ranges['feed_mm_per_rev']
        f_float = float(f)

        if f_float < safety['min']:
            self.add_error('feed', ValidationError.SAFETY_VIOLATION,
                           f"Подача слишком мала (мин. {safety['min']} мм/об)", f_float)
            return False, f"Подача слишком мала. Минимальное значение: {safety['min']} мм/об"

        elif f_float > safety['max']:
            self.add_error('feed', ValidationError.SAFETY_VIOLATION,
                           f"Подача слишком велика (макс. {safety['max']} мм/об)", f_float)
            return False, f"Подача слишком велика. Максимальное значение: {safety['max']} мм/об"

        # Проверяем типичные значения для операции
        if operation:
            operation_lower = operation.lower()
            typical_feeds = {
                'токарка': (0.05, 0.5),
                'фрезерование': (0.01, 0.3),
                'сверление': (0.05, 0.4),
                'растачивание': (0.03, 0.2),
                'нарезание резьбы': (0.5, 3.0),
            }

            for op, feed_range in typical_feeds.items():
                if op in operation_lower:
                    if f_float < feed_range[0] or f_float > feed_range[1]:
                        self.add_warning('feed',
                                         f"Подача {f_float} мм/об выходит за типичный диапазон для {operation} "
                                         f"({feed_range[0]}-{feed_range[1]} мм/об)")
                    break

        return True, None

    def validate_cutting_speed(self, vc: Any, material: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Валидация скорости резания.

        Args:
            vc: Скорость резания (м/мин)
            material: Материал (для контекстной проверки)

        Returns:
            Tuple[bool, Optional[str]]: Результат валидации и сообщение об ошибке
        """
        try:
            if isinstance(vc, str):
                vc_str = vc.replace(',', '.').strip()
                v = Decimal(vc_str)
            else:
                v = Decimal(str(vc))
        except (InvalidOperation, ValueError, TypeError):
            self.add_error('cutting_speed', ValidationError.INVALID_TYPE,
                           "Скорость резания должна быть числом", vc)
            return False, "Скорость резания должна быть числом"

        # Проверяем диапазон безопасности
        safety = self.db.safety_ranges['cutting_speed_m_min']
        v_float = float(v)

        if v_float < safety['min']:
            self.add_error('cutting_speed', ValidationError.SAFETY_VIOLATION,
                           f"Скорость резания слишком низкая (мин. {safety['min']} м/мин)", v_float)
            return False, f"Скорость резания слишком низкая. Минимальное значение: {safety['min']} м/мин"

        elif v_float > safety['max']:
            self.add_error('cutting_speed', ValidationError.SAFETY_VIOLATION,
                           f"Скорость резания слишком высокая (макс. {safety['max']} м/мин)", v_float)
            return False, f"Скорость резания слишком высокая. Максимальное значение: {safety['max']} м/мин"

        # Проверяем типичные значения для материала
        if material:
            material_lower = material.lower()
            typical_speeds = {
                'алюминий': (100, 1000),
                'сталь': (50, 300),
                'титан': (10, 60),
                'нержавейка': (30, 100),
                'чугун': (40, 120),
                'латунь': (80, 200),
                'медь': (60, 180),
                'бронза': (40, 150),
                'инконель': (5, 30),
            }

            for mat, speed_range in typical_speeds.items():
                if mat in material_lower:
                    if v_float < speed_range[0] or v_float > speed_range[1]:
                        self.add_warning('cutting_speed',
                                         f"Скорость резания {v_float} м/мин выходит за типичный диапазон для {material} "
                                         f"({speed_range[0]}-{speed_range[1]} м/мин)")
                    break

        return True, None

    def validate_full_context(self, context: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Полная валидация контекста с проверкой логических связей.

        Args:
            context: Контекст для валидации

        Returns:
            Tuple[bool, Optional[str]]: Результат валидации и сообщение об ошибке
        """
        self.clear_errors()

        # Обязательные поля
        required_fields = ['material', 'operation', 'mode', 'diameter']
        for field in required_fields:
            if field not in context:
                self.add_error(field, ValidationError.MISSING_REQUIRED,
                               f"Отсутствует обязательное поле: {field}", None)

        if self.last_errors:
            return False, "Отсутствуют обязательные поля"

        # Валидация отдельных полей
        validators = [
            ('material', lambda: self.validate_material(context['material'])),
            ('operation', lambda: self.validate_operation(context['operation'])),
            ('mode', lambda: self.validate_mode(context['mode'])),
            ('diameter', lambda: self.validate_diameter(context['diameter'], context)),
        ]

        # Дополнительные поля если есть
        if 'rpm' in context:
            validators.append(('rpm',
                               lambda: self.validate_rpm(context['rpm'],
                                                         context.get('diameter'),
                                                         context.get('material'))))

        if 'feed' in context:
            validators.append(('feed',
                               lambda: self.validate_feed(context['feed'],
                                                          context.get('operation'))))

        if 'vc' in context:
            validators.append(('vc',
                               lambda: self.validate_cutting_speed(context['vc'],
                                                                   context.get('material'))))

        # Выполняем все валидации
        for field_name, validator in validators:
            is_valid, error = validator()
            if not is_valid:
                # Ошибка уже добавлена в add_error
                pass

        # Дополнительные логические проверки
        if 'diameter' in context and 'rpm' in context and 'vc' in context:
            # Проверяем согласованность Vc = π × D × n / 1000
            import math
            diameter = float(context['diameter'])
            rpm = float(context['rpm'])
            vc = float(context['vc'])

            calculated_vc = math.pi * diameter * rpm / 1000
            tolerance = 0.1  # 10% допуск

            if abs(calculated_vc - vc) / vc > tolerance:
                self.add_error('consistency', ValidationError.LOGICAL_ERROR,
                               f"Несоответствие параметров: Vc расчётная={calculated_vc:.1f}, "
                               f"Vc введённая={vc:.1f}", None)

        # Проверяем безопасность комбинации параметров
        if 'material' in context and 'operation' in context and 'diameter' in context and 'rpm' in context:
            material = context['material'].lower()
            operation = context['operation'].lower()
            diameter = float(context['diameter'])
            rpm = float(context['rpm'])

            # Проверяем типичные диапазоны RPM для операции и диаметра
            if operation in self.db.operations:
                typical_rpm_range = self.db.operations[operation]['typical_rpm_range']
                if rpm < typical_rpm_range[0] or rpm > typical_rpm_range[1]:
                    self.add_warning('rpm',
                                     f"Обороты {rpm} об/мин выходят за типичный диапазон для {operation} "
                                     f"({typical_rpm_range[0]}-{typical_rpm_range[1]} об/мин)")

        if self.last_errors:
            # Возвращаем первую ошибку
            error_msg = self.last_errors[0]['message']
            return False, error_msg

        return True, None

    def get_validation_summary(self) -> Dict[str, Any]:
        """
        Получить сводку по результатам валидации.

        Returns:
            Dict: Сводка валидации
        """
        return {
            'level': self.level.value,
            'errors': self.last_errors.copy(),
            'warnings': self.warnings.copy(),
            'has_errors': len(self.last_errors) > 0,
            'has_warnings': len(self.warnings) > 0,
            'is_valid': len(self.last_errors) == 0
        }


# ============================================================================
# ФУНКЦИИ ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ
# ============================================================================

# Глобальный экземпляр валидатора
_default_validator = Validator()


def validate_material(material: str) -> Tuple[bool, Optional[str]]:
    """
    Валидация материала (обратная совместимость).

    Args:
        material: Название материала

    Returns:
        Tuple[bool, Optional[str]]: Результат валидации
    """
    return _default_validator.validate_material(material)


def validate_operation(operation: str) -> Tuple[bool, Optional[str]]:
    """
    Валидация операции (обратная совместимость).

    Args:
        operation: Название операции

    Returns:
        Tuple[bool, Optional[str]]: Результат валидации
    """
    return _default_validator.validate_operation(operation)


def validate_diameter(diameter: Any) -> Tuple[bool, Optional[str]]:
    """
    Валидация диаметра (обратная совместимость).

    Args:
        diameter: Диаметр для проверки

    Returns:
        Tuple[bool, Optional[str]]: Результат валидации
    """
    return _default_validator.validate_diameter(diameter)


def validate_rpm(rpm: Any) -> Tuple[bool, Optional[str]]:
    """
    Валидация оборотов (обратная совместимость).

    Args:
        rpm: Обороты для проверки

    Returns:
        Tuple[bool, Optional[str]]: Результат валидации
    """
    return _default_validator.validate_rpm(rpm)


def validate_full_context(context: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Валидация полного контекста (обратная совместимость).

    Args:
        context: Контекст для проверки

    Returns:
        Tuple[bool, Optional[str]]: Результат валидации
    """
    return _default_validator.validate_full_context(context)


def get_safety_ranges() -> Dict[str, Dict[str, float]]:
    """
    Получить безопасные диапазоны параметров.

    Returns:
        Dict: Безопасные диапазоны
    """
    return _default_validator.db.safety_ranges.copy()


# ============================================================================
# ТЕСТИРОВАНИЕ
# ============================================================================

if __name__ == "__main__":
    print("🧪 Тестирование Validator")
    print("=" * 60)

    # Создаем валидатор с разными уровнями
    validators = {
        'lenient': Validator(ValidationLevel.LENIENT),
        'standard': Validator(ValidationLevel.STANDARD),
        'strict': Validator(ValidationLevel.STRICT),
    }

    # Тестовые данные
    test_cases = [
        {
            'name': 'Корректные данные',
            'context': {
                'material': 'сталь 45',
                'operation': 'токарка',
                'mode': 'черновой',
                'diameter': 50,
                'rpm': 1200,
                'feed': 0.2,
                'vc': 188.5
            }
        },
        {
            'name': 'Некорректный материал',
            'context': {
                'material': 'золото',
                'operation': 'токарка',
                'mode': 'черновой',
                'diameter': 50
            }
        },
        {
            'name': 'Слишком маленький диаметр',
            'context': {
                'material': 'алюминий',
                'operation': 'фрезерование',
                'mode': 'чистовой',
                'diameter': 0.01
            }
        },
        {
            'name': 'Опасные обороты',
            'context': {
                'material': 'сталь',
                'operation': 'сверление',
                'mode': 'черновой',
                'diameter': 10,
                'rpm': 50000
            }
        },
        {
            'name': 'Несоответствие параметров',
            'context': {
                'material': 'титан',
                'operation': 'растачивание',
                'mode': 'получистовой',
                'diameter': 100,
                'rpm': 1000,
                'vc': 500  # Не соответствует формуле
            }
        }
    ]

    for test in test_cases:
        print(f"\n📝 Тест: {test['name']}")
        print(f"   Данные: {test['context']}")

        for level_name, validator in validators.items():
            is_valid, error = validator.validate_full_context(test['context'])
            summary = validator.get_validation_summary()

            print(f"   Уровень {level_name}: {'✅' if is_valid else '❌'} {error}")

            if summary['warnings']:
                for warning in summary['warnings']:
                    print(f"     ⚠️ Предупреждение: {warning['message']}")

    print("\n" + "=" * 60)
    print("📊 Безопасные диапазоны:")
    safety_ranges = get_safety_ranges()
    for param, ranges in safety_ranges.items():
        print(f"\n{param}:")
        for key, value in ranges.items():
            print(f"  {key}: {value}")

    print("\n" + "=" * 60)
    print("✅ Тестирование завершено")