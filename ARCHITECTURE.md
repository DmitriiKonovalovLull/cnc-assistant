# Архитектура CNC Assistant

## Принципы

### Intent-based архитектура
Бот работает по принципу:
```
Message → Intent → Router → Handler → Engine → Response
```

**НЕ** используем:
- FSM-управляемую логику
- Жёсткие сценарии
- Кнопки вместо естественного языка

## Структура проекта

```
app/
    core/
        intent_system.py      # Определение намерений
        router.py              # Маршрутизация по интентам
        session.py             # Управление сессией
        
    handlers/
        standard_handler.py    # Обработка стандартов
        process_handler.py     # Расчёт режимов
        fit_handler.py         # Расчёт посадок
        thread_handler.py      # Расчёт резьбы
        surface_handler.py     # Расчёт шероховатости
        power_handler.py       # Проверка мощности
        standards_handler.py   # Управление базой стандартов
        
    services/
        standard_service.py    # Работа со стандартами
        ...

standards/
    registry/
        standard_family.py     # Типы стандартов (ISO, DIN, GOST, OST...)
        
    manager/
        standard_manager.py    # Главный менеджер стандартов
        
    downloader/
        base_downloader.py     # Базовый класс downloader
        iso_downloader.py      # Downloader для ISO
        din_downloader.py      # Downloader для DIN
        gost_downloader.py     # Downloader для GOST
        ost_downloader.py      # Downloader для OST
        ...
        
    validators/
        # Валидация PDF, SHA256 и т.д.
        
    storage/
        # Хранение стандартов

engines/
    thread_engine.py          # Движок расчёта резьбы
    fit_engine.py             # Движок расчёта посадок
    surface_engine.py         # Движок расчёта шероховатости
    process_engine.py         # Движок расчёта режимов
```

## Типы намерений (Intent)

- `GREETING` - Приветствие
- `HELP` - Помощь
- `STANDARD_LOOKUP` - Поиск стандарта
- `PROCESS_CALCULATION` - Расчёт режимов обработки
- `FIT_CALCULATION` - Расчёт посадок
- `THREAD_CALCULATION` - Расчёт резьбы
- `SURFACE_CALCULATION` - Расчёт шероховатости
- `POWER_CHECK` - Проверка мощности
- `DOWNLOAD_STANDARDS` - Загрузка стандартов
- `STANDARD_INTEGRITY_CHECK` - Проверка базы стандартов
- `ADMIN_CHECK` - Админские команды
- `UNKNOWN` - Неизвестный запрос

## Сессия (Session)

Сессия хранит:
- `current_standard` - Текущий стандарт
- `current_material` - Текущий материал
- `current_machine` - Текущий станок
- `current_operation` - Текущая операция
- `calculated_values` - Рассчитанные значения
- `history` - История операций

Очищается при:
- Приветствии
- Отмене ("нет", "отмена")

## Управление стандартами

### StandardManager

Главный менеджер стандартов:
- `update_all()` - Обновить все стандарты
- `verify_integrity()` - Проверить целостность
- `get_status()` - Получить статус базы
- `format_status_message()` - Форматировать сообщение со статусом

### Downloaders

Каждый downloader для страны:
- `fetch_list()` - Получить список стандартов
- `download_standard(id)` - Скачать стандарт
- `validate_pdf()` - Проверить PDF
- `calculate_sha()` - Вычислить SHA256
- `store_metadata()` - Сохранить метаданные

### Поддерживаемые стандарты

- ISO (Международные)
- DIN (Немецкие)
- ANSI (Американские)
- ASME (Американские инженерные)
- JIS (Японские)
- GOST (Государственные РФ)
- OST (Отраслевые РФ)
- EN (Европейские)
- BS (Британские)
- GB (Китайские)

## Примеры использования

### Проверка базы стандартов
```
Пользователь: проверка базы
Бот: 
=== STANDARD SYSTEM CHECK ===
✅ ISO: 1243
✅ DIN: 843
✅ GOST: 2101
⚠️ OST: 322 (2 missing)
✅ ANSI: 412

Integrity: ⚠️ ISSUES FOUND
===============================
```

### Загрузка стандартов
```
Пользователь: скачай все стандарты
Бot:
📥 Обновление стандартов
✅ ISO: 1243 стандартов
✅ DIN: 843 стандартов
✅ GOST: 2101 стандартов
⚠️ OST: 322 стандартов (некоторые недоступны публично)

Обновление завершено.
```

## Важные замечания

1. **ОСТ стандарты** редко доступны публично - основная стратегия: локальная база + загрузка пользователем
2. **ISO стандарты** платные и требуют API ключ или подписку
3. **Архитектура** должна поддерживать fallback стратегии когда стандарт не найден
4. **Сессия** очищается при приветствии для предотвращения "зацикленных сценариев"
