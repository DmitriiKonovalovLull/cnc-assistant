# Подсистема стандартов (ГОСТ, ОСТ, ISO)

Отдельная доменная область: без смешивания с process_planner.

## Структура

- **ingestion/** — парсинг PDF/DOC/таблиц → сырые данные
  - `pdf_parser.py` — извлечение текста и таблиц из PDF
  - `table_extractor.py` — выделение таблиц из текста
  - `text_cleaner.py` — нормализация текста и чисел
  - `fetch_gost_data.py` — загрузка актуальных данных ГОСТ/ISO из открытых источников
  - `fetch_world_standards.py` — параллельная загрузка стандартов всех стран (GOST, ISO, DIN, GB, JIS, ANSI, BS)
  - `multi_format_parser.py` — многоформатный парсер (PDF, Excel, CSV, JSON, XML, HTML) с поддержкой специфики стран
  - `country_parsers/` — специализированные парсеры для разных стран
    - `china_parser.py` — GB, GB/T, GB/Z стандарты (иероглифы, мм)
    - `japan_parser.py` — JIS стандарты (японские термины, JIS B 0401)
    - `usa_parser.py` — ANSI, ASME, ASTM, SAE (дюймы, UNF/UNC)
    - `germany_parser.py` — DIN, DIN EN, DIN ISO (немецкие термины)
    - `russia_parser.py` — ГОСТ, ГОСТ Р, ОСТ, ТУ (советские обозначения)
  - `data/` — сохранённые загруженные данные (JSON, HTML)
- **normalization/** — приведение к единой модели
  - `thread_normalizer.py` — нормализация метрических резьб
  - `tolerance_normalizer.py` — нормализация допусков (IT, H7, g6)
  - `fit_normalizer.py` — нормализация посадок
  - `surface_normalizer.py` — нормализация шероховатости
  - `universal_normalizer.py` — универсальный нормализатор для всех систем (ThreadData, ToleranceData)
- **models/** — Расширенные модели для всех мировых систем стандартов
  - `models.py` — StandardSource (16 систем), StandardCategory (8 категорий), ThreadData, RegionalSpecific
  - `standard_entity.py` — StandardEntity с поддержкой региональной специфики и аналогов
  - `manufacturing_requirement.py` — ManufacturingRequirement
  - `process_constraint.py` — ProcessConstraint
- **registry/** — единая точка доступа к стандартам
  - `standard_registry.py` — базовый StandardRegistry (get_thread, get_tolerance, get_fit, get_surface)
  - `world_registry.py` — расширенный WorldStandardRegistry (поиск по всем системам, аналоги, сравнение)
- **business_logic/** — RequirementEngine (Entity → Requirement), ConstraintEngine (Requirement → Constraints)
- **equivalence/** — аналоги всех мировых систем стандартов
  - `equivalence_engine.py` — EquivalenceEngine с таблицами соответствия и формулами пересчета
  - `equivalence_data.json` — база знаний эквивалентности (ГОСТ↔ISO, GB↔ISO, JIS↔ISO, etc.)
  - `equivalence_db.json` — таблицы соответствий стандартов по категориям
  - `build_equivalence_db.py` — построитель оптимизированной базы данных эквивалентности
- **api/** — вход для бота: process_designation(text) → сообщение и ограничения

## Порядок реализации

1. Резьба (метрическая) — реализовано
2. IT-допуски и поля (H7, g6) — реализовано
3. Посадки — заглушки
4. Шероховатость (Ra, Rz) — реализовано
5. Аналоги ISO — заглушки (equivalence_engine)

## Связь с process_planner (ЭТАП 7)

При появлении process_planner:

```python
from standards.api.designation_handler import process_designation, get_constraints_for_planner

res = process_designation(user_text)
if res:
    for constraint in res["constraints"]:
        apply_to_operation_plan(constraint)
```

## Интеграция в Telegram

В handler при сообщении пользователя вызывается `process_designation(user_text)`. Если обозначение распознано (Ø50 H7, M42x1.5, Ra 1.6), бот отвечает текстом с требованием и ограничениями технологии.

## Загрузка актуальных данных ГОСТ/ISO

Модуль `ingestion/fetch_gost_data.py` позволяет скачивать актуальные данные из открытых источников:

```python
from standards.ingestion.fetch_gost_data import update_all_data, load_gost_threads, load_iso_tolerances

# Обновить все данные (GOST резьбы + ISO допуски)
results = update_all_data()

# Загрузить сохранённые данные (или fallback если файла нет)
threads = load_gost_threads()
tolerances = load_iso_tolerances()
```

**Особенности:**
- Автоматический fallback на встроенные базовые данные при отсутствии интернета
- Использование User-Agent заголовков для избежания блокировок
- Сохранение в `standards/ingestion/data/*.json`
- Поддержка множественных источников (можно добавить зеркала)

## Модуль скачивания стандартов

Модуль `downloader/standard_downloader.py` обеспечивает скачивание стандартов из официальных источников:

**Возможности:**
- Скачивание PDF стандартов
- Проверка целостности по SHA256
- Версионирование и метаданные
- Retry при ошибках сети
- Кэширование скачанных файлов

**Использование:**
```python
from standards.downloader.standard_downloader import StandardDownloader

downloader = StandardDownloader()
file_path = downloader.download(
    url="https://example.com/standard.pdf",
    name="ISO-965-1",
    source="ISO"
)
```

**CLI команда:**
```bash
python standards/cli/update_standards.py update-standards
# или через main.py:
python main.py  # выбрать пункт 4
```

## Загрузка стандартов всех стран

Модуль `ingestion/fetch_world_standards.py` обеспечивает параллельную загрузку стандартов из всех основных мировых систем:

**Поддерживаемые системы:**
- **GOST** (РФ): docs.cntd.ru, protect.gost.ru → `data/gost/`
- **ISO** (международный): iso.org, standards.iso.org → `data/iso/`
- **DIN** (Германия): beuth.de, din.de → `data/din/`
- **GB** (Китай): gbstandards.org, chinesestandard.net → `data/gb/`
- **JIS** (Япония): jisc.go.jp → `data/jis/`
- **ANSI** (США): ansi.org → `data/ansi/`
- **BS** (Британия): bsigroup.com → `data/bs/`

**Использование:**

```python
from standards.ingestion.fetch_world_standards import fetch_all_standards_sync

# Параллельная загрузка всех стандартов
summary = fetch_all_standards_sync()

print(f"Successful: {summary['summary']['successful']}")
print(f"Failed: {summary['summary']['failed']}")

# Результаты по каждому источнику
for source, result in summary["results"].items():
    if result.get("success"):
        print(f"{source}: {len(result.get('data_files', []))} files downloaded")
```

**Особенности:**
- Параллельная загрузка через `asyncio.gather()` для максимальной скорости
- Автоматическое сохранение метаданных в `data/{source}/metadata.json`
- Общий отчёт сохраняется в `data/fetch_summary.json`
- Обработка исключений для каждого источника независимо
- Fallback на синхронные запросы если aiohttp недоступен

## Многоформатный парсер стандартов

Модуль `ingestion/multi_format_parser.py` поддерживает парсинг стандартов в различных форматах с учётом специфики разных стран:

**Поддерживаемые форматы:**
- PDF, Excel (.xlsx, .xls), CSV, JSON, XML, HTML

**Специализированные парсеры:**
- **ChineseStandardsParser** — GB стандарты (Китай)
  - Кодировки: GB2312, GB18030
  - Перевод китайских технических терминов
  - Поиск аналогов в китайских текстах
  
- **JapaneseStandardsParser** — JIS стандарты (Япония)
  - Кодировки: Shift-JIS, EUC-JP
  - Перевод японских технических терминов
  
- **USStandardsParser** — ANSI, ASME, ASTM, SAE (США)
  - Дюймовая система единиц
  - Конвертация дюймов в метрические единицы
  
- **EuropeanStandardsParser** — DIN, BS, NF, UNI, EN (Европа)
  - Распознавание гармонизированных EN стандартов
  - Связь EN ↔ ISO

**Извлечение информации об аналогах:**
Все парсеры поддерживают метод `extract_equivalence_info()`, который ищет в тексте стандарта информацию об аналогах:
- "equivalent to ISO 1234"
- "mod ISO 1234" / "modified ISO 1234"
- "based on DIN 123"
- "harmonized with EN 123"
- Китайские/японские эквиваленты

**Использование:**

```python
from standards.ingestion.multi_format_parser import get_parser_for_source

# Автоматический выбор парсера по источнику
parser = get_parser_for_source("GB")  # ChineseStandardsParser
result = parser.parse("path/to/chinese_standard.csv")

# Извлечение информации об аналогах
equivalences = parser.extract_equivalence_info(result["text"])
for eq in equivalences:
    print(f"{eq['source']} {eq['number']} ({eq['relation']})")

## Специализированные парсеры по странам

Модуль `ingestion/country_parsers/` содержит парсеры, наследуемые от базового `StandardsParser`:

**1. ChinaStandardsParser (china_parser.py):**
- Парсинг GB, GB/T, GB/Z стандартов
- Работа с китайскими иероглифами (GB2312, GB18030)
- Конвертация единиц измерения (Китай использует мм)
- Метод `parse_gb_designation()` для распознавания GB обозначений

**2. JapanStandardsParser (japan_parser.py):**
- Парсинг JIS стандартов
- Японские технические термины (Shift-JIS, EUC-JP)
- Особые обозначения допусков (JIS B 0401)
- Метод `parse_jis_designation()` и `parse_jis_tolerance()`

**3. USAStandardsParser (usa_parser.py):**
- ANSI, ASME, ASTM, SAE стандарты
- Дюймовая система единиц
- UNF/UNC резьбы, NPT, BSP
- ANSI допуски (ANSI B4.1)
- Методы `parse_ansi_designation()`, `parse_inch_thread()`, `parse_ansi_tolerance()`

**4. GermanyStandardsParser (germany_parser.py):**
- DIN, DIN EN, DIN ISO стандарты
- Немецкие технические термины
- Распознавание гармонизированных стандартов
- Метод `parse_din_designation()`

**5. RussiaStandardsParser (russia_parser.py):**
- ГОСТ, ГОСТ Р, ОСТ, ТУ стандарты
- Советские и российские обозначения
- Особенности форматов (старый формат: "1 ГОСТ 24705")
- Метод `parse_gost_designation()`

**Использование:**

```python
from standards.ingestion.country_parsers import (
    ChinaStandardsParser,
    JapanStandardsParser,
    USAStandardsParser,
    GermanyStandardsParser,
    RussiaStandardsParser
)

# Китайский парсер
china_parser = ChinaStandardsParser()
gb_info = china_parser.parse_gb_designation("GB/T 192-2003")

# Японский парсер
japan_parser = JapanStandardsParser()
jis_info = japan_parser.parse_jis_designation("JIS B 0205")

# Американский парсер
usa_parser = USAStandardsParser()
thread_info = usa_parser.parse_inch_thread("1/4-20 UNC")

# Немецкий парсер
germany_parser = GermanyStandardsParser()
din_info = germany_parser.parse_din_designation("DIN EN ISO 965-1")

# Российский парсер
russia_parser = RussiaStandardsParser()
gost_info = russia_parser.parse_gost_designation("ГОСТ 24705")
```

## Мировой реестр стандартов

Модуль `registry/world_registry.py` предоставляет расширенный реестр с поддержкой всех мировых систем:

**Основные возможности:**

1. **Поиск по обозначению** — в конкретной системе или во всех:
```python
from standards.registry.world_registry import WorldStandardRegistry

registry = WorldStandardRegistry()

# Поиск в конкретной системе
results = registry.search_by_designation("M20", system="GB")

# Поиск во всех системах
all_results = registry.search_by_designation("M20")
```

2. **Поиск аналогов** — найти аналоги стандарта в других системах:
```python
# ГОСТ 24705 → ISO 965-1, DIN 13, GB/T 192
equivalents = registry.find_equivalents("24705", from_system="GOST")
for eq in equivalents:
    print(f"{eq['system']} {eq['designation']} (схожесть: {eq['score']*100:.1f}%)")
```

3. **Сравнение стандартов** — коэффициент схожести (0-100%):
```python
comparison = registry.compare_standards(
    "M20", "GOST",
    "M20", "ISO"
)
print(f"Схожесть: {comparison['similarity_percent']}%")
print(f"Совпадают: {comparison['matches']}")
print(f"Различаются: {comparison['differences']}")
```

4. **Предпочтительные системы** — по региону или стране:
```python
# По региону
systems = registry.get_preferred_system("CIS")  # ["GOST", "OST", "ISO"]

# По стране
systems = registry.get_preferred_system_by_country("Russia")  # ["GOST", "OST", "ISO"]
systems = registry.get_preferred_system_by_country("China")   # ["GB", "ISO"]
systems = registry.get_preferred_system_by_country("Germany") # ["DIN", "ISO", "EN"]
```

5. **Кэширование** — с разделением по системам для быстрого доступа:
```python
stats = registry.get_statistics()
print(f"Всего сущностей: {stats['total_entities']}")
print(f"По системам: {stats['by_system']}")
print(f"По категориям: {stats['by_category']}")
```

**Особенности:**
- Кэш с разделением по системам: `{"GOST": {}, "ISO": {}, "GB": {}, ...}`
- Автоматический поиск аналогов через EquivalenceEngine
- Поддержка всех мировых систем стандартов
- Интеграция с regional_specific для хранения информации об аналогах

## Движок эквивалентности стандартов

Модуль `equivalence/equivalence_engine.py` предоставляет расширенный функционал для поиска аналогов и сравнения стандартов:

**Таблицы соответствия:**
- ГОСТ ↔ ISO (многие ГОСТ гармонизированы с ISO)
- ГОСТ ↔ DIN (исторические связи)
- GB ↔ ISO (Китай часто копирует ISO с модификациями)
- JIS ↔ ISO (Япония)
- ANSI ↔ ISO (США)

**Основные методы:**

1. **calculate_similarity(standard1, standard2)** — расчет схожести (0-100%):
```python
from standards.equivalence.equivalence_engine import EquivalenceEngine

engine = EquivalenceEngine()
similarity = engine.calculate_similarity(entity1, entity2)
print(f"Схожесть: {similarity * 100:.1f}%")
```

2. **find_din_analog(gost_designation)** — поиск аналога в DIN:
```python
analog = engine.find_din_analog("M20")
# Возвращает: {"din": "13-1", "confidence": 0.85, "category": "thread"}
```

3. **find_gb_analog(iso_designation)** — поиск китайского аналога:
```python
analog = engine.find_gb_analog("ISO 965-1")
# Возвращает: {"gb": "192", "confidence": 0.9, "category": "thread", "note": "GB/T 192-2003 mod ISO 965-1"}
```

4. **get_conversion_formula(from_system, to_system, parameter)** — формулы пересчета:
```python
formula = engine.get_conversion_formula("ANSI", "ISO", "length")
# Возвращает: {
#   "formula": "value_mm = value_inch * 25.4",
#   "reverse": "value_inch = value_mm / 25.4",
#   "description": "Дюймы в миллиметры",
#   "constant": 25.4
# }
```

**База знаний:**
- Загружается из `equivalence_data.json` и `equivalence_db.json`
- Содержит таблицы соответствия для всех основных систем
- Быстрые поиски по обозначениям резьб и допусков
- Автоматическое создание данных по умолчанию если файл не найден

**Построение оптимизированной базы данных:**

Модуль `build_equivalence_db.py` собирает данные из всех источников и строит оптимизированный граф связей:

```python
from standards.equivalence.build_equivalence_db import EquivalenceDBBuilder

builder = EquivalenceDBBuilder()
optimized_db = builder.build()  # Собирает данные, строит граф, сохраняет в JSON

# Поиск всех аналогов стандарта
equivalents = builder.find_all_equivalents("GOST", "24705")
# Возвращает: [{"system": "ISO", "number": "965-1", "confidence": 0.8}, ...]

# Поиск пути между стандартами
path = builder.find_path("GOST", "24705", "ISO", "965-1")
# Возвращает: ["GOST:24705", "ISO:965-1"]
```

**Структура оптимизированной БД:**
- `by_system` — индексация по системам стандартов (GOST, ISO, DIN, etc.)
- `by_category` — индексация по категориям (thread, tolerance, fit, surface)
- `quick_lookup` — быстрый поиск по обозначениям (M20, H7, etc.)
- `graph` — граф связей между стандартами для поиска путей

**Расчет схожести по категориям:**
- **Резьбы**: диаметр (40%), шаг (40%), класс допуска (20%)
- **Допуски**: класс допуска (60%), поле допуска (40%)
- **Посадки**: тип посадки (50%), поля отверстия/вала (25%+25%)
- **Шероховатость**: сравнение Ra в пределах рядов значений

## Тестирование

Все модули покрыты тестами в `tests/standards/`:

**Запуск тестов:**
```bash
# Все тесты стандартов
pytest tests/standards -v

# Конкретный модуль
pytest tests/standards/test_thread_geometry.py -v

# С покрытием кода
pytest tests/standards --cov=standards --cov-report=html
```

**Покрытие:**
- ✅ Геометрия резьбы (все формулы ISO 965-1)
- ✅ IT допуски (все формулы ISO 286)
- ✅ Посадки (зазоры/натяги)
- ✅ Шероховатость (связь с подачей)
- ✅ Эквивалентность стандартов
- ✅ Генерация ограничений
- ✅ Интеграция с planner
- ✅ Модуль скачивания

## Математические вычисления

Модуль `calculations/` содержит математически корректные вычисления по формулам ISO/GOST:

### Геометрия резьбы (`thread_geometry.py`)
- Вычисление высоты профиля: H = (√3 / 2) * P
- Глубина резьбы: h = 0.61343 * P
- Средний диаметр: d2 = d - 0.64952 * P
- Малый диаметр: d3 = d - 1.22687 * P

### IT допуски (`tolerance_calculator.py`)
- Базовая единица допуска: i = 0.45 * ∛D + 0.001 * D (мкм)
- IT6 = 10i, IT7 = 16i, IT8 = 25i
- Вычисление полей допусков (H7, g6, etc.)

### Посадки (`fit_calculator.py`)
- Вычисление зазоров/натягов
- Определение типа посадки (clearance/interference/transition)

### Шероховатость (`surface_roughness.py`)
- Связь подачи и Ra: Ra ≈ (f²) / (32 * r)
- Вычисление максимальной подачи для достижения Ra

## Универсальный нормализатор

Модуль `normalization/universal_normalizer.py` предоставляет единую точку нормализации для всех мировых систем стандартов:

**Основные возможности:**

1. **normalize_thread(designation, system)** — нормализация резьб всех систем:
```python
from standards.normalization.universal_normalizer import UniversalNormalizer

normalizer = UniversalNormalizer()

# Метрические резьбы (GOST, ISO, DIN, GB, JIS)
thread1 = normalizer.normalize_thread("M20", "ISO")
print(f"Диаметр: {thread1.diameter} мм, шаг: {thread1.pitch} мм")

# Дюймовые резьбы (ANSI, ASME) - автоматическая конвертация в мм
thread2 = normalizer.normalize_thread("1/4-20 UNC", "ANSI")
print(f"Диаметр: {thread2.diameter} мм, шаг: {thread2.pitch} мм")
```

2. **normalize_tolerance(tolerance, system)** — нормализация допусков всех систем:
```python
# Метрические допуски (ISO, GOST, GB, JIS)
tol1 = normalizer.normalize_tolerance("H7", "ISO")
print(f"Поле допуска: {tol1.tolerance_field}, класс: IT{tol1.tolerance_grade}")

# Американские допуски (ANSI) - конвертация в мм
tol2 = normalizer.normalize_tolerance("0.500 +0.001/-0.000", "ANSI")
print(f"Номинальный размер: {tol2.nominal_mm} мм")
print(f"Допуск: {tol2.tolerance_value_mm} мм")
```

3. **convert_to_metric(value, from_unit)** — точная конвертация единиц:
```python
# Точное преобразование: 1 дюйм = 25.4 мм
mm = normalizer.convert_to_metric(1.0, "inch")  # 25.4
inch = normalizer.convert_to_metric(25.4, "mm")  # 25.4
cm = normalizer.convert_to_metric(1.0, "cm")     # 10.0
```

4. **get_standard_family(designation)** — определение семейства стандарта:
```python
family = normalizer.get_standard_family("GB/T 192")
# Возвращает: {
#   "family": "thread",
#   "parent": "ISO 965-1",
#   "confidence": 0.9,
#   "system": "GB"
# }
```

5. **normalize_all(designation, system, category)** — универсальная нормализация:
```python
result = normalizer.normalize_all("M20", "ISO", category="thread")
# Автоматически определяет категорию и нормализует
```

**Поддерживаемые системы:**
- Метрические: GOST, ISO, DIN, GB, JIS
- Дюймовые: ANSI, ASME, ASTM, SAE
- Автоматическая конвертация дюймов → мм
- Единый формат ThreadData и ToleranceData независимо от исходной системы

## Поддержка мировых систем стандартов

Модуль `models/models.py` поддерживает все основные мировые системы стандартов:

**StandardSource (16 систем):**
- ГОСТ, ОСТ (РФ/ЕАЭС/СССР)
- ISO (международный)
- DIN, BS, NF, UNI, SIS, PN, CSN (Европа)
- GB, JIS, KS, IS (Азия)
- ANSI, ASME (США)

**StandardCategory (8 категорий):**
- THREAD (резьбы: метрическая, дюймовая, трубная, трапецеидальная)
- TOLERANCE (допуски IT, ANSI, JIS)
- FIT (посадки)
- SURFACE (шероховатость)
- GROOVE (канавки)
- MATERIAL (материалы)
- HEAT_TREATMENT (термообработка)
- COATING (покрытия)

**ThreadData** поддерживает:
- Метрические резьбы (pitch в мм)
- Дюймовые резьбы (TPI - Threads Per Inch)
- Трубные резьбы (NPT, BSP)
- Трапецеидальные, упорные резьбы
- Автоматическая конвертация единиц (mm ↔ inch)

**Пример использования:**

```python
from standards.models import StandardEntity, StandardSource, StandardCategory, ThreadData, RegionalSpecific

# Создание сущности с региональной спецификой
entity = StandardEntity(
    id="thread_gost_m42",
    source=StandardSource.GOST.value,
    category=StandardCategory.THREAD.value,
    normalized_data={"diameter": 42, "pitch": 1.5},
    regional_specific=RegionalSpecific(
        region="CIS",
        equivalent_to=[
            {"source": "ISO", "designation": "M42x1.5", "confidence": 0.95}
        ]
    )
)

# Работа с ThreadData
metric_thread = ThreadData(
    thread_type="metric",
    diameter=42,
    diameter_unit="mm",
    pitch=1.5,
    tolerance_class="6g"
)

unified_thread = ThreadData(
    thread_type="unified",
    diameter=0.5,
    diameter_unit="inch",
    tpi=20,
    thread_series="UNC"
)

print(f"Metric pitch: {metric_thread.get_pitch_mm()} mm")
print(f"Unified pitch: {unified_thread.get_pitch_mm()} mm")
print(f"Unified diameter: {unified_thread.get_diameter_mm()} mm")
```
