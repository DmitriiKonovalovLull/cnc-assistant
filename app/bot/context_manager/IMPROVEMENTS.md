# Улучшения Context Manager

## Выполненные улучшения

### ✅ 1. Асинхронные блокировки в RateLimiter
- Добавлены `asyncio.Lock` для каждого пользователя
- Методы `is_allowed()` и `get_remaining_time()` теперь асинхронные
- Сохранены синхронные версии (`is_allowed_sync`, `get_remaining_time_sync`) для обратной совместимости
- Потокобезопасный доступ к `user_messages`

### ✅ 2. Защита от переполнения памяти в метриках
- Использование `deque` с временным окном (24 часа по умолчанию)
- Автоматическая очистка старых записей при добавлении новых
- Дополнительная защита: ограничение максимального количества записей (10000)
- Асинхронная блокировка для потокобезопасности
- Синхронная версия для обратной совместимости

### ✅ 3. Архивация старых контекстов
- Автоматическая архивация контекстов старше `archive_days` (по умолчанию 7 дней)
- Сжатие архивов с помощью `gzip`
- Метод `get_archive_versions()` для получения истории версий
- Организация архивов в отдельной директории

### ✅ 4. Абстракция хранилища для Redis
- Абстрактный класс `ContextStorageBackend`
- Реализация `RedisContextStorage` для распределенного хранения
- Поддержка TTL для автоматического истечения
- Поддержка batch-операций (`get_many`, `set_many`)

### ✅ 5. Мониторинг памяти
- Класс `MonitoredContextManager` с методом `get_memory_stats()`
- Отслеживание:
  - Общего количества контекстов
  - Общего размера в байтах
  - Среднего и максимального размера контекста
  - Использования памяти процессом (через `psutil`)
- Автоматическое предупреждение при превышении 100 MB

### ✅ 6. Batch-операции
- Класс `BatchContextManager` с методами:
  - `get_many()` - получение нескольких контекстов
  - `set_many()` - сохранение нескольких контекстов
- Оптимизация загрузки из кэша и бэкенда

### ✅ 7. Валидация контекста
- Функция `validate_context()` проверяет:
  - Обязательные поля (user_id, session_id)
  - Типы данных (диаметры, длина)
  - Соотношения диаметров (внешняя/внутренняя обработка)
  - Диапазон значений (confidence 0-1)
- Автоматическая валидация при сохранении в `ContextManager.set()`

### ✅ 8. Система миграций контекста
- Класс `ContextMigration` для обновления структуры контекста
- Версионирование контекстов (`_version`)
- Автоматическое применение миграций при загрузке
- Отслеживание времени миграции (`_migrated_at`)

### ✅ 9. Уведомления об истечении
- Класс `ExpiringContextManager` с поддержкой callbacks
- Регистрация callbacks через `register_expiry_callback()`
- Автоматическая проверка истечения через `start_expiry_checker()`
- Вызов callbacks при истечении контекста

### ✅ 10. Экспорт метрик в Prometheus
- Класс `PrometheusMetrics` для интеграции с Prometheus
- Метрики:
  - `contexts_total` - общее количество контекстов
  - `context_size_bytes` - размеры контекстов (гистограмма)
  - `rate_limit_hits_total` - срабатывания rate limit
  - `message_processing_seconds` - время обработки сообщений
  - `memory_usage_bytes` - использование памяти
  - `cpu_usage_percent` - использование CPU
- Автоматическое обновление метрик через `start_updater()`

### ✅ 11. Исправлены магические числа
- `DEFAULT_RATE_LIMIT_MAX_MESSAGES = 10`
- `DEFAULT_RATE_LIMIT_PERIOD_SECONDS = 60`
- Использование констант вместо магических чисел

### ✅ 12. Оптимизация popitem
- Заменен `while len(...) >= max` на `if len(...) >= max`
- Удаляется только один самый старый контекст за раз

## Использование

### Асинхронный Rate Limiter:
```python
from app.bot.context_manager import RateLimiter

rate_limiter = RateLimiter(max_messages=10, per_seconds=60)

# Асинхронная версия
is_allowed = await rate_limiter.is_allowed(user_id)
remaining = await rate_limiter.get_remaining_time(user_id)

# Синхронная версия (для обратной совместимости)
is_allowed = rate_limiter.is_allowed_sync(user_id)
remaining = rate_limiter.get_remaining_time_sync(user_id)
```

### Метрики с временным окном:
```python
from app.bot.context_manager import BotMetrics

metrics = BotMetrics()

# Асинхронная версия
await metrics.add_response_time(0.5)

# Синхронная версия
metrics.add_response_time_sync(0.5)

# Получение статистики
stats = await metrics.get_stats()  # async
stats = metrics.get_stats_sync()   # sync
```

### FileContextStorage с архивацией:
```python
from app.bot.context_manager import FileContextStorage

storage = FileContextStorage(storage_dir="contexts", archive_days=7)

# Сохранение (автоматическая архивация старых версий)
storage.set(user_id, context)

# Получение архивных версий
archives = storage.get_archive_versions(user_id)
```

### Redis хранилище:
```python
import redis.asyncio as redis
from app.bot.context_manager import RedisContextStorage

redis_client = await redis.from_url("redis://localhost:6379")
storage = RedisContextStorage(redis_client, ttl_seconds=86400)

# Использование
context = storage.get(user_id)
storage.set(user_id, context)
```

### Мониторинг памяти:
```python
from app.bot.context_manager import MonitoredContextManager

manager = MonitoredContextManager(max_contexts=1000, ttl_hours=24)

# Получение статистики памяти
stats = manager.get_memory_stats()
# {'total_contexts': 150, 'total_size_bytes': 50000, ...}

# Логирование статистики
manager.log_memory_stats()
```

### Batch-операции:
```python
from app.bot.context_manager import BatchContextManager

manager = BatchContextManager(max_contexts=1000, ttl_hours=24)

# Получение нескольких контекстов
contexts = await manager.get_many(['user1', 'user2', 'user3'])

# Сохранение нескольких контекстов
await manager.set_many({
    'user1': context1,
    'user2': context2
})
```

### Валидация контекста:
```python
from app.bot.context_manager import validate_context

errors = validate_context(context)
if errors:
    raise ValueError(f"Invalid context: {', '.join(errors)}")
```

### Миграции:
```python
from app.bot.context_manager import ContextMigration

# Автоматически применяется при загрузке из FileContextStorage
# Можно применить вручную:
migrated_data = ContextMigration.migrate(old_data)
```

### Prometheus метрики:
```python
from app.bot.context_manager import PrometheusMetrics, MonitoredContextManager, RateLimiter

prom_metrics = PrometheusMetrics()

# Обновление метрик
prom_metrics.update(context_manager, rate_limiter)

# Автоматическое обновление
await prom_metrics.start_updater(context_manager, rate_limiter, interval_seconds=15)
```

## Обратная совместимость

Все изменения сохраняют обратную совместимость:
- Синхронные методы доступны для старого кода
- Старые вызовы работают без изменений
- Новые async методы используются в новом коде

## Производительность

- Асинхронные блокировки минимизируют блокировки
- Временное окно в метриках предотвращает переполнение памяти
- Архивация уменьшает количество файлов на диске
- Batch-операции оптимизируют загрузку множественных контекстов
