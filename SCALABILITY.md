# 🚀 Масштабируемость и оптимизация

Документация по оптимизациям для масштабируемости и подготовки к интеграции LLM.

## 📋 Созданные сервисы

### 1. ContextRepository (`app/services/context_repository.py`)

**Проблема:** Контекст хранился только в памяти (`user_contexts: Dict`), что не масштабируется для нескольких инстансов бота.

**Решение:** 
- Кэширование в памяти с TTL
- Персистентное хранение в БД (готово к реализации)
- Автоматическая очистка истекшего кэша

**Использование:**
```python
from app.services.context_repository import ContextRepository

repository = ContextRepository(db_session=session)

# Получить контекст
context = repository.get_context(user_id, session_id)

# Сохранить контекст
repository.save_context(context)

# Удалить контекст
repository.delete_context(user_id)
```

### 2. LLMAdapter (`app/services/llm_adapter.py`)

**Проблема:** Нет абстракции для будущей интеграции LLM, все захардкожено.

**Решение:**
- Абстрактный интерфейс `LLMAdapter`
- Текущая реализация `RuleBasedLLMAdapter` (без реального LLM)
- Готовность к интеграции OpenAI, Anthropic, локальных моделей
- Фабрика `LLMFactory` для создания адаптеров

**Использование:**
```python
from app.services.llm_adapter import LLMFactory, LLMProvider

# Текущая реализация (правила)
adapter = LLMFactory.create_adapter(LLMProvider.LOCAL)

# В будущем - реальный LLM
# adapter = LLMFactory.create_adapter(LLMProvider.OPENAI, api_key="...")

recommendation = await adapter.generate_recommendation(context, user_message)
```

### 3. CacheService (`app/services/cache_service.py`)

**Проблема:** Нет кэширования расчетов и знаний, каждый раз пересчитывается.

**Решение:**
- Кэширование с TTL
- Декораторы `@cached` и `@cached_async`
- Автоматическая генерация ключей
- Статистика использования кэша

**Использование:**
```python
from app.services.cache_service import cached, cached_async

# Синхронная функция
@cached(ttl_seconds=3600)
def expensive_calculation(param1, param2):
    # Тяжелые вычисления
    return result

# Асинхронная функция
@cached_async(ttl_seconds=1800)
async def async_operation(param):
    # Асинхронные операции
    return result
```

### 4. DatabasePool (`app/services/database_pool.py`)

**Проблема:** Каждый раз создается новое соединение с БД, нет переиспользования.

**Решение:**
- Пул соединений с настраиваемым размером
- Переиспользование соединений
- Контекстный менеджер для автоматического управления
- Статус пула для мониторинга

**Использование:**
```python
from app.services.database_pool import DatabasePool

db_pool = DatabasePool(db_url="sqlite:///...", pool_size=5)

# Использование с контекстным менеджером
with db_pool.get_session() as session:
    # Работа с БД
    pass

# Статус пула
status = db_pool.get_pool_status()
```

### 5. TrainingDataExporter (`app/services/training_data_exporter.py`)

**Проблема:** Экспорт данных для обучения не оптимизирован, нет батчинга.

**Решение:**
- Батчинг для больших объемов данных
- Поддержка JSONL и JSON форматов
- Форматы для fine-tuning (ChatML, Alpaca, Instruction)
- Оптимизированная итерация по данным

**Использование:**
```python
from app.services.training_data_exporter import TrainingDataExporter

exporter = TrainingDataExporter(db_session=session, batch_size=1000)

# Экспорт в JSONL
exporter.export_to_jsonl(Path("data/training.jsonl"))

# Экспорт для fine-tuning
exporter.export_for_finetuning(
    Path("data/finetuning.jsonl"),
    format_type="chatml"
)
```

## 🔧 Интеграция в бот

Все новые сервисы интегрированы в `telegram_bot.py`:

1. **DatabasePool** - используется для всех операций с БД
2. **ContextRepository** - используется вместо `user_contexts` dict
3. **LLMAdapter** - готов к использованию (пока правило-основанный)
4. **CacheService** - можно использовать через декораторы

## 📊 Метрики производительности

### До оптимизации:
- Контекст только в памяти → не масштабируется
- Новое соединение БД на каждый запрос → медленно
- Нет кэширования → повторные расчеты
- Нет батчинга → медленный экспорт данных

### После оптимизации:
- ✅ Контекст в БД + кэш → масштабируется
- ✅ Пул соединений → быстрее работа с БД
- ✅ Кэширование → меньше повторных расчетов
- ✅ Батчинг → быстрый экспорт данных

## 🎯 Подготовка к LLM

### Текущее состояние:
- `RuleBasedLLMAdapter` - использует существующую логику
- Все методы LLM адаптера реализованы через правила

### Для интеграции реального LLM:

1. **Создать новый адаптер:**
```python
class OpenAIAdapter(LLMAdapter):
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
    
    async def generate_recommendation(self, context, user_message):
        # Использовать OpenAI API
        ...
```

2. **Использовать в коде:**
```python
adapter = LLMFactory.create_adapter(
    LLMProvider.OPENAI,
    api_key=os.getenv("OPENAI_API_KEY")
)
```

3. **Все остальное остается без изменений** - абстракция скрывает детали реализации.

## 🔄 Миграция

### Постепенная миграция:
1. ✅ Новые сервисы созданы и интегрированы
2. ✅ Старый код продолжает работать (fallback)
3. ⏳ Постепенно переводить на новые сервисы
4. ⏳ Удалить старый код после полной миграции

### Обратная совместимость:
- `user_contexts` dict все еще работает как fallback
- Старые функции сохранения БД продолжают работать
- Новые сервисы опциональны

## 📈 Дальнейшие оптимизации

### Планируется:
1. **Redis для кэша** - распределенный кэш для нескольких инстансов
2. **PostgreSQL вместо SQLite** - для продакшена
3. **Очередь задач** - для тяжелых операций (OCR, расчеты)
4. **Метрики и мониторинг** - Prometheus, Grafana
5. **Балансировка нагрузки** - для нескольких инстансов бота

### Готовность к масштабированию:
- ✅ Архитектура готова к горизонтальному масштабированию
- ✅ Контекст можно хранить в БД/Redis
- ✅ Пул соединений готов к PostgreSQL
- ✅ LLM адаптер готов к интеграции
- ✅ Экспорт данных оптимизирован для обучения

## 🧪 Тестирование

Для проверки оптимизаций:

```python
# Проверка кэша
from app.services.cache_service import _cache_service
stats = _cache_service.stats()
print(f"Cache: {stats}")

# Проверка пула БД
from app.services.database_pool import db_pool
status = db_pool.get_pool_status()
print(f"DB Pool: {status}")

# Проверка репозитория контекста
from app.services.context_repository import context_repository
context = context_repository.get_context(user_id)
```

## 📚 Дополнительная документация

- `ARCHITECTURE.md` - общая архитектура системы
- `IMPLEMENTATION.md` - детали реализации
- `AI_BOT.md` - описание AI-бота
- `TOOL_PARSING.md` - парсинг инструментов
