# Тесты модуля стандартов

Полное покрытие тестами модуля стандартов с проверкой всех формул и интеграций.

## Структура тестов

- `test_thread_geometry.py` - Тесты геометрии резьбы (ISO 965-1)
- `test_tolerance_calculator.py` - Тесты вычислений IT допусков (ISO 286)
- `test_fits.py` - Тесты вычислений посадок
- `test_surface_roughness.py` - Тесты связи шероховатости с параметрами обработки
- `test_equivalence.py` - Тесты движка эквивалентности стандартов
- `test_constraints.py` - Тесты генерации технологических ограничений
- `test_downloader.py` - Тесты модуля скачивания стандартов
- `test_integration_standard_to_planner.py` - Интеграционные тесты полного пути

## Запуск тестов

```bash
# Все тесты стандартов
pytest tests/standards -v

# Конкретный файл
pytest tests/standards/test_thread_geometry.py -v

# С покрытием
pytest tests/standards --cov=standards --cov-report=html
```

## Проверяемые формулы

### Геометрия резьбы
- H = (√3 / 2) * P
- h = 0.61343 * P
- d2 = d - 0.64952 * P
- d3 = d - 1.22687 * P

### IT допуски
- i = 0.45 * ∛D + 0.001 * D
- IT6 = 10i
- IT7 = 16i
- IT8 = 25i

### Шероховатость
- Ra ≈ (f²) / (32 * r)
- f = √(Ra * 32 * r)

### Посадки
- S_min = D_hole_min - D_shaft_max
- S_max = D_hole_max - D_shaft_min

## Требования

- pytest >= 7.4.0
- Все зависимости из requirements.txt
