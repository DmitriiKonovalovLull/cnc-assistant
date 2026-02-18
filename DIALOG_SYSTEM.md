# ✅ Dialog System - Система обработки диалогов

## Статус: ГОТОВО ✅

Создана полностью рабочая система обработки входящих сообщений с строгой архитектурой.

## Проблемы которые решены

✅ **Состояние ломается** → Строгая State Machine с контролем переходов
✅ **Бот отвечает не тем сценарием** → Приоритеты интентов и правильная маршрутизация
✅ **Интенты конфликтуют** → Четкая система приоритетов
✅ **Нет приоритетов** → Реализована система приоритетов интентов
✅ **Нет state machine** → Полноценная State Machine с валидацией

## Созданные файлы

### Основные модули

✅ `app/dialog/constants.py` - Константы (состояния, интенты, переходы)
✅ `app/dialog/state_machine.py` - State Machine с контролем переходов
✅ `app/dialog/intent_detector.py` - Rule-based детектор интентов
✅ `app/dialog/context_manager.py` - Управление контекстом диалога
✅ `app/dialog/validators.py` - Валидация входных данных
✅ `app/dialog/message_processor.py` - Главный pipeline обработки
✅ `app/dialog/__init__.py` - Экспорты модуля
✅ `app/dialog/integration_example.py` - Пример интеграции

### Тесты

✅ `tests/test_dialog/test_intent_priority.py` - Тесты приоритетов
✅ `tests/test_dialog/test_state_transitions.py` - Тесты переходов
✅ `tests/test_dialog/test_reset.py` - Тесты сброса
✅ `tests/test_dialog/test_standard_override.py` - Тесты переопределения
✅ `tests/test_dialog/test_invalid_input.py` - Тесты невалидного ввода

### Документация

✅ `app/dialog/README.md` - Полная документация системы
✅ `DIALOG_SYSTEM.md` - Этот файл

## Архитектура

```
Incoming message
    ↓
Preprocessing
    ↓
Intent detection (rule-based, не LLM)
    ↓
State validation
    ↓
State transition
    ↓
Handler execution
    ↓
Response
```

## Основные компоненты

### 1. StateMachine

Управляет состояниями с строгим контролем:
- Только допустимые переходы разрешены
- Все переходы логируются
- История переходов сохраняется
- Метод `reset()` для сброса

**Состояния:**
- `IDLE` - начальное
- `WAITING_MATERIAL` - ожидание материала
- `WAITING_DIMENSIONS` - ожидание размеров
- `WAITING_OPERATION` - ожидание операции
- `CALCULATION_READY` - готов к расчету
- `STANDARD_LOOKUP` - поиск стандарта
- `UPLOAD_MODE` - режим загрузки
- `ERROR_STATE` - ошибка

### 2. IntentDetector

Rule-based детектор (без LLM):
- Regex паттерны
- Ключевые слова
- Структурированные паттерны (стандарты, размеры)

**Приоритеты:**
1. RESET (высший)
2. STANDARD_REQUEST
3. CALCULATION_REQUEST
4. GREETING
5. HELP
6. UNKNOWN

### 3. ContextManager

Управляет контекстом отдельно от состояния:
- Материал, размеры, операция, количество, стандарт
- Методы `clear()`, `clear_calculation()`, `clear_standard()`
- Контекст можно очищать частично

### 4. Validator

Валидация входных данных:
- Диаметры, диапазоны размеров
- Материалы, операции, количество
- Извлечение данных из сообщения

### 5. MessageProcessor

Главный pipeline:
- Объединяет все компоненты
- Обрабатывает конфликты интентов
- Управляет переходами состояний
- Защита от поломки логики

## Использование

### Базовое использование

```python
from app.dialog import MessageProcessor

processor = MessageProcessor()
result = processor.process(user_id=123, message="ОСТ 33056-80")

print(result['response'])  # Ответ пользователю
print(result['state'])      # Новое состояние
print(result['intent'])     # Определенный интент
```

### Интеграция с handler.py

См. `app/dialog/integration_example.py` для примера постепенной интеграции.

## Примеры обработки

### Запрос стандарта

```python
result = processor.process(user_id=1, message="ОСТ 33056-80")
# Intent: STANDARD_REQUEST
# State: STANDARD_LOOKUP
# Сбрасывает расчетный контекст
```

### Запрос расчета

```python
result = processor.process(user_id=1, message="токарка алюминий 50 до 200")
# Intent: CALCULATION_REQUEST
# State: CALCULATION_READY (если все данные есть)
```

### Сброс

```python
result = processor.process(user_id=1, message="сброс")
# Intent: RESET
# State: IDLE
# Context: полностью очищен
```

### Приветствие

```python
result = processor.process(user_id=1, message="привет")
# Intent: GREETING
# State: не меняется (остается текущим)
```

## Защита от поломки логики

1. **Логирование всех операций**
2. **Валидация переходов** - только допустимые переходы
3. **Валидация входных данных** - невалидный ввод не меняет состояние
4. **Разделение ответственности** - каждый компонент отвечает за свою область

## Тестирование

```bash
pytest tests/test_dialog/
```

Все тесты проходят успешно:
- ✅ Приоритеты интентов
- ✅ Переходы состояний
- ✅ Механизм сброса
- ✅ Переопределение стандартом
- ✅ Обработка невалидного ввода

## Следующие шаги

1. ✅ Базовая архитектура создана
2. ✅ State Machine реализована
3. ✅ Intent Detector реализован
4. ✅ Context Manager реализован
5. ✅ Validators реализованы
6. ✅ MessageProcessor реализован
7. ✅ Тесты написаны
8. ⏭️ Интеграция с handler.py (пример создан)
9. ⏭️ Интеграция с расчетным движком
10. ⏭️ Интеграция с системой стандартов

## Примечания

- Система полностью rule-based, без использования LLM
- Код чистый, модульный, расширяемый
- Нет циклических зависимостей
- Production-ready архитектура
- Полное логирование всех операций
