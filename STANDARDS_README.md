# Production-Ready Система Управления Стандартами

## Описание

Юридически безопасная система хранения и обновления инженерных стандартов для CNC backend проекта.

**Принципы:**
- ✅ Пользовательская загрузка PDF
- ✅ Версионирование через SHA256
- ✅ Структурированное хранение данных
- ✅ Кэширование для производительности
- ❌ НЕ скачивает автоматически платные документы
- ❌ НЕ скрейпит сайты
- ❌ НЕ обходит paywall

## Архитектура

```
Internet → Downloader → Parser → Versioning → Database → Cache → Bot
```

**Бот работает только с БД/кэшем, не напрямую с интернетом.**

## Структура проекта

```
app/
    standards/
        models.py          # SQLAlchemy модели
        repository.py      # Репозиторий для работы с БД
        manager.py         # Главный менеджер
        parser.py          # PDF парсер
        cache.py           # Redis кэш
        routes.py          # FastAPI endpoints
        schemas.py         # Pydantic схемы
    core/
        database.py        # Настройка БД
        config.py          # Конфигурация
    main.py               # FastAPI приложение

cli/
    manage_standards.py    # CLI команды

alembic/                  # Миграции БД
docker-compose.yml        # PostgreSQL + Redis
```

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements_standards.txt
```

### 2. Настройка окружения

```bash
cp .env.example .env
# Отредактируйте .env файл
```

### 3. Запуск инфраструктуры

```bash
docker-compose up -d
```

### 4. Применение миграций

```bash
alembic upgrade head
```

### 5. Запуск API

```bash
python -m app.main
```

## Использование CLI

### Проверка обновлений

```bash
python cli/manage_standards.py check
python cli/manage_standards.py check --force
```

Вывод:
```
=== STANDARD CHECK ===

✅ ISO: 12 checked
⚠️ GOST: 7 checked
   2 updates available
✅ OST: 3 checked

Total: 22 checked, 2 updated
```

### Проверка целостности

```bash
python cli/manage_standards.py integrity
```

Вывод:
```
=== INTEGRITY CHECK ===

Total standards: 45
Missing files: 0
Corrupted files: 0

Integrity: ✅ PASSED
```

### Импорт стандарта

```bash
python cli/manage_standards.py import path/to/standard.pdf \
    --family OST \
    --code 33056-80 \
    --full-code "ОСТ 1 33056-80" \
    --title "Гайка шестигранная высокая самоконтрящаяся" \
    --country "РФ" \
    --revision "1980"
```

### Список стандартов

```bash
python cli/manage_standards.py list
python cli/manage_standards.py list --family OST --limit 50
```

## API Endpoints

### GET /standards/
Получить список стандартов

**Параметры:**
- `family` (optional) - фильтр по семейству
- `skip` (default: 0) - пропустить записей
- `limit` (default: 100) - максимум записей

### GET /standards/{family}/{code}
Получить стандарт по семейству и коду

**Pipeline:** Cache → Database

### POST /standards/upload
Загрузить стандарт из PDF

**Параметры:**
- `file` - PDF файл
- `family` - Семейство стандарта
- `code` - Код стандарта
- `full_code` - Полный код
- `title` (optional) - Название
- `country` (optional) - Страна
- `revision` (optional) - Ревизия

**Flow:**
1. Принять PDF
2. Вычислить SHA256
3. Проверить есть ли стандарт с таким hash
4. Если нет:
   - сохранить файл
   - распарсить
   - извлечь таблицы
   - сохранить JSON в StandardData
   - создать StandardVersion

### POST /standards/{standard_id}/mark-review
Пометить стандарт для проверки ("это не то")

### POST /standards/check-updates
Проверить обновления стандартов

**Параметры:**
- `force` (optional) - принудительная проверка всех

### GET /standards/integrity/check
Проверить целостность базы стандартов

## База данных

### Таблицы

**standards**
- Основная таблица с метаданными стандартов
- Индексы по `family`, `code`, `version_hash`

**standard_versions**
- История версий стандартов
- Связь с `standards` через `standard_id`

**standard_data**
- Распарсенные данные из PDF (JSONB)
- Таблицы, параметры, размеры

### Миграции

```bash
# Создать новую миграцию
alembic revision --autogenerate -m "description"

# Применить миграции
alembic upgrade head

# Откатить миграцию
alembic downgrade -1
```

## Кэширование

### Redis (опционально)

Ключ: `standard:{family}:{code}`
TTL: 24 часа (настраивается)

Если Redis недоступен → fallback на in-memory кэш

### Pipeline работы бота

1. Проверить Redis
2. Если нет → проверить БД
3. Если нет → предложить скачать
4. Если есть → вернуть структурированные данные

## Версионирование

Каждый стандарт версионируется через SHA256 хеш файла:

1. При загрузке вычисляется SHA256
2. Сохраняется в `version_hash`
3. При следующей проверке сравнивается с новым хешем
4. Если изменился → создается новая запись в `standard_versions`

## Проверка обновлений

### Автоматическая проверка

- Проверка раз в 6 месяцев (180 дней)
- Проверяются только стандарты с `last_checked < 180 дней назад`
- В public режиме только локальная проверка метаданных
- В enterprise режиме можно использовать API

### Механизм "это не то"

Когда пользователь говорит "это не то":
1. Стандарт помечается `needs_review = TRUE`
2. Статус меняется на `suspicious`
3. Принудительная перепроверка
4. Сравнение версий
5. Показ diff отчета

## Парсинг PDF

### Извлечение данных

Парсер извлекает:
- Текст со всех страниц
- Таблицы (если доступен pdfplumber)
- Структурированные данные:
  - Резьбы (M20, M42x1.5)
  - Допуски (H7, g6)
  - Размеры (диаметры, длины)

### Сохранение

Данные сохраняются в `standard_data`:
- `section_name` - название раздела
- `data` (JSONB) - структурированные данные
- `data_type` - тип данных (table, parameters)
- `page_number` - номер страницы

## Режимы работы

### Public режим (по умолчанию)
- Только пользовательская загрузка PDF
- Нет автоматического скачивания
- Проверка обновлений только локально

### Enterprise режим
- Можно подключить официальный API метаданных
- Автоматическая проверка обновлений через API
- Расширенные возможности

Настройка в `.env`:
```
STANDARDS_MODE=enterprise
ENTERPRISE_API_URL=https://api.example.com
ENTERPRISE_API_KEY=your_api_key
```

## Безопасность

Система НЕ должна:
- ❌ Автоматически скрейпить сайты
- ❌ Обходить paywall
- ❌ Массово скачивать стандарты

Только:
- ✅ Пользовательская загрузка
- ✅ Работа с метаданными
- ✅ Версионирование через SHA256

## Производительность

### Время доступа
- Internet → 1-5 сек
- Database → 5-20 мс
- Cache (Redis) → 1-5 мс

### Результат
Бот отвечает как промышленная система благодаря работе из БД/кэша.

## Тестирование

```bash
pytest tests/test_standards/
```

## Примеры использования

### Загрузка стандарта через API

```python
import requests

files = {'file': open('standard.pdf', 'rb')}
data = {
    'family': 'OST',
    'code': '33056-80',
    'full_code': 'ОСТ 1 33056-80',
    'title': 'Гайка шестигранная высокая самоконтрящаяся'
}

response = requests.post('http://localhost:8000/standards/upload', files=files, data=data)
print(response.json())
```

### Получение стандарта

```python
response = requests.get('http://localhost:8000/standards/OST/33056-80')
standard = response.json()
print(standard['data'])  # Распарсенные данные
```

## Требования

- Python 3.11+
- PostgreSQL 15+
- Redis 7+ (опционально)
- FastAPI
- SQLAlchemy 2.0+
- Alembic
- pdfplumber или PyPDF2

## Лицензия

Система разработана для внутреннего использования.
Соблюдайте авторские права на стандарты.
