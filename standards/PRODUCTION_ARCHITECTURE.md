# Production Architecture системы стандартов

## Принципы

### Архитектура Pipeline
```
Internet → Downloader → Parser → Versioning → Database → Cache → Bot
```

**ВАЖНО**: Бот никогда не работает напрямую с интернетом. Только с БД.

## Структура базы данных

### Таблица `standards`
- `id` UUID PK
- `family` VARCHAR - ISO / DIN / GOST / OST / ANSI
- `code` VARCHAR - 33056-80
- `full_code` VARCHAR - ОСТ 1 33056-80
- `title` TEXT
- `country` VARCHAR
- `year` INT
- `version_hash` VARCHAR - SHA256 текущей версии
- `source_url` TEXT
- `last_checked` TIMESTAMP
- `last_updated` TIMESTAMP
- `status` VARCHAR - active / deprecated / updated / suspicious
- `needs_review` BOOLEAN - флаг "это не то"

### Таблица `standard_versions`
- `id` UUID
- `standard_id` UUID FK
- `version_hash` VARCHAR - SHA256 версии
- `published_date` DATE
- `file_path` TEXT
- `created_at` TIMESTAMP

### Таблица `standard_tables`
- `id` UUID
- `standard_id` UUID FK
- `section_name` VARCHAR
- `json_data` JSONB - распарсенные данные
- `data_type` VARCHAR - table / parameters / dimensions
- `page_number` INT

## Версионирование через HASH

Каждый скачанный файл:
1. Вычисляется SHA256 хеш
2. Сохраняется в `version_hash`
3. При следующей проверке сравнивается с новым хешем
4. Если изменился → создается новая запись в `standard_versions`

## Проверка обновлений

### Автоматическая проверка
- Проверка раз в 6 месяцев (180 дней)
- Проверяются только стандарты с `last_checked < 180 дней назад`
- Принудительная проверка: `--force` флаг

### Процесс проверки
1. Получить список стандартов для проверки
2. Для каждого стандарта:
   - Скачать новую версию (если доступна)
   - Вычислить SHA256
   - Сравнить с текущим `version_hash`
   - Если изменился → сохранить новую версию
3. Обновить `last_checked`

## Механизм "это не то"

Когда пользователь говорит "это не то":
1. Стандарт помечается `needs_review = TRUE`
2. Статус меняется на `suspicious`
3. Принудительная перепроверка
4. Сравнение версий
5. Показ diff отчета

## Парсинг PDF → JSON

### Зачем
- Сравнение версий (JSON легче сравнивать чем PDF)
- Структурированные данные для работы бота
- Быстрый поиск параметров

### Процесс
1. PDF → Парсер → JSON структура
2. Сохранение в `standard_tables.json_data`
3. При обновлении → сравнение JSON
4. Генерация diff отчета

## Кэширование

### Redis (опционально)
- Ключ: `standard:{family}:{code}`
- TTL: 24 часа
- Fallback: in-memory кэш

### Pipeline работы бота
1. Проверить Redis
2. Если нет → проверить БД
3. Если нет → предложить скачать
4. Если есть → вернуть структурированные данные

## Команды управления

### `python manage_standards.py update`
Проверка обновлений всех стандартов.

Вывод:
```
=== STANDARD UPDATE ===

ISO: 12 checked, 1 updated
DIN: 5 checked, 0 updated
GOST: 7 checked, 2 updated
OST: 3 checked, 0 updated

Integrity: OK
```

### `python manage_standards.py status`
Проверка статуса базы стандартов.

### `python manage_standards.py mark-suspicious "ОСТ 33056-80"`
Пометить стандарт как подозрительный.

## Важные ограничения

### Реальность стандартов
- 🔴 Большинство стандартов платные
- 🔴 Официальных API нет
- 🔴 Массовое автоскачивание может быть проблемным

### Production стратегия
1. ✅ Загружаем только нужные стандарты
2. ✅ Пользователь может загрузить PDF вручную
3. ✅ Индексируем загруженные файлы
4. ✅ Работаем только из локальной БД

## Структура модулей

```
standards/
    database/
        models.py          # SQLAlchemy модели
    manager/
        standard_manager.py # Главный менеджер
    downloader/
        base_downloader.py  # Базовый класс
        iso_downloader.py
        din_downloader.py
        gost_downloader.py
        ost_downloader.py
    parser/
        pdf_parser.py       # Парсинг PDF → JSON
    versioning/
        version_manager.py  # Управление версиями
    integrity/
        update_checker.py   # Проверка обновлений
    cache/
        cache_manager.py    # Кэширование (Redis)
```

## Производительность

### Время доступа
- Internet → 1-5 сек
- Database → 5-20 мс
- Cache (Redis) → 1-5 мс

### Результат
Бот отвечает как промышленная система благодаря работе из БД/кэша.
