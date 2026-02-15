# Умный парсер интернета

## Обзор

Парсер решает четыре основные проблемы:

1. **SPA (React/Vue)** — сайты Sandvik, Kennametal, Iscar, Seco, Walter отдают пустой HTML без JS. Используется **Playwright**: реальный браузер выполняет JavaScript, поиск через форму на сайте.
2. **Асинхронность** — вместо `requests` + `run_in_executor` используется **aiohttp**: настоящая async-параллельность, без блокировки пула потоков.
3. **Поиск по сайтам** — у каждого производителя свой endpoint/форма. Конфигурация в **site_config**: селекторы поля поиска, контейнера результатов, таймауты.
4. **Контекстное извлечение** — мощность и обороты берутся только из секций «Шпиндель»/«Spindle», а не из «Мощность освещения» или «Насос». Реализовано в **context_extractor**: разбивка по заголовкам (h2/h3/dt/th), затем regex только в нужном блоке.

## Компоненты

### 1. BrowserParser (`app/knowledge/internet_parser/browser_parser.py`)

- **Параллельный опрос** сайтов через `asyncio.gather`.
- Для каждого сайта: если `needs_js` — Playwright (ввод в поиск, ожидание контента), иначе aiohttp GET по шаблону URL.
- Извлечение данных через контекстный экстрактор (инструмент, станок, режимы).

### 2. Конфигурация сайтов (`app/knowledge/internet_parser/site_config.py`)

- **TOOL_SITES** / **MACHINE_SITES**: id, base_url, needs_js, селекторы поиска, таймауты.
- Sandvik, Kennametal, Iscar, Seco, Walter — все с `needs_js=True` и стратегией Playwright (поиск по форме).

### 3. Контекстный экстрактор (`app/knowledge/internet_parser/context_extractor.py`)

- Разбивка HTML на секции по заголовкам (h2, h3, dt, th, строки таблиц).
- Для поля **power** учитываются только секции, где в заголовке есть «шпиндель», «spindle», «main drive», «мощность», «power» и т.п.
- Для **max_rpm** — секции с «оборот», «rpm», «шпиндель».
- Для инструментов: радиус, материал, марка, vc — только из секций про режущую кромку/материал/режимы.

### 4. Бэкенды загрузки

- **fetch_aiohttp.py** — асинхронные GET через aiohttp (обязательная зависимость).
- **fetch_playwright.py** — опционально; открывает сайт, вводит запрос в поле поиска, ждёт контент, возвращает HTML.

### 5. InternetSearchService (`app/services/internet_search_service.py`)

- API не менялся: `search_and_save_tool`, `search_and_save_machine`, `search_operation_modes`, `search_standard_info`, `search_unknown_query`.
- Внутри по-прежнему вызывает `browser_parser.search_tool_info` и т.д.

## Зависимости

**Обязательные (уже в requirements.txt):**

```bash
pip install aiohttp
```

**Для SPA (Sandvik, Kennametal, Iscar, Seco, Walter):**

```bash
pip install -r requirements_internet.txt
playwright install
```

Без Playwright парсер будет пытаться только aiohttp; для перечисленных сайтов контент без JS пустой, поэтому поиск по ним без Playwright не даст результатов.

## Использование

Как раньше: бот при неизвестном станке/инструменте вызывает `InternetSearchService.search_and_save_machine` / `search_and_save_tool`. Внутри запускается новый умный парсер (aiohttp + при наличии Playwright — поиск по формам на SPA, контекстное извлечение).

## Настройка

- **Отключение поиска:** в `.env`: `INTERNET_SEARCH_ENABLED=false`.
- **Добавление сайта:** в `site_config.py` добавить запись в `TOOL_SITES` или `MACHINE_SITES` (base_url, needs_js, селекторы поиска при стратегии Playwright).

## Ограничения

- Сайты могут менять вёрстку — селекторы поиска иногда нужно обновлять.
- Playwright требует установки браузеров (`playwright install`) и больше ресурсов, чем простой HTTP.
- Некоторые сайты могут ограничивать или блокировать автоматический доступ.
