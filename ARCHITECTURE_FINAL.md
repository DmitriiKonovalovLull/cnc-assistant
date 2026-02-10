# 🧠 CNC-ASSISTANT — ФИНАЛЬНАЯ АРХИТЕКТУРА

## 📁 Структура проекта

```
cnc-assistant/
├── app/
│   ├── main.py                    # Точка входа: запуск бота, инициализация сервисов
│   │
│   ├── bot/
│   │   ├── telegram_bot.py       # Telegram API, сообщения, без логики
│   │   ├── handler.py             # ОРКЕСТРАТОР: принимает сообщение → parser → context → assumptions → core
│   │   └── dialogs.py             # Сценарии диалогов (уточнения, подтверждения, "я предположил")
│   │
│   ├── core/
│   │   ├── context.py             # 🔥 СЕРДЦЕ СИСТЕМЫ: единый объект состояния
│   │   ├── state_machine.py        # FSM: EMPTY → PARTIAL → ASSUMED → READY → CALCULATED → FEEDBACK
│   │   ├── parser.py              # Парсер человеческого текста: "титан Ø200→50 вылет 100 30 бар"
│   │   ├── assumptions.py         # Двигатель предположений: если нет данных → ставит дефолты + снижает confidence
│   │   ├── calculator.py          # Физика: Vc, n, f, ap, мощность, жёсткость, тепловая нагрузка
│   │   ├── pass_strategy.py       # Стратегия проходов: черновые / получист / чистовой
│   │   └── validator.py           # Защита от бреда: титан + 300 м/мин = ❌
│   │
│   ├── domain/
│   │   ├── models.py               # Material, Machine, Tool, Operation
│   │   └── experience.py           # Вес опыта оператора (новичок / профи / цех)
│   │
│   ├── services/
│   │   ├── recommendation.py      # Перевод чисел в человеческий язык
│   │   ├── comparison.py           # Сравнение: бот vs оператор
│   │   ├── data_collector.py       # Сохранение: вход → расчёт → решение человека → факт
│   │   ├── knowledge_service.py   # Работа со знаниями (локальными + интернет)
│   │   ├── context_repository.py  # Хранилище контекста пользователей
│   │   ├── cache_service.py        # Кэширование для производительности
│   │   ├── database_pool.py       # Пул соединений с БД
│   │   ├── llm_adapter.py         # Адаптер для будущей LLM интеграции
│   │   ├── training_data_exporter.py  # Экспорт данных для обучения
│   │   ├── tool_saver.py          # Сохранение неизвестных инструментов
│   │   ├── machine_saver.py       # Сохранение неизвестных станков
│   │   ├── material_saver.py      # Сохранение неизвестных материалов
│   │   └── work_manager.py        # Управление сохраненными работами
│   │
│   ├── knowledge/
│   │   ├── internet_parser/
│   │   │   ├── sources.py         # Форумы, мануалы, PDF, ГОСТ, datasheets
│   │   │   ├── scraper.py         # Загрузка HTML/PDF
│   │   │   ├── text_cleaner.py    # Очистка мусора
│   │   │   └── extractor.py       # Извлечение фактов: "Ti-6Al-4V vc 25-40"
│   │   │
│   │   ├── normalizer/
│   │   │   ├── material_map.py    # титан / ti / ВТ6 → Titanium
│   │   │   ├── tool_map.py        # CNMG / 80° / R0.8
│   │   │   └── machine_map.py     # Gamma 1250 TC → power, rpm, rigidity
│   │   │
│   │   └── knowledge_base/
│   │       ├── materials.json
│   │       ├── tools.json
│   │       ├── machines.json
│   │       └── cutting_rules.json # Правила резания
│   │
│   └── storage/
│       ├── db.py                  # SQLite / PostgreSQL
│       ├── models.py              # SQLAlchemy модели
│       └── data_pipeline.py       # Подготовка датасета под LLM
│
├── data/
│   ├── rules/
│   │   └── cutting_modes.yaml     # Справочники (без логики)
│   └── limits/
│       └── physical_limits.yaml  # Физические лимиты
│
└── training/
    ├── datasets/                  # JSONL для обучения
    ├── prompts/                   # Будущие системные промпты
    └── finetune/                  # Твоя ЛИЧНАЯ LLM
```

## 🔁 Полная логика работы бота (шаг за шагом)

### 1️⃣ Пользователь пишет как человек
```
"титан, gamma 1250, Ø200→50, вылет 100, 30 бар"
```

### 2️⃣ parser.py
Извлекает:
- материал
- станок
- диаметры
- давление
- вылет

❌ **ничего не вычисляет**

### 3️⃣ context.py
Создаётся единый объект:
```json
{
  "material": "titanium",
  "machine": "Gamma 1250 TC",
  "diameters": [200, 50],
  "tool_overhang": 100,
  "confidence": 0.62,
  "assumed": ["tool_radius", "tool_material"]
}
```

### 4️⃣ assumptions.py
Если данных нет:
- ставит дефолт
- снижает confidence
- **ПОМЕЧАЕТ как предположение**

❗ **бот не задаёт лишних вопросов**

### 5️⃣ state_machine.py
Определяет состояние:
- данных достаточно → считаем
- мало данных → аккуратно уточняем

**Состояния:**
- `EMPTY` - нет данных
- `PARTIAL` - частичные данные
- `ASSUMED` - данные с предположениями
- `READY` - достаточно данных для расчета
- `CALCULATED` - расчет выполнен
- `FEEDBACK` - получена обратная связь

### 6️⃣ calculator.py
Считает:
- Vc
- обороты
- подачу
- ap
- мощность
- жёсткость (вылет!)

### 7️⃣ validator.py
Режет бред:
- перегрев
- перегруз
- опасные режимы

### 8️⃣ pass_strategy.py
Решает:
- сколько проходов
- какие (черн / полу / чист)

### 9️⃣ recommendation.py
Переводит в **ЧЕЛОВЕЧЕСКИЙ язык**:
```
«Для титана с таким вылетом скорость снижена на 40%»
```

### 🔟 Бот спрашивает ГЛАВНОЕ
```
А как ТЫ делаешь на практике?
```

### 1️⃣1️⃣ comparison.py
Сравнивает:
- бот
- оператор

### 1️⃣2️⃣ data_collector.py
Сохраняет **САМОЕ ЦЕННОЕ**:
```
контекст → расчёт → решение человека → результат
```

### 1️⃣3️⃣ data_pipeline.py
Готовит датасет для:
- дообучения
- RAG
- своей LLM

## 🎯 Главная идея (ЗАПОМНИ)

❌ **бот = не калькулятор**  
✅ **бот = ученик цеха**

Он:
1. сначала думает логикой
2. потом учится у людей
3. потом становится ИИ‑технологом

## 📊 Поток данных

```
Пользователь
    ↓
telegram_bot.py (прием сообщения)
    ↓
handler.py (оркестратор)
    ↓
parser.py (извлечение данных)
    ↓
context.py (сохранение состояния)
    ↓
assumptions.py (заполнение пробелов)
    ↓
state_machine.py (определение готовности)
    ↓
calculator.py (физика)
    ↓
validator.py (проверка)
    ↓
pass_strategy.py (стратегия проходов)
    ↓
recommendation.py (человеческий язык)
    ↓
comparison.py (сравнение с оператором)
    ↓
data_collector.py (сохранение опыта)
    ↓
data_pipeline.py (подготовка для LLM)
```

## 🔧 Ключевые компоненты

### Context (context.py)
- Единый объект состояния
- Хранит метаданные (источник, уверенность)
- Сериализуется в JSON для сохранения

### State Machine (state_machine.py)
- Определяет готовность к расчету
- Управляет переходами состояний
- Интегрирован в handler.py

### Data Collector (data_collector.py)
- Сохраняет каждое взаимодействие
- Формирует датасет для обучения
- Интегрирован с UserDecision моделью

### Comparison Service (comparison.py)
- Сравнивает рекомендации с решениями операторов
- Анализирует причины различий
- Генерирует объяснения

### Data Pipeline (data_pipeline.py)
- Экспортирует данные в форматы для обучения
- Поддерживает ChatML, Alpaca, Instruction форматы
- Генерирует системные промпты

## 🚀 Готовность к LLM

Система готова для:
- Fine-tuning локальных моделей
- Дообучения через API
- RAG (Retrieval Augmented Generation)
- Обучения собственной LLM

Все данные собираются в формате, готовом для обучения.
