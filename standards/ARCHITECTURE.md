# Архитектура модуля стандартов

## Общая архитектура

Система стандартов построена по модульному принципу с четким разделением ответственности:

```
standards/
├── ingestion/          # Загрузка и парсинг исходных данных
├── normalization/      # Приведение к единой модели
├── models/            # Модели данных
├── registry/         # Реестр стандартов
├── calculations/      # Математические вычисления (ISO/GOST формулы)
├── business_logic/    # Требования и ограничения
├── equivalence/       # Эквивалентность стандартов
├── api/              # API для интеграции с ботом
├── downloader/       # Скачивание стандартов из интернета
└── cli/              # CLI команды
```

## Поток данных

```
Обозначение пользователя (M20, H7, Ra 1.6)
    ↓
designation_handler.process_designation()
    ↓
registry.search_by_designation() → StandardEntity
    ↓
requirement_engine.build_requirement() → ManufacturingRequirement
    ↓ (математические вычисления)
calculations/ → точные значения допусков, геометрия резьбы
    ↓
constraint_engine.generate_constraints() → ProcessConstraint[]
    ↓
process_planner.apply_constraints() → скорректированный план обработки
```

## Математические вычисления

Все вычисления выполняются строго по формулам ISO/GOST без LLM-угадываний:

### Геометрия резьбы
- **Формулы ISO 965-1**: H, h, d2, d3
- **Вычисление количества проходов**: на основе глубины резьбы
- **Требования к точности**: на основе шага и класса допуска

### IT допуски
- **Формула ISO 286**: i = 0.45 * ∛D + 0.001 * D
- **Классы допусков**: IT6 = 10i, IT7 = 16i, IT8 = 25i
- **Поля допусков**: вычисление верхних/нижних отклонений

### Посадки
- **Вычисление зазоров/натягов**: S_min, S_max
- **Определение типа посадки**: clearance/interference/transition
- **Производственные требования**: на основе типа посадки

### Шероховатость
- **Связь с подачей**: Ra ≈ (f²) / (32 * r)
- **Вычисление максимальной подачи**: f = √(Ra * 32 * r)
- **Требования к обработке**: на основе значения Ra

## Интеграция с process_planner

ConstraintEngine генерирует ограничения, которые передаются в planner:

```python
constraints = constraint_engine.generate_constraints(requirement)

for constraint in constraints:
    if constraint.constraint_id == "finish_turning_required":
        planner.add_operation("finish_turning")
    elif constraint.constraint_id == "low_feed_required":
        planner.limit_feed(constraint.parameters["max_feed_mm_rev"])
    # и т.д.
```

## Логирование

Каждое решение логируется:
- Исходный стандарт
- Вычисленные параметры
- Наложенные ограничения
- Изменённые режимы

## Запреты

❌ Нельзя:
- Угадывать параметры
- Принимать решения без формулы
- Использовать LLM вместо таблиц
- Смешивать парсер и бизнес-логику

✅ Можно:
- Использовать только математические формулы
- Проверять результаты тестами
- Логировать все вычисления
- Разделять слои архитектуры
