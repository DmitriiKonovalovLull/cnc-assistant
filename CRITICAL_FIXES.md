# Критические исправления логики Telegram CNC Assistant

## Статус: ГОТОВО ✅

Исправлены все критические логические ошибки и добавлен раздельный режим работы.

## Исправления

### 1. Полный reset при /start ✅

**Проблема:** `/start` не делал полный reset, показывал старую работу

**Решение:**
- `/start` теперь полностью очищает:
  - State → IDLE
  - Mode → IDLE
  - Context → полностью удаляется
  - Redis context → удаляется
- НЕ показывает "Я помню предыдущую работу"
- НЕ восстанавливает старые диаметры

**Файлы:**
- `app/bot/telegram_bot.py` - исправлен `cmd_start()`
- `app/bot/telegram_bot/handlers/commands.py` - исправлен `cmd_start()`
- `app/dialog/message_processor.py` - добавлен `_handle_start_command()`

### 2. Разделение режимов ✅

**Добавлен enum `DialogMode`:**
- `IDLE` - начальное состояние
- `STANDARD_MODE` - режим работы со стандартами
- `CNC_CALC_MODE` - режим расчета режимов резания
- `SIMPLE_CALCULATOR_MODE` - математический калькулятор
- `PROJECT_MODE` - режим работы с проектами (требует номер работы)

**Файлы:**
- `app/dialog/constants.py` - добавлен `DialogMode`
- `app/dialog/mode_manager.py` - новый менеджер режимов

### 3. STANDARD_MODE защита ✅

**Поведение:**
- Если найден стандарт → `mode = STANDARD_MODE`
- Очищается расчетный контекст
- Запрещен парсинг размеров
- НЕ требуется номер работы
- НЕ предлагается "применить к текущей"

**Выход из STANDARD_MODE:**
- "просто посчитать режимы" → `mode = CNC_CALC_MODE`
- Очищается контекст стандарта

**Файлы:**
- `app/dialog/message_processor.py` - добавлена обработка `STANDARD_MODE`
- `app/dialog/intent_detector.py` - улучшено определение расчета

### 4. Убран обязательный номер работы ✅

**Поведение:**
- Для простого расчета номер работы НЕ требуется
- Создается временная in-memory задача без номера
- Номер требуется только в `PROJECT_MODE` (отдельно)

**Файлы:**
- `app/dialog/message_processor.py` - добавлен флаг `no_work_number_required` в metadata

### 5. Обычный калькулятор ✅

**Триггеры:**
- "калькулятор"
- "посчитать"
- "calc"
- Математические выражения: "2+2", "120*3.14", "sqrt(16)"

**Парсер выражений:**
- Безопасный парсинг через `ast.parse` с whitelist
- Разрешено: `+`, `-`, `*`, `/`, `**`, `sqrt()`, `sin()`, `cos()`, `pi`, `e`
- НЕ используется `eval()` напрямую

**Поведение:**
- Если выражение → `mode = SIMPLE_CALCULATOR_MODE`
- Возвращает результат
- НЕ меняет CNC контекст

**Файлы:**
- `app/dialog/expression_calculator.py` - новый парсер выражений
- `app/dialog/message_processor.py` - обработка калькулятора

### 6. Защита от числовых ошибок ✅

**Правила:**
- Размеры парсятся ТОЛЬКО если:
  - `mode == CNC_CALC_MODE`
  - И `state == WAITING_DIMENSIONS`
- Числа > 2000 мм отклоняются
- Числа из стандартов игнорируются

**Файлы:**
- `app/dialog/validators.py` - улучшена валидация
- `app/dialog/message_processor.py` - проверка режима перед парсингом

### 7. Новый MessageProcessor Pipeline ✅

**Порядок обработки:**
1. Check /start (полный reset)
2. Detect calculator expression
3. Detect intent
4. Detect standard
5. Route by mode
6. Route by state

**Приоритет интентов:**
1. /start
2. RESET
3. Calculator expression
4. Standard request
5. CNC calculation
6. Other

**Файлы:**
- `app/dialog/message_processor.py` - полностью переработан pipeline

## Результаты

### До исправлений:
```
/start → показывает старую работу ❌
ОСТ 33079-80 → создает диаметр 33079 мм ❌
2+2 → не работает ❌
"просто посчитать" → требует номер работы ❌
```

### После исправлений:
```
/start → чистое приветствие ✅
ОСТ 33079-80 → STANDARD_MODE, размеры не парсятся ✅
2+2 → 4 ✅
"просто посчитать режимы" → CNC_CALC_MODE, номер не требуется ✅
```

## Тесты

Созданы unit тесты в `tests/test_dialog/test_mode_separation.py`:
- `test_start_full_reset()` - полный reset при /start
- `test_standard_does_not_parse_numbers()` - стандарт не парсит числа
- `test_simple_calculator_expression()` - математический калькулятор
- `test_switch_from_standard_to_calc()` - переключение режимов
- `test_no_work_number_required()` - номер работы не требуется
- `test_large_number_rejected()` - большие числа отклоняются
- `test_calculator_does_not_change_cnc_context()` - калькулятор не меняет контекст
- `test_dimensions_only_in_cnc_calc_mode()` - размеры только в правильном режиме

## Статус

✅ Все исправления реализованы
✅ Тесты созданы
✅ Код компилируется без ошибок
✅ Готово к использованию
