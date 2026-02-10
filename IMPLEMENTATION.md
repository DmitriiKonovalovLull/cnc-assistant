# Реализация архитектуры CNC Assistant

## ✅ Что было создано

### 1. Core модули (ядро системы)

#### `app/core/context.py` - Единый объект состояния
- Класс `Context` - хранит все данные о текущей задаче
- Класс `FieldMetadata` - метаданные полей (источник, уверенность, reasoning)
- Enum `DataSource` - источник данных (USER, ASSUMED, DEFAULT, INFERRED)
- Методы для работы с полями, историей диалога, уверенностью

#### `app/core/parser.py` - Парсер текста
- Класс `TextParser` - извлекает данные из пользовательского ввода
- Класс `ParsedData` - результат парсинга
- Распознавание: материалы, операции, режимы, диаметры, числа, параметры режимов

#### `app/core/assumptions.py` - Двигатель предположений
- Класс `AssumptionEngine` - делает разумные предположения
- Предположения о станке, инструменте, режиме обработки, длине
- Всегда помечает source=ASSUMED с указанием confidence и reasoning

### 2. Services модули (сервисы)

#### `app/services/knowledge_service.py` - Сервис знаний
- Класс `KnowledgeService` - работа с базой знаний
- Загрузка материалов, инструментов, станков из JSON
- Поиск и нормализация данных
- Создание базовых данных по умолчанию если файлов нет

### 3. Bot модули (бот)

#### `app/bot/handler.py` - Главный обработчик
- Класс `MessageHandler` - оркестратор системы
- Связывает парсер, контекст, калькулятор, assumptions
- Решает: считать, уточнять, показывать результат
- Методы: `process_message()`, `_determine_action()`, `_execute_action()`

### 4. Knowledge структура (знания)

#### `app/knowledge/normalizer/` - Нормализаторы
- `material_map.py` - нормализация материалов (14хгса → сталь)
- `tool_map.py` - нормализация инструментов (CNMG → токарный проходной)
- `machine_map.py` - нормализация станков

#### `app/knowledge/knowledge_base/` - База знаний (JSON)
- `materials.json` - материалы с свойствами
- `tools.json` - инструменты с параметрами
- `machines.json` - станки с характеристиками

### 5. Main модуль

#### `app/main.py` - Точка входа
- Обновлен для использования новой архитектуры
- Инициализация всех компонентов в правильном порядке
- Поддержка lifespan для корректного завершения

## 🔄 Поток работы

1. **Получение сообщения** → `telegram_bot.py`
2. **Главный обработчик** → `handler.py`
   - Достаёт Context
   - Передаёт текст в parser
   - Обновляет state_machine
   - Запускает assumptions
3. **Парсинг текста** → `parser.py`
   - Извлекает материал, операцию, диаметры, числа
4. **Контекст** → `context.py`
   - Хранит что известно точно, что предположено, что по умолчанию
5. **Машина состояний** → `state_machine.py`
   - Отвечает: достаточно ли данных, можно ли считать
6. **Двигатель предположений** → `assumptions.py`
   - Делает разумные предположения с метаданными
7. **База знаний** → `knowledge_service.py`
   - Ищет материал/инструмент, нормализует названия
8. **Калькулятор** → `calculator.py`
   - Считает Vc, n, ap, f, мощность
9. **Стратегия проходов** → `pass_strategy.py`
   - Разбивка на проходы
10. **Валидатор** → `validator.py`
    - Защита от бреда, опасных режимов
11. **Рекомендации** → `recommendation.py`
    - Объясняет человеческим языком
12. **Сбор данных** → `data_collector.py`
    - Сохраняет решения операторов

## 📝 Что нужно доработать

1. **Интеграция с существующим telegram_bot.py**
   - Передать handler в бот
   - Использовать Context вместо локальных переменных
   - Использовать parser для парсинга сообщений

2. **Калькулятор**
   - Интеграция с Context
   - Использование данных из KnowledgeService

3. **PassStrategy**
   - Интеграция с Context
   - Использование данных из KnowledgeService

4. **Интернет-парсер** (опционально)
   - `app/knowledge/internet_parser/sources.py`
   - `app/knowledge/internet_parser/scraper.py`
   - `app/knowledge/internet_parser/text_cleaner.py`
   - `app/knowledge/internet_parser/extractor.py`

5. **Data pipeline** (опционально)
   - `app/storage/data_pipeline.py` - подготовка под LLM

## 🚀 Как использовать

### Запуск проекта:
```bash
py app/main.py
```

### Использование Handler в коде:
```python
from app.bot.handler import MessageHandler
from app.services.knowledge_service import KnowledgeService

# Инициализация
knowledge_service = KnowledgeService()
await knowledge_service.initialize()

handler = MessageHandler(knowledge_service=knowledge_service)

# Обработка сообщения
result = await handler.process_message(
    user_text="сталь, токарный ЧПУ, с Ø100 до Ø90",
    user_id="user123"
)

# Результат содержит:
# - action: 'calculate' или 'clarify'
# - recommendation: рекомендации калькулятора
# - context: полный контекст
# - assumptions_made: список предположений
# - defaults_used: список значений по умолчанию
```

## 📚 Структура проекта

```
app/
├── main.py                    # Точка входа
├── bot/
│   ├── handler.py            # Главный роутер (НОВЫЙ)
│   ├── telegram_bot.py       # Telegram API
│   └── dialogs.py           # Диалоги
├── core/
│   ├── context.py            # Единый объект состояния (НОВЫЙ)
│   ├── parser.py             # Парсер текста (НОВЫЙ)
│   ├── assumptions.py        # Двигатель предположений (НОВЫЙ)
│   ├── state_machine.py       # FSM
│   ├── calculator.py         # Физика резания
│   ├── pass_strategy.py      # Стратегия проходов
│   └── validator.py          # Валидация
├── services/
│   ├── knowledge_service.py  # Сервис знаний (НОВЫЙ)
│   ├── recommendation.py     # Рекомендации
│   ├── comparison.py         # Сравнение
│   └── data_collector.py     # Сбор данных
├── knowledge/                 # НОВАЯ СТРУКТУРА
│   ├── normalizer/
│   │   ├── material_map.py   # Нормализация материалов
│   │   ├── tool_map.py       # Нормализация инструментов
│   │   └── machine_map.py     # Нормализация станков
│   └── knowledge_base/
│       ├── materials.json    # База материалов
│       ├── tools.json         # База инструментов
│       └── machines.json      # База станков
└── storage/
    ├── db.py                  # База данных
    └── models.py              # Модели
```

## ✅ Готово к использованию

Все основные модули созданы и готовы к интеграции. Ошибки импортов исправлены. Проект можно запускать и тестировать.
