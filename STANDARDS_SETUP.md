# Настройка системы стандартов

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements_standards.txt
```

### 2. Настройка окружения

Скопируйте `.env.example` в `.env` и настройте:

```bash
cp .env.example .env
```

Отредактируйте `.env`:
- `DATABASE_URL` - подключение к PostgreSQL
- `REDIS_URL` - подключение к Redis (опционально)
- `STANDARDS_MODE` - режим работы (public/enterprise)

### 3. Запуск инфраструктуры (Docker)

```bash
docker-compose up -d
```

Это запустит:
- PostgreSQL на порту 5432
- Redis на порту 6379

### 4. Применение миграций

```bash
alembic upgrade head
```

### 5. Запуск API

```bash
python -m app.main
```

API будет доступен на `http://localhost:8000`

## Использование CLI

### Проверка обновлений

```bash
python cli/manage_standards.py check
```

### Проверка целостности

```bash
python cli/manage_standards.py integrity
```

### Импорт стандарта

```bash
python cli/manage_standards.py import path/to/file.pdf \
    --family OST \
    --code 33056-80 \
    --full-code "ОСТ 1 33056-80" \
    --title "Гайка шестигранная высокая самоконтрящаяся"
```

### Список стандартов

```bash
python cli/manage_standards.py list
python cli/manage_standards.py list --family OST
```

## API Endpoints

### GET /standards/
Получить список стандартов

### GET /standards/{family}/{code}
Получить стандарт по семейству и коду

### POST /standards/upload
Загрузить стандарт из PDF

### POST /standards/{standard_id}/mark-review
Пометить стандарт для проверки

### POST /standards/check-updates
Проверить обновления стандартов

### GET /standards/integrity/check
Проверить целостность базы

## Режимы работы

### Public режим
- Только пользовательская загрузка PDF
- Нет автоматического скачивания
- Проверка обновлений только локально

### Enterprise режим
- Можно подключить официальный API метаданных
- Автоматическая проверка обновлений через API
- Расширенные возможности

## Архитектура

```
Internet → Downloader → Parser → Versioning → Database → Cache → Bot
```

Бот работает только с БД/кэшем, не напрямую с интернетом.

## Безопасность

Система НЕ должна:
- ❌ Автоматически скрейпить сайты
- ❌ Обходить paywall
- ❌ Массово скачивать стандарты

Только:
- ✅ Пользовательская загрузка
- ✅ Работа с метаданными
- ✅ Версионирование через SHA256
