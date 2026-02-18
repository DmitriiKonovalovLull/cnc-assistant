# Улучшения модуля валидации

## Критические исправления

### 1. ✅ Защита от переполнения в расчетах

**Проблема:** Функция `_calculate_cutting_speed` не имела защиты от очень больших чисел, что могло привести к переполнению.

**Решение:**
- Добавлена проверка на значения > 1e6 и < 1e-6
- Добавлена обработка `OverflowError`
- Добавлена проверка на NaN/Inf

**Код:**
```python
def _calculate_cutting_speed(diameter_mm: float, rpm: float) -> float:
    # Защита от переполнения
    if diameter_mm > 1e6 or rpm > 1e6:
        return 0.0
    
    # Защита от очень маленьких значений
    if diameter_mm < 1e-6 or rpm < 1e-6:
        return 0.0
    
    try:
        vc = math.pi * diameter_mm * rpm / 1000
        if math.isnan(vc) or math.isinf(vc):
            return 0.0
        return vc
    except OverflowError:
        return 0.0
```

### 2. ✅ Валидация единиц измерения

**Проблема:** Нет проверки, что пользователь не перепутал мм/об с мм/мин и т.д.

**Решение:** Добавлен класс `UnitValidator` с автоматическим определением возможных ошибок в единицах измерения.

**Класс:** `UnitValidator`
- Метод `detect_possible_unit_mismatch()` - определяет возможную ошибку в единицах
- Метод `add_unit_warning()` - добавляет предупреждение в результат валидации

**Пример использования:**
```python
UnitValidator.add_unit_warning(result, 'feed', 150.0)  # Предупредит о возможной ошибке
```

## Серьезные улучшения

### 3. ✅ Конфигурация допусков

**Проблема:** Магические числа в адаптивном допуске затрудняли настройку.

**Решение:** Создан класс `ToleranceConfig` с централизованной конфигурацией допусков.

**Класс:** `ToleranceConfig`
- `BASE_TOLERANCE` - базовые допуски для разных типов параметров (в процентах)
- `MIN_ABSOLUTE` - минимальные абсолютные допуски
- Метод `get_tolerance()` - получение адаптивного допуска

**Пример:**
```python
tolerance = ToleranceConfig.get_tolerance('diameter', 100.0)  # Вернет адаптивный допуск
```

### 4. ✅ Проверка взаимосвязи параметров

**Проблема:** Нет проверки, что глубина резания не больше припуска и т.д.

**Решение:** Добавлен метод `validate_mutual_relations()` в класс `Validator`.

**Проверки:**
- Глубина резания vs припуск
- Подача vs радиус пластины

**Пример:**
```python
result = validator.validate_mutual_relations(context)
```

### 5. ✅ Пакетная валидация

**Проблема:** При массовой обработке данных нужна пакетная валидация.

**Решение:** Добавлен класс `BatchValidator` для пакетной обработки контекстов.

**Класс:** `BatchValidator`
- Метод `validate_batch()` - валидирует список контекстов
- Метод `get_invalid_indices()` - получает индексы невалидных контекстов
- Метод `get_invalid_contexts()` - получает невалидные контексты с результатами

**Пример:**
```python
batch_validator = BatchValidator(validator)
stats = batch_validator.validate_batch(contexts)
```

### 6. ✅ Пользовательские правила валидации

**Проблема:** Нет возможности добавлять собственные правила валидации.

**Решение:** Добавлены классы `ValidationRule` и `ExtendableValidator`.

**Класс:** `ValidationRule`
- Определяет пользовательское правило валидации
- Поддерживает уровни серьезности ('error' или 'warning')

**Класс:** `ExtendableValidator`
- Расширяет базовый `Validator`
- Позволяет добавлять пользовательские правила через `add_rule()`

**Пример:**
```python
rule = ValidationRule(
    name='custom_check',
    condition=lambda ctx: 'required_field' in ctx,
    error_message='Отсутствует обязательное поле',
    severity='error'
)

extendable_validator = ExtendableValidator()
extendable_validator.add_rule(rule)
```

### 7. ✅ Кэширование результатов валидации

**Проблема:** Многократные запросы к валидации для одинаковых контекстов.

**Решение:** Добавлен класс `CachedValidator` с кэшированием результатов.

**Класс:** `CachedValidator`
- Использует `lru_cache` для кэширования
- Создает хеш-ключ из нормализованного контекста
- Исключает временные поля из ключа кэша

**Пример:**
```python
cached_validator = CachedValidator(cache_size=1000)
result = cached_validator.validate_full_context(context)  # Результат кэшируется
```

### 8. ✅ Многоязычные сообщения

**Проблема:** Сообщения валидации только на русском языке.

**Решение:** Добавлен класс `I18nValidator` с поддержкой многоязычных сообщений.

**Класс:** `I18nValidator`
- Поддерживает русский и английский языки
- Метод `_t()` для получения переведенных сообщений
- Легко расширяется для других языков

**Пример:**
```python
i18n_validator = I18nValidator(lang='en')
result = i18n_validator.validate_material('steel')
```

## Архитектурные улучшения

### 9. ✅ Взвешенные правила для ML

**Проблема:** Нет системы оценки валидности для машинного обучения.

**Решение:** Добавлены классы `WeightedValidationRule` и `MLValidator`.

**Класс:** `MLValidator`
- Метод `calculate_validation_score()` - рассчитывает оценку валидности (0-1)
- Метод `get_validation_factors()` - получает факторы валидации для объяснения решений

**Пример:**
```python
ml_validator = MLValidator()
rule = WeightedValidationRule(
    name='diameter_check',
    weight=0.3,
    condition=lambda ctx: 0.0 if 10 <= ctx.get('diameter', 0) <= 1000 else 1.0,
    description='Проверка диаметра'
)
ml_validator.add_weighted_rule(rule)
score = ml_validator.calculate_validation_score(context)
```

### 10. ✅ Обучение на обратной связи

**Проблема:** Валидатор не адаптируется на основе пользовательской обратной связи.

**Решение:** Добавлен класс `FeedbackAwareValidator` с поддержкой обучения.

**Класс:** `FeedbackAwareValidator`
- Метод `record_feedback()` - записывает обратную связь
- Метод `_adjust_rules()` - корректирует правила на основе обратной связи
- Метод `get_adjusted_range()` - получает скорректированный диапазон

**Пример:**
```python
feedback_validator = FeedbackAwareValidator()
result = feedback_validator.validate_full_context(context)
feedback_validator.record_feedback(context, result, user_accepted=True)
```

## Детальные улучшения

### 11. ✅ Оптимизация поиска по алиасам

**Проблема:** Неэффективный поиск по алиасам материалов.

**Решение:** Добавлен индекс алиасов `_alias_index` в `ValidationDatabase`.

**Изменения:**
- Метод `_build_alias_index()` - строит индекс при инициализации
- Метод `get_material()` - использует индекс для быстрого поиска

### 12. ✅ Защита от отрицательных значений в адаптивном допуске

**Проблема:** Функция `_adaptive_tolerance` не проверяла отрицательные значения.

**Решение:** Добавлена защита от отрицательных и очень маленьких значений.

**Код:**
```python
def _adaptive_tolerance(value: float, base_tolerance: float = 0.1, min_abs: float = 1.0) -> float:
    abs_value = abs(value)
    if abs_value < 1e-6:
        return min_abs
    return max(base_tolerance * abs_value, min_abs)
```

## Использование новых возможностей

### Базовое использование

```python
from app.core.validator import Validator, ValidationLevel

validator = Validator(level=ValidationLevel.STANDARD)
result = validator.validate_full_context(context)
```

### С валидацией единиц измерения

```python
from app.core.validator import Validator, UnitValidator

validator = Validator()
result = validator.validate_number(150.0, 'feed', 'feed_mm_per_rev')
# UnitValidator автоматически добавит предупреждение, если нужно
```

### С пакетной валидацией

```python
from app.core.validator import Validator, BatchValidator

validator = Validator()
batch_validator = BatchValidator(validator)
stats = batch_validator.validate_batch(contexts)
```

### С пользовательскими правилами

```python
from app.core.validator import ExtendableValidator, ValidationRule

validator = ExtendableValidator()
rule = ValidationRule(
    name='check_ap',
    condition=lambda ctx: ctx.get('ap', 0) <= ctx.get('stock', 0),
    error_message='Глубина резания не может быть больше припуска',
    severity='error'
)
validator.add_rule(rule)
```

### С кэшированием

```python
from app.core.validator import CachedValidator

validator = CachedValidator(cache_size=1000)
result = validator.validate_full_context(context)  # Кэшируется
```

### С многоязычными сообщениями

```python
from app.core.validator import I18nValidator

validator = I18nValidator(lang='en')
result = validator.validate_material('steel')
```

### С ML оценкой

```python
from app.core.validator import MLValidator, WeightedValidationRule

validator = MLValidator()
rule = WeightedValidationRule(
    name='diameter_check',
    weight=0.3,
    condition=lambda ctx: 0.0 if 10 <= ctx.get('diameter', 0) <= 1000 else 1.0,
    description='Проверка диаметра'
)
validator.add_weighted_rule(rule)
score = validator.calculate_validation_score(context)
```

### С обратной связью

```python
from app.core.validator import FeedbackAwareValidator

validator = FeedbackAwareValidator()
result = validator.validate_full_context(context)
validator.record_feedback(context, result, user_accepted=True)
```

## Обратная совместимость

Все изменения обратно совместимы. Существующий код продолжит работать без изменений. Новые классы являются расширениями базового `Validator` и могут использоваться по мере необходимости.
