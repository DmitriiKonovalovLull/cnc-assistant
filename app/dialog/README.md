# Dialog System - Система обработки диалогов

## Описание

Production-ready система обработки входящих сообщений для CNC Telegram assistant.

**Принципы:**
- ✅ Строгая State Machine с контролем переходов
- ✅ Rule-based Intent Detection (без LLM)
- ✅ Разделение состояния и контекста
- ✅ Защита от поломки логики
- ✅ Полное логирование

## Архитектура

```
Incoming message
    ↓
Preprocessing
    ↓
Intent detection (rule-based)
    ↓
State validation
    ↓
State transition
    ↓
Handler execution
    ↓
Response
```

## Компоненты

### 1. StateMachine (`state_machine.py`)

Управляет состояниями пользователей:
- `IDLE` - начальное состояние
- `WAITING_MATERIAL` - ожидание материала
- `WAITING_DIMENSIONS` - ожидание размеров
- `WAITING_OPERATION` - ожидание операции
- `CALCULATION_READY` - готов к расчету
- `STANDARD_LOOKUP` - поиск стандарта
- `UPLOAD_MODE` - режим загрузки
- `ERROR_STATE` - ошибка

**Правила:**
- Только допустимые переходы разрешены
- Все переходы логируются
- Нельзя менять state напрямую, только через `transition()`

### 2. IntentDetector (`intent_detector.py`)

Rule-based детектор интентов (без LLM):
- `RESET` - сброс (высший приоритет)
- `STANDARD_REQUEST` - запрос стандарта (высокий приоритет)
- `CALCULATION_REQUEST` - запрос расчета
- `GREETING` - приветствие
- `HELP` - помощь
- `UPLOAD_STANDARD` - загрузка стандарта
- `UNKNOWN` - неизвестный

**Приоритеты:**
1. RESET
2. STANDARD_REQUEST
3. CALCULATION_REQUEST
4. GREETING
5. HELP
6. UNKNOWN

### 3. ContextManager (`context_manager.py`)

Управляет контекстом диалога:
- Материал
- Размеры (диаметры, длина)
- Операция
- Количество
- Стандарт

**Методы:**
- `clear()` - очистить весь контекст
- `clear_calculation()` - очистить только расчетные данные
- `clear_standard()` - очистить только стандарт
- `update()` - обновить контекст

### 4. Validator (`validators.py`)

Валидация входных данных:
- `validate_diameter()` - диаметр
- `validate_dimension_range()` - диапазон размеров
- `validate_material()` - материал
- `validate_operation()` - операция
- `validate_quantity()` - количество
- `extract_data_from_message()` - извлечение данных из сообщения

### 5. MessageProcessor (`message_processor.py`)

Главный процессор сообщений:
- Объединяет все компоненты
- Реализует полный pipeline обработки
- Обрабатывает конфликты интентов
- Управляет переходами состояний

## Использование

### Базовое использование

```python
from app.dialog import MessageProcessor

processor = MessageProcessor()

# Обработка сообщения
result = processor.process(user_id=123, message="ОСТ 33056-80")

print(result['response'])  # Ответ пользователю
print(result['state'])     # Новое состояние
print(result['intent'])    # Определенный интент
```

### Интеграция с Telegram ботом

```python
from app.dialog import MessageProcessor

processor = MessageProcessor()

async def handle_message(user_id: int, message: str):
    result = processor.process(user_id, message)
    
    # Отправляем ответ
    await bot.send_message(user_id, result['response'])
    
    # Логируем
    logger.info(f"State: {result['state'].value}, Intent: {result['intent'].value}")
```

## Примеры обработки

### Пример 1: Запрос стандарта

```python
result = processor.process(user_id=1, message="ОСТ 33056-80")
# Intent: STANDARD_REQUEST
# State: STANDARD_LOOKUP
# Response: "🔍 Ищу стандарт: ОСТ 33056-80..."
```

### Пример 2: Запрос расчета

```python
result = processor.process(user_id=1, message="токарка алюминий 50 до 200")
# Intent: CALCULATION_REQUEST
# State: CALCULATION_READY (если все данные есть)
# Response: "✅ Данные собраны..."
```

### Пример 3: Сброс

```python
result = processor.process(user_id=1, message="сброс")
# Intent: RESET
# State: IDLE
# Context: очищен
# Response: "✅ Состояние сброшено..."
```

### Пример 4: Приветствие

```python
result = processor.process(user_id=1, message="привет")
# Intent: GREETING
# State: не меняется (остается текущим)
# Response: "Привет! Чем могу помочь?"
```

## Защита от поломки логики

1. **Логирование всех операций:**
   - Входящие сообщения
   - Переходы состояний
   - Определенные интенты

2. **Валидация переходов:**
   - Только допустимые переходы разрешены
   - Недопустимые переходы блокируются и логируются

3. **Валидация входных данных:**
   - Невалидный ввод не меняет состояние
   - Пользователь получает понятное сообщение об ошибке

4. **Разделение ответственности:**
   - State Machine управляет только состояниями
   - Context Manager управляет только контекстом
   - Validator валидирует только данные

## Тестирование

```bash
pytest tests/test_dialog/
```

Тесты покрывают:
- Приоритеты интентов
- Переходы состояний
- Механизм сброса
- Переопределение стандартом
- Обработку невалидного ввода

## Расширение

### Добавление нового интента

1. Добавить в `constants.py`:
```python
class Intent(Enum):
    NEW_INTENT = "new_intent"
```

2. Добавить приоритет в `INTENT_PRIORITY`

3. Добавить детекцию в `IntentDetector._is_new_intent()`

4. Добавить обработку в `MessageProcessor._handle_new_intent()`

### Добавление нового состояния

1. Добавить в `constants.py`:
```python
class DialogState(Enum):
    NEW_STATE = "new_state"
```

2. Добавить допустимые переходы в `ALLOWED_TRANSITIONS`

3. Добавить обработку в `MessageProcessor._handle_by_state()`

## Логирование

Все операции логируются:
- `INFO` - нормальные операции (переходы, обработка)
- `WARNING` - блокированные переходы, невалидный ввод
- `DEBUG` - детальная информация для отладки

Формат логов:
```
INFO: State TRANSITION: user_id=123, idle -> waiting_operation, reason=calculation_request
INFO: Intent detected: calculation_request (confidence=0.80) for message: токарка алюминий
```
