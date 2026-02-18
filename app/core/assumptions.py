"""
ДВИГАТЕЛЬ ПРЕДПОЛОЖЕНИЙ - магия ИИ.
Делает разумные предположения на основе контекста.
Всегда помечает source=ASSUMED и confidence=0.0-1.0
С поддержкой разрешения конфликтов, кэширования и валидации.
"""

import logging
import hashlib
from typing import Dict, Any, Optional, List, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from app.core.context import Context, DataSource

logger = logging.getLogger(__name__)


# ============================================================================
# КОНФИГУРАЦИЯ ПРЕДПОЛОЖЕНИЙ
# ============================================================================

@dataclass
class AssumptionConfig:
    """Конфигурация для предположений."""
    
    # Радиусы инструмента (мм)
    TOOL_RADIUS_FINISHING: float = 0.4
    TOOL_RADIUS_ROUGHING: float = 0.8
    TOOL_RADIUS_DEFAULT: float = 0.8
    
    # Вылет инструмента (мм)
    TOOL_OVERHANG_TURNING: float = 30.0
    TOOL_OVERHANG_MILLING: float = 50.0
    TOOL_OVERHANG_DEFAULT: float = 40.0
    
    # Мощность станка (кВт)
    POWER_CNC_LATHE: float = 11.0
    POWER_MANUAL_LATHE: float = 7.5
    POWER_CNC_MILL: float = 15.0
    POWER_MANUAL_MILL: float = 5.5
    POWER_DEFAULT: float = 11.0
    
    # Пороги для режимов (мм)
    ROUGHING_THRESHOLD: float = 5.0
    SEMI_FINISHING_THRESHOLD: float = 1.0
    
    # Соотношения
    LENGTH_TO_DIAMETER_RATIO: float = 1.5
    MIN_LENGTH: float = 20.0
    MAX_LENGTH: float = 200.0
    
    # Confidence уровни (базовые)
    CONFIDENCE_MACHINE_TYPE: float = 0.7
    CONFIDENCE_MACHINE_POWER: float = 0.6
    CONFIDENCE_TOOL_MATERIAL: float = 0.8
    CONFIDENCE_TOOL_RADIUS: float = 0.7
    CONFIDENCE_TOOL_OVERHANG: float = 0.6
    CONFIDENCE_MODE: float = 0.7
    CONFIDENCE_LENGTH: float = 0.5
    
    # Приоритеты источников данных (чем выше, тем важнее)
    SOURCE_PRIORITY: Dict[DataSource, int] = field(default_factory=lambda: {
        DataSource.USER: 100,
        DataSource.EXTERNAL: 90,
        DataSource.INFERRED: 70,
        DataSource.ASSUMED: 50,
        DataSource.DEFAULT: 30,
    })
    
    # TTL для кэша (секунды)
    CACHE_TTL_SECONDS: int = 300


# ============================================================================
# КЭШИРОВАНИЕ ПРЕДПОЛОЖЕНИЙ
# ============================================================================

class AssumptionCache:
    """Кэш для результатов предположений."""
    
    def __init__(self, ttl_seconds: int = 300):
        """
        Инициализация кэша.
        
        Args:
            ttl_seconds: Время жизни записей в секундах
        """
        self.cache: Dict[str, Tuple[Any, datetime]] = {}
        self.ttl = ttl_seconds
    
    def get(self, context_hash: str, field: str) -> Optional[Any]:
        """
        Получить предположение из кэша.
        
        Args:
            context_hash: Хеш контекста
            field: Название поля
            
        Returns:
            Значение из кэша или None
        """
        key = f"{context_hash}:{field}"
        if key in self.cache:
            value, timestamp = self.cache[key]
            if datetime.now() - timestamp < timedelta(seconds=self.ttl):
                return value
            else:
                del self.cache[key]
        return None
    
    def set(self, context_hash: str, field: str, value: Any):
        """
        Сохранить предположение в кэш.
        
        Args:
            context_hash: Хеш контекста
            field: Название поля
            value: Значение
        """
        key = f"{context_hash}:{field}"
        self.cache[key] = (value, datetime.now())
    
    def clear(self):
        """Очистить кэш."""
        self.cache.clear()


# ============================================================================
# ВАЛИДАЦИЯ ПРЕДПОЛОЖЕНИЙ
# ============================================================================

class AssumptionValidator:
    """Валидатор предположений."""
    
    @staticmethod
    def validate_assumption(field: str, value: Any) -> bool:
        """
        Проверить, что предположение физически возможно.
        
        Args:
            field: Название поля
            value: Значение
            
        Returns:
            True если значение валидно
        """
        validators: Dict[str, Callable[[Any], bool]] = {
            'machine_power': lambda v: isinstance(v, (int, float)) and 0.5 <= v <= 500,  # кВт
            'tool_radius': lambda v: isinstance(v, (int, float)) and 0.1 <= v <= 3.2,    # мм
            'tool_overhang': lambda v: isinstance(v, (int, float)) and 10 <= v <= 200,   # мм
            'length': lambda v: isinstance(v, (int, float)) and 1 <= v <= 2000,          # мм
            'diameter_start': lambda v: isinstance(v, (int, float)) and 0.1 <= v <= 2000,  # мм
            'diameter_end': lambda v: isinstance(v, (int, float)) and 0.1 <= v <= 2000,    # мм
        }
        
        validator = validators.get(field)
        if validator:
            try:
                if not validator(value):
                    logger.warning(f"Invalid assumption for {field}: {value}")
                    return False
            except (TypeError, ValueError):
                logger.warning(f"Validation error for {field}: {value}")
                return False
        
        return True


# ============================================================================
# ОСНОВНОЙ КЛАСС
# ============================================================================

class AssumptionEngine:
    """
    Двигатель предположений.
    Делает разумные предположения на основе контекста.
    """
    
    def __init__(self, knowledge_service=None, config: Optional[AssumptionConfig] = None):
        """
        Инициализация двигателя предположений.
        
        Args:
            knowledge_service: Сервис знаний (опционально)
            config: Конфигурация предположений
        """
        self.knowledge_service = knowledge_service
        self.config = config or AssumptionConfig()
        self.cache = AssumptionCache(ttl_seconds=self.config.CACHE_TTL_SECONDS)
        self.validator = AssumptionValidator()
        self.feedback_store: List[Dict[str, Any]] = []
    
    def _get_context_hash(self, context: Context) -> str:
        """
        Создать хеш контекста для кэширования.
        
        Args:
            context: Контекст
            
        Returns:
            Хеш строки
        """
        important_fields = [
            context.material,
            context.operation,
            context.diameter_start,
            context.diameter_end,
            context.machine_type,
            context.mode
        ]
        hash_str = str(tuple(important_fields))
        return hashlib.md5(hash_str.encode()).hexdigest()
    
    def resolve_conflict(
        self,
        context: Context,
        field_name: str,
        new_value: Any,
        new_source: DataSource
    ) -> Context:
        """
        Разрешить конфликт между существующим значением и новым.
        
        Args:
            context: Контекст
            field_name: Название поля
            new_value: Новое значение
            new_source: Источник нового значения
            
        Returns:
            Обновленный контекст
        """
        metadata = context.get_field_metadata(field_name)
        
        if not metadata:
            # Поля нет - просто устанавливаем
            return context
        
        # Получаем приоритеты источников
        old_priority = self.config.SOURCE_PRIORITY.get(metadata.source, 0)
        new_priority = self.config.SOURCE_PRIORITY.get(new_source, 0)
        
        # Если новое значение из более надежного источника
        if new_priority > old_priority:
            # Логируем конфликт
            logger.info(
                f"Resolving conflict for {field_name}: "
                f"{metadata.value} ({metadata.source.value}) -> "
                f"{new_value} ({new_source.value})"
            )
            
            # Обновляем значение
            context.set_field(
                field_name,
                new_value,
                new_source,
                confidence=1.0 if new_source == DataSource.USER else metadata.confidence,
                reasoning=f"Заменяет {metadata.source.value}: {metadata.reasoning}"
            )
        
        return context
    
    def _analyze_user_history(self, context: Context) -> Dict[str, Any]:
        """
        Проанализировать историю пользователя для улучшения предположений.
        
        Args:
            context: Контекст с историей
            
        Returns:
            Словарь предпочтений пользователя
        """
        if not context.user_id:
            return {}
        
        # Анализируем историю диалога
        history = context.dialog_history or []
        if not history:
            return {}
        
        # Анализируем частоту выбора разных значений
        stats: Dict[str, Dict[str, int]] = {}
        for entry in history:
            event = entry.get('event', '')
            data = entry.get('data', {})
            
            # Ищем события выбора пользователя
            if event == 'user_choice' or event == 'field_set':
                field = data.get('field')
                value = data.get('value')
                
                if field and value:
                    if field not in stats:
                        stats[field] = {}
                    
                    value_str = str(value)
                    if value_str not in stats[field]:
                        stats[field][value_str] = 0
                    stats[field][value_str] += 1
        
        # Находим наиболее частые значения
        preferences: Dict[str, Any] = {}
        for field, values in stats.items():
            if values:
                most_common_value = max(values, key=values.get)
                # Пытаемся преобразовать обратно в нужный тип
                try:
                    # Пробуем float
                    preferences[field] = float(most_common_value)
                except ValueError:
                    # Оставляем строкой
                    preferences[field] = most_common_value
        
        return preferences
    
    def _calculate_confidence(
        self,
        field: str,
        context: Context,
        base_confidence: float
    ) -> float:
        """
        Рассчитать confidence с учетом контекста.
        
        Args:
            field: Название поля
            context: Контекст
            base_confidence: Базовая уверенность
            
        Returns:
            Скорректированная уверенность
        """
        confidence = base_confidence
        
        # Понижаем confidence, если мало данных
        data_points = sum([
            context.is_field_set('material'),
            context.is_field_set('diameter_start'),
            context.is_field_set('operation')
        ])
        
        if data_points < 2:
            confidence *= 0.7
        
        # Повышаем confidence для стандартных случаев
        if field == 'tool_material' and context.machine_type:
            if 'чпу' in context.machine_type.lower():
                confidence = min(confidence * 1.2, 1.0)
        
        # Учитываем противоречия
        if self._has_contradictions(field, context):
            confidence *= 0.5
        
        # Учитываем историю пользователя
        preferences = self._analyze_user_history(context)
        if field in preferences:
            confidence = min(confidence * 1.1, 1.0)
        
        return round(confidence, 2)
    
    def _has_contradictions(self, field: str, context: Context) -> bool:
        """
        Проверить наличие противоречий в контексте.
        
        Args:
            field: Название поля
            context: Контекст
            
        Returns:
            True если есть противоречия
        """
        # Например, чистовая обработка с большим припуском
        if field == 'mode' and context.mode == 'чистовая':
            if context.diameter_start and context.diameter_end:
                stock = (context.diameter_start - context.diameter_end) / 2
                if stock > 2.0:
                    return True
        
        return False
    
    def make_assumptions(self, context: Context) -> Context:
        """
        Сделать предположения для контекста.
        
        ВАЖНО: Предположения делаются ТОЛЬКО для инженерных запросов.
        Не делаем предположения для приветствий, команд и т.д.
        
        Args:
            context: Контекст для анализа
            
        Returns:
            Обновленный контекст
        """
        # Проверяем, есть ли хотя бы минимальные данные для инженерного запроса
        has_minimal_data = (
            context.is_field_set('material') or
            context.is_field_set('diameter_start') or
            context.is_field_set('operation') or
            context.is_field_set('standard_id')
        )
        
        if not has_minimal_data:
            return context
        
        # Получаем хеш контекста для кэширования
        context_hash = self._get_context_hash(context)
        
        # 1. Предположения о станке
        if not context.is_field_set('machine_type'):
            cached = self.cache.get(context_hash, 'machine_type')
            if cached:
                assumed_machine = cached
            else:
                assumed_machine = self._assume_machine_type(context)
                if assumed_machine:
                    self.cache.set(context_hash, 'machine_type', assumed_machine)
            
            if assumed_machine:
                confidence = self._calculate_confidence(
                    'machine_type',
                    context,
                    self.config.CONFIDENCE_MACHINE_TYPE
                )
                context.set_field(
                    'machine_type',
                    assumed_machine,
                    DataSource.ASSUMED,
                    confidence=confidence,
                    reasoning="Предположено на основе операции"
                )
        
        if not context.is_field_set('machine_power'):
            cached = self.cache.get(context_hash, 'machine_power')
            if cached:
                assumed_power = cached
            else:
                assumed_power = self._assume_machine_power(context)
                if assumed_power and self.validator.validate_assumption('machine_power', assumed_power):
                    self.cache.set(context_hash, 'machine_power', assumed_power)
            
            if assumed_power and self.validator.validate_assumption('machine_power', assumed_power):
                confidence = self._calculate_confidence(
                    'machine_power',
                    context,
                    self.config.CONFIDENCE_MACHINE_POWER
                )
                context.set_field(
                    'machine_power',
                    assumed_power,
                    DataSource.ASSUMED,
                    confidence=confidence,
                    reasoning="Типичная мощность для данного типа станка"
                )
        
        # 2. Предположения об инструменте
        if not context.is_field_set('tool_material'):
            cached = self.cache.get(context_hash, 'tool_material')
            if cached:
                assumed_tool = cached
            else:
                assumed_tool = self._assume_tool_material(context)
                if assumed_tool:
                    self.cache.set(context_hash, 'tool_material', assumed_tool)
            
            if assumed_tool:
                confidence = self._calculate_confidence(
                    'tool_material',
                    context,
                    self.config.CONFIDENCE_TOOL_MATERIAL
                )
                context.set_field(
                    'tool_material',
                    assumed_tool,
                    DataSource.ASSUMED,
                    confidence=confidence,
                    reasoning="Типичный инструмент для данного типа станка"
                )
        
        if not context.is_field_set('tool_radius'):
            cached = self.cache.get(context_hash, 'tool_radius')
            if cached:
                assumed_radius = cached
            else:
                assumed_radius = self._assume_tool_radius(context)
                if assumed_radius and self.validator.validate_assumption('tool_radius', assumed_radius):
                    self.cache.set(context_hash, 'tool_radius', assumed_radius)
            
            if assumed_radius and self.validator.validate_assumption('tool_radius', assumed_radius):
                confidence = self._calculate_confidence(
                    'tool_radius',
                    context,
                    self.config.CONFIDENCE_TOOL_RADIUS
                )
                context.set_field(
                    'tool_radius',
                    assumed_radius,
                    DataSource.ASSUMED,
                    confidence=confidence,
                    reasoning="Типичный радиус для данного типа обработки"
                )
        
        if not context.is_field_set('tool_overhang'):
            cached = self.cache.get(context_hash, 'tool_overhang')
            if cached:
                assumed_overhang = cached
            else:
                assumed_overhang = self._assume_tool_overhang(context)
                if assumed_overhang and self.validator.validate_assumption('tool_overhang', assumed_overhang):
                    self.cache.set(context_hash, 'tool_overhang', assumed_overhang)
            
            if assumed_overhang and self.validator.validate_assumption('tool_overhang', assumed_overhang):
                confidence = self._calculate_confidence(
                    'tool_overhang',
                    context,
                    self.config.CONFIDENCE_TOOL_OVERHANG
                )
                context.set_field(
                    'tool_overhang',
                    assumed_overhang,
                    DataSource.ASSUMED,
                    confidence=confidence,
                    reasoning="Типичный вылет для данного типа обработки"
                )
        
        # 3. Предположения о режиме обработки
        # Улучшенная проверка: учитываем confidence существующего значения
        mode_metadata = context.get_field_metadata('mode')
        if (not context.is_field_set('mode') or 
            (mode_metadata and mode_metadata.confidence < 0.3)) and \
           (context.diameter_start and context.diameter_end):
            cached = self.cache.get(context_hash, 'mode')
            if cached:
                assumed_mode = cached
            else:
                assumed_mode = self._assume_mode(context)
                if assumed_mode:
                    self.cache.set(context_hash, 'mode', assumed_mode)
            
            if assumed_mode:
                confidence = self._calculate_confidence(
                    'mode',
                    context,
                    self.config.CONFIDENCE_MODE
                )
                context.set_field(
                    'mode',
                    assumed_mode,
                    DataSource.ASSUMED,
                    confidence=confidence,
                    reasoning="Предположено на основе припуска"
                )
        
        # 4. Предположения о длине
        if not context.is_field_set('length'):
            cached = self.cache.get(context_hash, 'length')
            if cached:
                assumed_length = cached
            else:
                assumed_length = self._assume_length(context)
                if assumed_length and self.validator.validate_assumption('length', assumed_length):
                    self.cache.set(context_hash, 'length', assumed_length)
            
            if assumed_length and self.validator.validate_assumption('length', assumed_length):
                confidence = self._calculate_confidence(
                    'length',
                    context,
                    self.config.CONFIDENCE_LENGTH
                )
                context.set_field(
                    'length',
                    assumed_length,
                    DataSource.ASSUMED,
                    confidence=confidence,
                    reasoning="Типичная длина для данного диаметра"
                )
        
        return context
    
    def _assume_machine_type(self, context: Context) -> Optional[str]:
        """
        Предположить тип станка.
        
        ВАЖНО: Не делаем предположения без явных признаков инженерного запроса.
        """
        # Используем knowledge_service если доступен
        if self.knowledge_service and context.machine_type:
            # Можно попробовать найти более точную информацию
            pass
        
        # Если указана операция "токарка" → токарный ЧПУ
        if context.operation == 'токарка':
            return 'токарный ЧПУ'
        
        # Если указана операция "фрезерование" → фрезерный ЧПУ
        if context.operation == 'фрезерование':
            return 'фрезерный ЧПУ'
        
        # Если есть стандарт - предполагаем токарный
        if context.is_field_set('standard_id'):
            return 'токарный ЧПУ'
        
        return None
    
    def _assume_machine_power(self, context: Context) -> Optional[float]:
        """
        Предположить мощность станка.
        
        Использует knowledge_service если доступен.
        """
        # Используем knowledge_service если доступен
        if self.knowledge_service and context.machine_type:
            try:
                machine_info = self.knowledge_service.find_machine(context.machine_type)
                if machine_info and machine_info.get('power_kw'):
                    return float(machine_info['power_kw'])
            except Exception as e:
                logger.debug(f"Knowledge service lookup failed: {e}")
        
        # Fallback на типичные значения из конфигурации
        machine_type = context.machine_type or ''
        
        power_map = {
            'токарный ЧПУ': self.config.POWER_CNC_LATHE,
            'токарный ручной': self.config.POWER_MANUAL_LATHE,
            'фрезерный ЧПУ': self.config.POWER_CNC_MILL,
            'фрезерный ручной': self.config.POWER_MANUAL_MILL
        }
        
        for key, power in power_map.items():
            if key in machine_type.lower():
                return power
        
        return self.config.POWER_DEFAULT
    
    def _assume_tool_material(self, context: Context) -> Optional[str]:
        """Предположить материал инструмента."""
        machine_type = context.machine_type or ''
        
        # ЧПУ → твердый сплав (типично)
        if 'чпу' in machine_type.lower():
            return 'твердый сплав'
        
        # Ручной → быстрорез (типично)
        if 'ручной' in machine_type.lower():
            return 'быстрорез'
        
        return 'твердый сплав'
    
    def _assume_tool_radius(self, context: Context) -> Optional[float]:
        """Предположить радиус инструмента."""
        mode = context.mode or ''
        
        # Чистовая → меньший радиус
        if 'чистов' in mode.lower():
            return self.config.TOOL_RADIUS_FINISHING
        
        # Черновая → больший радиус
        if 'чернов' in mode.lower():
            return self.config.TOOL_RADIUS_ROUGHING
        
        return self.config.TOOL_RADIUS_DEFAULT
    
    def _assume_tool_overhang(self, context: Context) -> Optional[float]:
        """Предположить вылет инструмента."""
        # Типичный вылет для токарки
        if context.operation == 'токарка':
            return self.config.TOOL_OVERHANG_TURNING
        
        # Типичный вылет для фрезерования
        if context.operation == 'фрезерование':
            return self.config.TOOL_OVERHANG_MILLING
        
        return self.config.TOOL_OVERHANG_DEFAULT
    
    def _assume_mode(self, context: Context) -> Optional[str]:
        """Предположить режим обработки на основе припуска."""
        if not context.diameter_start or not context.diameter_end:
            return 'черновая'
        
        stock = (context.diameter_start - context.diameter_end) / 2
        
        # Большой припуск → черновая
        if stock > self.config.ROUGHING_THRESHOLD:
            return 'черновая'
        
        # Средний припуск → получистовая
        if stock > self.config.SEMI_FINISHING_THRESHOLD:
            return 'получистовая'
        
        # Маленький припуск → чистовая
        return 'чистовая'
    
    def _assume_length(self, context: Context) -> Optional[float]:
        """Предположить длину обработки."""
        # Если есть диаметр, предполагаем длину пропорционально
        if context.diameter_start:
            assumed_length = context.diameter_start * self.config.LENGTH_TO_DIAMETER_RATIO
            return max(
                self.config.MIN_LENGTH,
                min(assumed_length, self.config.MAX_LENGTH)
            )
        
        return 50.0
    
    def explain_assumption(self, field_name: str, context: Context) -> str:
        """
        Объяснить, почему было сделано предположение.
        
        Args:
            field_name: Имя поля
            context: Контекст
            
        Returns:
            Текстовое объяснение
        """
        metadata = context.get_field_metadata(field_name)
        if not metadata or metadata.source != DataSource.ASSUMED:
            return ""
        
        return metadata.reasoning or "Предположено на основе контекста"
    
    def record_feedback(
        self,
        field: str,
        assumed_value: Any,
        actual_value: Any,
        was_accepted: bool
    ):
        """
        Записать обратную связь по предположению.
        
        Args:
            field: Название поля
            assumed_value: Предполагаемое значение
            actual_value: Фактическое значение
            was_accepted: Было ли принято предположение
        """
        self.feedback_store.append({
            'field': field,
            'assumed': assumed_value,
            'actual': actual_value,
            'accepted': was_accepted,
            'timestamp': datetime.now()
        })
        
        # Анализируем и корректируем правила (можно расширить)
        if len(self.feedback_store) >= 10:
            self._analyze_feedback()
    
    def _analyze_feedback(self):
        """Анализировать обратную связь и корректировать правила."""
        if len(self.feedback_store) < 10:
            return
        
        # Группируем по полям
        field_stats: Dict[str, List[bool]] = {}
        for feedback in self.feedback_store:
            field = feedback['field']
            if field not in field_stats:
                field_stats[field] = []
            field_stats[field].append(feedback['accepted'])
        
        # Анализируем точность
        for field, results in field_stats.items():
            if len(results) >= 10:
                accuracy = sum(results) / len(results)
                if accuracy < 0.6:
                    logger.warning(
                        f"Low accuracy ({accuracy:.2f}) for {field} assumptions. "
                        f"Consider adjusting rules."
                    )