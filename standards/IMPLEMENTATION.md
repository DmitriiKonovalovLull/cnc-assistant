# Реализация системы стандартов

## ✅ Реализовано

### 1. Математические вычисления (`calculations/`)

#### Геометрия резьбы (`thread_geometry.py`)
- ✅ Формулы ISO 965-1: H, h, d2, d3
- ✅ Вычисление количества проходов
- ✅ Требования к точности на основе шага и класса допуска

#### IT допуски (`tolerance_calculator.py`)
- ✅ Формула базовой единицы: i = 0.45 * ∛D + 0.001 * D
- ✅ Вычисление IT классов: IT6 = 10i, IT7 = 16i, IT8 = 25i
- ✅ Вычисление полей допусков (H7, g6) с отклонениями

#### Посадки (`fit_calculator.py`)
- ✅ Вычисление зазоров/натягов: S_min, S_max
- ✅ Определение типа посадки
- ✅ Производственные требования

#### Шероховатость (`surface_roughness.py`)
- ✅ Формула связи с подачей: Ra ≈ (f²) / (32 * r)
- ✅ Вычисление максимальной подачи
- ✅ Требования к обработке

### 2. Улучшенные движки

#### RequirementEngine
- ✅ Использует математические вычисления для точных значений
- ✅ Вычисляет геометрию резьбы
- ✅ Вычисляет точные значения допусков
- ✅ Вычисляет параметры посадок
- ✅ Сохраняет вычисленные значения в metadata

#### ConstraintEngine
- ✅ Генерирует ограничения на основе математических вычислений
- ✅ Определяет требования к чистовой обработке по допуску
- ✅ Вычисляет ограничения подачи по шероховатости
- ✅ Генерирует ограничения для резьбы и посадок

### 3. Тесты (`tests/standards/`)

- ✅ `test_thread_geometry.py` - проверка всех формул геометрии резьбы
- ✅ `test_tolerance_calculator.py` - проверка формул IT допусков
- ✅ `test_fits.py` - проверка вычислений посадок
- ✅ `test_surface_roughness.py` - проверка связи шероховатости с подачей
- ✅ `test_equivalence.py` - проверка движка эквивалентности
- ✅ `test_constraints.py` - проверка генерации ограничений
- ✅ `test_downloader.py` - проверка модуля скачивания
- ✅ `test_integration_standard_to_planner.py` - интеграционные тесты

### 4. Модуль скачивания (`downloader/`)

- ✅ `StandardDownloader` - скачивание стандартов из интернета
- ✅ Проверка целостности по SHA256
- ✅ Версионирование и метаданные
- ✅ Retry при ошибках сети
- ✅ Кэширование

### 5. CLI команды (`cli/`)

- ✅ `update_standards.py` - команда обновления базы стандартов
- ✅ Интеграция в `main.py` (пункт 4)
- ✅ Команда запуска тестов (пункт 5)

### 6. Интеграция

- ✅ Автозагрузка стандартов при старте `main.py`
- ✅ Автозагрузка стандартов при старте Telegram бота
- ✅ Улучшенный `designation_handler` с показом вычисленных значений
- ✅ Все вычисления логируются

## Примеры использования

### Вычисление геометрии резьбы

```python
from standards.calculations import calculate_thread_geometry

thread = calculate_thread_geometry(diameter=42.0, pitch=1.5)
print(f"Глубина резьбы: {thread.thread_depth:.3f} мм")
print(f"Средний диаметр: {thread.pitch_diameter:.3f} мм")
```

### Вычисление IT допуска

```python
from standards.calculations import calculate_it_tolerance

tolerance = calculate_it_tolerance(diameter_mm=50.0, it_grade=7)
print(f"IT7 для Ø50: {tolerance:.4f} мм")
```

### Полный путь от обозначения до ограничений

```python
from standards.api.designation_handler import process_designation

result = process_designation("Ø50 H7")
# result содержит:
# - entity: StandardEntity
# - requirement: ManufacturingRequirement (с вычисленными значениями)
# - constraints: List[ProcessConstraint]
# - message: готовое сообщение для пользователя
```

## Запуск тестов

```bash
# Все тесты
pytest tests/standards -v

# Конкретный модуль
pytest tests/standards/test_thread_geometry.py -v

# С покрытием
pytest tests/standards --cov=standards --cov-report=html
```

## Обновление стандартов

```bash
# Через main.py
python main.py  # выбрать пункт 4

# Напрямую
python standards/cli/update_standards.py update-standards
```

## Соответствие требованиям

✅ Все вычисления выполняются строго по формулам ISO/GOST  
✅ Нет LLM-угадываний  
✅ Все решения логируются  
✅ Модульная архитектура  
✅ Полное покрытие тестами  
✅ Интеграция с planner через constraints  
✅ Масштабируемость до 200+ стандартов  
