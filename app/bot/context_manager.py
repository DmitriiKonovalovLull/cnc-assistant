"""
МЕНЕДЖЕР КОНТЕКСТОВ - управление контекстами пользователей.
С поддержкой ограничений, очистки, rate limiting и персистентного хранения.
"""

import json
import logging
import time
import sys
from collections import OrderedDict, defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable, Awaitable, Any
import asyncio

from app.core.context import Context

logger = logging.getLogger(__name__)

# Константы
MAX_TELEGRAM_MESSAGE_LENGTH = 4096  # Ограничение Telegram API
TELEGRAM_SAFE_MESSAGE_LENGTH = 4000  # Безопасная длина с запасом

# Константы для Rate Limiter
DEFAULT_RATE_LIMIT_MAX_MESSAGES = 10
DEFAULT_RATE_LIMIT_PERIOD_SECONDS = 60


# ============================================================================
# RATE LIMITER
# ============================================================================

class RateLimiter:
    """Rate limiter для защиты от спама с асинхронной блокировкой."""
    
    def __init__(self, max_messages: int = DEFAULT_RATE_LIMIT_MAX_MESSAGES, 
                 per_seconds: int = DEFAULT_RATE_LIMIT_PERIOD_SECONDS):
        """
        Инициализация rate limiter.
        
        Args:
            max_messages: Максимальное количество сообщений
            per_seconds: За период времени (в секундах)
        """
        self.max_messages = max_messages
        self.per_seconds = per_seconds
        self.user_messages: Dict[str, List[float]] = defaultdict(list)
        self._locks: Dict[str, asyncio.Lock] = defaultdict(lambda: asyncio.Lock())
    
    async def is_allowed(self, user_id: str) -> bool:
        """
        Проверить, может ли пользователь отправить сообщение.
        Асинхронная версия с блокировкой для потокобезопасности.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если разрешено, False если превышен лимит
        """
        async with self._locks[user_id]:
            now = time.time()
            cutoff = now - self.per_seconds
            
            # Очищаем старые сообщения
            self.user_messages[user_id] = [
                ts for ts in self.user_messages[user_id] if ts > cutoff
            ]
            
            if len(self.user_messages[user_id]) >= self.max_messages:
                return False
            
            self.user_messages[user_id].append(now)
            return True
    
    def is_allowed_sync(self, user_id: str) -> bool:
        """
        Синхронная версия для обратной совместимости.
        Использует блокировку через asyncio.run если нужно.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если разрешено, False если превышен лимит
        """
        now = time.time()
        cutoff = now - self.per_seconds
        
        # Очищаем старые сообщения
        self.user_messages[user_id] = [
            ts for ts in self.user_messages[user_id] if ts > cutoff
        ]
        
        if len(self.user_messages[user_id]) >= self.max_messages:
            return False
        
        self.user_messages[user_id].append(now)
        return True
    
    async def get_remaining_time(self, user_id: str) -> float:
        """
        Получить время до следующего разрешенного сообщения.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Время в секундах до разрешения
        """
        async with self._locks[user_id]:
            if user_id not in self.user_messages or not self.user_messages[user_id]:
                return 0.0
            
            now = time.time()
            oldest_message = min(self.user_messages[user_id])
            elapsed = now - oldest_message
            
            if elapsed >= self.per_seconds:
                return 0.0
            
            return self.per_seconds - elapsed
    
    def get_remaining_time_sync(self, user_id: str) -> float:
        """
        Синхронная версия для обратной совместимости.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Время в секундах до разрешения
        """
        if user_id not in self.user_messages or not self.user_messages[user_id]:
            return 0.0
        
        now = time.time()
        oldest_message = min(self.user_messages[user_id])
        elapsed = now - oldest_message
        
        if elapsed >= self.per_seconds:
            return 0.0
        
        return self.per_seconds - elapsed


# ============================================================================
# CONTEXT MANAGER
# ============================================================================

class ContextManager:
    """Менеджер контекстов с автоматической очисткой."""
    
    def __init__(self, max_contexts: int = 1000, ttl_hours: int = 24):
        """
        Инициализация менеджера контекстов.
        
        Args:
            max_contexts: Максимальное количество контекстов в памяти
            ttl_hours: Время жизни контекста в часах
        """
        self.contexts: OrderedDict[str, Tuple[Context, datetime]] = OrderedDict()
        self.max_contexts = max_contexts
        self.ttl = timedelta(hours=ttl_hours)
    
    def get(self, user_id: str) -> Optional[Context]:
        """
        Получить контекст пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Контекст или None
        """
        if user_id in self.contexts:
            context, timestamp = self.contexts[user_id]
            if datetime.now() - timestamp < self.ttl:
                # Обновляем позицию в OrderedDict (LRU)
                self.contexts.move_to_end(user_id)
                return context
            else:
                # Удаляем старый контекст
                del self.contexts[user_id]
                logger.debug(f"Removed expired context for user {user_id}")
        return None
    
    def set(self, user_id: str, context: Context):
        """
        Сохранить контекст пользователя с валидацией.
        
        Args:
            user_id: ID пользователя
            context: Контекст для сохранения
            
        Raises:
            ValueError: Если контекст невалиден
        """
        # Валидация контекста перед сохранением
        from app.bot.context_manager import validate_context
        errors = validate_context(context)
        if errors:
            raise ValueError(f"Invalid context for user {user_id}: {', '.join(errors)}")
        
        # Очищаем старые контексты при необходимости (оптимизировано)
        if len(self.contexts) >= self.max_contexts:
            # Удаляем только самый старый
            oldest_user_id, _ = self.contexts.popitem(last=False)
            logger.debug(f"Removed oldest context for user {oldest_user_id} (LRU)")
        
        self.contexts[user_id] = (context, datetime.now())
        logger.debug(f"Saved context for user {user_id}")
    
    def delete(self, user_id: str) -> bool:
        """
        Удалить контекст пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если контекст был удален
        """
        if user_id in self.contexts:
            del self.contexts[user_id]
            logger.info(f"Deleted context for user {user_id}")
            return True
        return False
    
    def cleanup_expired(self) -> int:
        """
        Очистить истекшие контексты.
        
        Returns:
            Количество удаленных контекстов
        """
        now = datetime.now()
        expired = []
        
        for user_id, (_, timestamp) in list(self.contexts.items()):
            if now - timestamp > self.ttl:
                expired.append(user_id)
        
        for user_id in expired:
            del self.contexts[user_id]
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired contexts")
        
        return len(expired)
    
    def get_stats(self) -> Dict[str, int]:
        """
        Получить статистику менеджера.
        
        Returns:
            Словарь со статистикой
        """
        return {
            'total_contexts': len(self.contexts),
            'max_contexts': self.max_contexts
        }


# ============================================================================
# ПЕРСИСТЕНТНОЕ ХРАНИЛИЩЕ
# ============================================================================

class FileContextStorage:
    """Хранение контекстов в файлах с архивацией старых версий."""
    
    def __init__(self, storage_dir: str = "contexts", archive_days: int = 7):
        """
        Инициализация файлового хранилища.
        
        Args:
            storage_dir: Директория для хранения контекстов
            archive_days: Количество дней до архивации старой версии
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir = self.storage_dir / "archive"
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.archive_days = archive_days
    
    def _get_path(self, user_id: str) -> Path:
        """Получить путь к файлу контекста."""
        # Используем первые 2 символа user_id для организации в поддиректории
        subdir = user_id[:2] if len(user_id) >= 2 else "00"
        subdir_path = self.storage_dir / subdir
        subdir_path.mkdir(exist_ok=True)
        return subdir_path / f"{user_id}.json"
    
    def get(self, user_id: str) -> Optional[Context]:
        """
        Получить контекст из файла с применением миграций.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Контекст или None
        """
        path = self._get_path(user_id)
        if not path.exists():
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Применяем миграции если нужно
            from app.bot.context_manager import ContextMigration
            data = ContextMigration.migrate(data)
            
            return Context.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load context from {path}: {e}")
            return None
    
    def set(self, user_id: str, context: Context):
        """
        Сохранить контекст в файл с автоматической архивацией старой версии.
        
        Args:
            user_id: ID пользователя
            context: Контекст для сохранения
        """
        path = self._get_path(user_id)
        
        # Если файл существует и старше archive_days, архивируем
        if path.exists():
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime)
                if datetime.now() - mtime > timedelta(days=self.archive_days):
                    self._archive_old_version(user_id)
            except Exception as e:
                logger.warning(f"Failed to check file age for {user_id}: {e}")
        
        # Сохраняем новую версию
        try:
            context_dict = context.to_dict()
            # Добавляем версию для миграций
            context_dict['_version'] = ContextMigration.CURRENT_VERSION
            context_dict['_updated_at'] = datetime.now().isoformat()
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(context_dict, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save context to {path}: {e}")
    
    def _archive_old_version(self, user_id: str):
        """
        Заархивировать старую версию контекста.
        
        Args:
            user_id: ID пользователя
        """
        path = self._get_path(user_id)
        if not path.exists():
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_path = self.archive_dir / f"{user_id}_{timestamp}.json.gz"
        
        try:
            import gzip
            import shutil
            
            with open(path, 'rb') as f_in:
                with gzip.open(archive_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Удаляем старый файл после успешной архивации
            path.unlink()
            logger.info(f"Archived old context for user {user_id} to {archive_path}")
        except Exception as e:
            logger.error(f"Failed to archive context for user {user_id}: {e}")
    
    def get_archive_versions(self, user_id: str) -> List[Path]:
        """
        Получить список архивных версий контекста пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список путей к архивным файлам
        """
        pattern = f"{user_id}_*.json.gz"
        return sorted(self.archive_dir.glob(pattern))
    
    def delete(self, user_id: str) -> bool:
        """
        Удалить контекст из файла.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если файл был удален
        """
        path = self._get_path(user_id)
        if path.exists():
            try:
                path.unlink()
                return True
            except Exception as e:
                logger.error(f"Failed to delete context file {path}: {e}")
        return False


# ============================================================================
# УТИЛИТЫ ДЛЯ СООБЩЕНИЙ
# ============================================================================

def split_long_message(text: str, max_length: int = TELEGRAM_SAFE_MESSAGE_LENGTH) -> List[str]:
    """
    Разбить длинное сообщение на части.
    
    Args:
        text: Текст сообщения
        max_length: Максимальная длина части
        
    Returns:
        Список частей сообщения
    """
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current_part = []
    current_length = 0
    
    for line in text.split('\n'):
        line_length = len(line) + 1  # +1 for newline
        
        if current_length + line_length > max_length:
            if current_part:
                parts.append('\n'.join(current_part))
            current_part = [line]
            current_length = line_length
        else:
            current_part.append(line)
            current_length += line_length
    
    if current_part:
        parts.append('\n'.join(current_part))
    
    # Добавляем нумерацию страниц
    if len(parts) > 1:
        for i, part in enumerate(parts, 1):
            parts[i-1] = f"{part}\n\n<i>Страница {i}/{len(parts)}</i>"
    
    return parts


def is_mobile(user_agent: Optional[str]) -> bool:
    """
    Проверить, является ли устройство мобильным.
    
    Args:
        user_agent: User-Agent строка (если доступна)
        
    Returns:
        True если мобильное устройство
    """
    if not user_agent:
        return False
    mobile_keywords = ['mobile', 'android', 'iphone', 'ipad', 'tablet']
    return any(keyword in user_agent.lower() for keyword in mobile_keywords)


def format_for_device(text: str, is_mobile: bool) -> str:
    """
    Адаптировать форматирование под устройство.
    
    Args:
        text: Текст сообщения
        is_mobile: Является ли устройство мобильным
        
    Returns:
        Адаптированный текст
    """
    if not is_mobile:
        return text
    
    # Для мобильных: упрощаем форматирование
    lines = text.split('\n')
    formatted = []
    
    for line in lines:
        # Упрощаем длинные строки (но сохраняем важную информацию)
        if len(line) > 60:
            # Разбиваем только очень длинные строки
            words = line.split()
            current_line = []
            current_length = 0
            
            for word in words:
                word_length = len(word) + 1
                if current_length + word_length > 60 and current_line:
                    formatted.append(' '.join(current_line))
                    current_line = [word]
                    current_length = word_length
                else:
                    current_line.append(word)
                    current_length += word_length
            
            if current_line:
                formatted.append(' '.join(current_line))
        else:
            formatted.append(line)
    
    return '\n'.join(formatted)


# ============================================================================
# МЕТРИКИ
# ============================================================================

@dataclass
class BotMetrics:
    """Метрики работы бота с защитой от переполнения памяти."""
    
    total_messages: int = 0
    total_photos: int = 0
    total_calculations: int = 0
    total_errors: int = 0
    users_count: int = 0
    response_times: List[Tuple[datetime, float]] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _window_hours: int = 24  # Временное окно для метрик
    
    def __post_init__(self):
        """Инициализация после создания dataclass."""
        if not hasattr(self, '_lock') or self._lock is None:
            self._lock = asyncio.Lock()
    
    async def add_response_time(self, seconds: float):
        """
        Добавить время ответа с автоматической очисткой старых записей.
        
        Args:
            seconds: Время ответа в секундах
        """
        async with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(hours=self._window_hours)
            
            # Добавляем новую запись
            self.response_times.append((now, seconds))
            
            # Очищаем старые записи (старше window_hours)
            self.response_times = [
                (ts, val) for ts, val in self.response_times if ts > cutoff
            ]
            
            # Дополнительная защита: ограничиваем максимальное количество записей
            max_records = 10000
            if len(self.response_times) > max_records:
                # Оставляем последние max_records записей
                self.response_times = self.response_times[-max_records:]
    
    def add_response_time_sync(self, seconds: float):
        """
        Синхронная версия для обратной совместимости.
        
        Args:
            seconds: Время ответа в секундах
        """
        now = datetime.now()
        cutoff = now - timedelta(hours=self._window_hours)
        
        # Добавляем новую запись
        self.response_times.append((now, seconds))
        
        # Очищаем старые записи
        self.response_times = [
            (ts, val) for ts, val in self.response_times if ts > cutoff
        ]
        
        # Дополнительная защита
        max_records = 10000
        if len(self.response_times) > max_records:
            self.response_times = self.response_times[-max_records:]
    
    async def get_stats(self) -> Dict[str, any]:
        """
        Получить статистику за текущее временное окно.
        
        Returns:
            Словарь со статистикой
        """
        async with self._lock:
            return self._calculate_stats()
    
    def get_stats_sync(self) -> Dict[str, any]:
        """
        Синхронная версия для обратной совместимости.
        
        Returns:
            Словарь со статистикой
        """
        return self._calculate_stats()
    
    def _calculate_stats(self) -> Dict[str, any]:
        """Внутренний метод расчета статистики."""
        import statistics
        
        stats = {
            'total_messages': self.total_messages,
            'total_photos': self.total_photos,
            'total_calculations': self.total_calculations,
            'total_errors': self.total_errors,
            'users_count': self.users_count,
        }
        
        if self.response_times:
            values = [val for _, val in self.response_times]
            stats['avg_response_time'] = statistics.mean(values)
            if len(values) > 20:
                stats['p95_response_time'] = statistics.quantiles(values, n=20)[18]
            else:
                stats['p95_response_time'] = max(values) if values else 0.0
            stats['min_response_time'] = min(values)
            stats['max_response_time'] = max(values)
            stats['response_times_count'] = len(values)
        else:
            stats['avg_response_time'] = 0.0
            stats['p95_response_time'] = 0.0
            stats['min_response_time'] = 0.0
            stats['max_response_time'] = 0.0
            stats['response_times_count'] = 0
        
        return stats
    
    def reset(self):
        """Сбросить метрики."""
        self.total_messages = 0
        self.total_photos = 0
        self.total_calculations = 0
        self.total_errors = 0
        self.users_count = 0
        self.response_times.clear()


# Глобальный экземпляр метрик
metrics = BotMetrics()


# ============================================================================
# ВАЛИДАЦИЯ КОНТЕКСТА
# ============================================================================

def validate_context(context: Context) -> List[str]:
    """
    Проверить контекст на корректность.
    
    Args:
        context: Контекст для проверки
        
    Returns:
        Список ошибок (пустой если все ок)
    """
    errors = []
    
    # Проверка обязательных полей
    if not context.user_id:
        errors.append("user_id is required")
    
    if not context.session_id:
        errors.append("session_id is required")
    
    # Проверка типов данных
    if context.diameter_start is not None:
        if not isinstance(context.diameter_start, (int, float)):
            errors.append(f"diameter_start must be number, got {type(context.diameter_start)}")
        elif context.diameter_start < 0:
            errors.append(f"diameter_start cannot be negative: {context.diameter_start}")
    
    if context.diameter_end is not None:
        if not isinstance(context.diameter_end, (int, float)):
            errors.append(f"diameter_end must be number, got {type(context.diameter_end)}")
        elif context.diameter_end < 0:
            errors.append(f"diameter_end cannot be negative: {context.diameter_end}")
    
    # Проверка соотношения диаметров
    if context.diameter_start is not None and context.diameter_end is not None:
        # Определяем тип обработки: если is_external явно не установлен,
        # определяем по соотношению диаметров
        is_external = None
        if hasattr(context, 'is_external') and context.is_external is not None:
            is_external = context.is_external
        else:
            # Автоматическое определение: если start > end - внешняя обработка
            is_external = context.diameter_start > context.diameter_end
        
        # Валидация в зависимости от типа обработки
        if is_external:
            # Внешняя обработка: диаметр начала должен быть больше диаметра конца
            if context.diameter_start <= context.diameter_end:
                errors.append(
                    f"For external turning, start diameter must be > end diameter: "
                    f"{context.diameter_start} <= {context.diameter_end}"
                )
        else:
            # Внутренняя обработка (расточка): диаметр начала должен быть меньше диаметра конца
            if context.diameter_start >= context.diameter_end:
                errors.append(
                    f"For internal turning (boring), start diameter must be < end diameter: "
                    f"{context.diameter_start} >= {context.diameter_end}"
                )
    
    # Проверка длины
    if context.length is not None:
        if not isinstance(context.length, (int, float)):
            errors.append(f"length must be number, got {type(context.length)}")
        elif context.length <= 0:
            errors.append(f"length must be positive: {context.length}")
    
    # Проверка доверия
    if context.overall_confidence is not None:
        if not isinstance(context.overall_confidence, (int, float)):
            errors.append(f"overall_confidence must be number, got {type(context.overall_confidence)}")
        elif not 0 <= context.overall_confidence <= 1:
            errors.append(f"overall_confidence must be between 0 and 1: {context.overall_confidence}")
    
    return errors


# ============================================================================
# МИГРАЦИИ КОНТЕКСТА
# ============================================================================

class ContextMigration:
    """Миграции для контекста при изменении структуры."""
    
    VERSIONS = {
        '1.0': lambda d: d,  # Базовая версия
        '1.1': lambda d: {**d, 'lang': d.get('lang', 'ru')},  # Добавлен язык
        '1.2': lambda d: {**d, 'tool_display_name': d.get('tool_display_name')},  # Добавлено имя инструмента
    }
    
    CURRENT_VERSION = '1.2'
    
    @classmethod
    def migrate(cls, data: Dict) -> Dict:
        """
        Применить миграции для приведения к текущей версии.
        
        Args:
            data: Данные контекста
            
        Returns:
            Мигрированные данные
        """
        version = data.get('_version', '1.0')
        
        if version == cls.CURRENT_VERSION:
            return data
        
        # Применяем последовательные миграции
        versions = sorted(cls.VERSIONS.keys())
        start_idx = versions.index(version) if version in versions else 0
        
        for v in versions[start_idx:]:
            if v == version:
                continue
            data = cls.VERSIONS[v](data)
            data['_version'] = v
        
        data['_version'] = cls.CURRENT_VERSION
        data['_migrated_at'] = datetime.now().isoformat()
        
        return data


# ============================================================================
# АБСТРАКЦИЯ ХРАНИЛИЩА
# ============================================================================

from abc import ABC, abstractmethod


class ContextStorageBackend(ABC):
    """Абстрактный класс для бэкенда хранения контекстов."""
    
    @abstractmethod
    def get(self, user_id: str) -> Optional[Context]:
        """Получить контекст."""
        pass
    
    @abstractmethod
    def set(self, user_id: str, context: Context):
        """Сохранить контекст."""
        pass
    
    @abstractmethod
    def delete(self, user_id: str) -> bool:
        """Удалить контекст."""
        pass
    
    async def get_many(self, user_ids: List[str]) -> Dict[str, Optional[Context]]:
        """
        Получить контексты для нескольких пользователей (опционально).
        
        Args:
            user_ids: Список ID пользователей
            
        Returns:
            Словарь {user_id: context}
        """
        return {user_id: self.get(user_id) for user_id in user_ids}
    
    async def set_many(self, contexts: Dict[str, Context]):
        """
        Сохранить контексты для нескольких пользователей (опционально).
        
        Args:
            contexts: Словарь {user_id: context}
        """
        for user_id, context in contexts.items():
            self.set(user_id, context)


class RedisContextStorage(ContextStorageBackend):
    """Хранение контекстов в Redis."""
    
    def __init__(self, redis_client, ttl_seconds: int = 86400):
        """
        Инициализация Redis хранилища.
        
        Args:
            redis_client: Клиент Redis (redis.asyncio.Redis или redis.Redis)
            ttl_seconds: TTL для ключей в секундах (по умолчанию 24 часа)
        """
        self.redis = redis_client
        self.ttl = ttl_seconds
    
    def get(self, user_id: str) -> Optional[Context]:
        """
        Получить контекст из Redis.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Контекст или None
        """
        try:
            data = self.redis.get(f"context:{user_id}")
            if data:
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                data_dict = json.loads(data)
                # Применяем миграции
                data_dict = ContextMigration.migrate(data_dict)
                return Context.from_dict(data_dict)
        except Exception as e:
            logger.error(f"Failed to get context from Redis for user {user_id}: {e}")
        return None
    
    def set(self, user_id: str, context: Context):
        """
        Сохранить контекст в Redis.
        
        Args:
            user_id: ID пользователя
            context: Контекст для сохранения
        """
        try:
            context_dict = context.to_dict()
            context_dict['_version'] = ContextMigration.CURRENT_VERSION
            context_dict['_updated_at'] = datetime.now().isoformat()
            
            data = json.dumps(context_dict, ensure_ascii=False, default=str)
            self.redis.setex(f"context:{user_id}", self.ttl, data)
        except Exception as e:
            logger.error(f"Failed to set context in Redis for user {user_id}: {e}")
    
    def delete(self, user_id: str) -> bool:
        """
        Удалить контекст из Redis.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если контекст был удален
        """
        try:
            return bool(self.redis.delete(f"context:{user_id}"))
        except Exception as e:
            logger.error(f"Failed to delete context from Redis for user {user_id}: {e}")
            return False


# ============================================================================
# УЛУЧШЕННЫЙ CONTEXT MANAGER
# ============================================================================

class MonitoredContextManager(ContextManager):
    """ContextManager с мониторингом памяти."""
    
    def get_memory_stats(self) -> Dict[str, any]:
        """
        Получить статистику использования памяти.
        
        Returns:
            Словарь со статистикой памяти
        """
        import sys
        
        if not self.contexts:
            return {
                'total_contexts': 0,
                'total_size_bytes': 0,
                'avg_size_bytes': 0.0,
                'max_size_bytes': 0,
                'process_memory_mb': 0.0
            }
        
        # Оцениваем размер каждого контекста (приблизительно)
        sizes = []
        for context, _ in self.contexts.values():
            try:
                size = sys.getsizeof(context.to_dict())
                sizes.append(size)
            except Exception:
                sizes.append(0)
        
        # Получаем информацию о процессе
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            process_memory_mb = memory_info.rss / 1024 / 1024
        except ImportError:
            process_memory_mb = 0.0
        
        return {
            'total_contexts': len(self.contexts),
            'total_size_bytes': sum(sizes),
            'avg_size_bytes': sum(sizes) / len(sizes) if sizes else 0.0,
            'max_size_bytes': max(sizes) if sizes else 0,
            'process_memory_mb': process_memory_mb
        }
    
    def log_memory_stats(self):
        """Логировать статистику памяти."""
        stats = self.get_memory_stats()
        logger.info(
            f"Memory stats: {stats['total_contexts']} contexts, "
            f"total {stats['total_size_bytes'] / 1024:.2f} KB, "
            f"process {stats['process_memory_mb']:.2f} MB"
        )
        
        if stats['total_size_bytes'] > 100 * 1024 * 1024:  # >100 MB
            logger.warning("High memory usage detected!")


class BatchContextManager(MonitoredContextManager):
    """ContextManager с поддержкой batch-операций."""
    
    async def get_many(self, user_ids: List[str]) -> Dict[str, Optional[Context]]:
        """
        Получить контексты для нескольких пользователей.
        
        Args:
            user_ids: Список ID пользователей
            
        Returns:
            Словарь {user_id: context}
        """
        results = {}
        
        # Разделяем на найденные в кэше и требующие загрузки из бэкенда
        cached_ids = []
        backend_ids = []
        
        for user_id in user_ids:
            if user_id in self.contexts:
                context, timestamp = self.contexts[user_id]
                if datetime.now() - timestamp < self.ttl:
                    results[user_id] = context
                    cached_ids.append(user_id)
                    # Обновляем позицию в LRU
                    self.contexts.move_to_end(user_id)
                else:
                    # Истекший контекст
                    del self.contexts[user_id]
                    backend_ids.append(user_id)
            else:
                backend_ids.append(user_id)
        
        # Загружаем из бэкенда если есть
        # (требует реализации в подклассах или через композицию)
        
        return results
    
    async def set_many(self, contexts: Dict[str, Context]):
        """
        Сохранить контексты для нескольких пользователей.
        
        Args:
            contexts: Словарь {user_id: context}
        """
        for user_id, context in contexts.items():
            self.set(user_id, context)


class ExpiringContextManager(BatchContextManager):
    """ContextManager с уведомлениями об истечении."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.expiry_callbacks: Dict[str, List] = defaultdict(list)
        self._check_task: Optional[asyncio.Task] = None
    
    def register_expiry_callback(self, user_id: str, callback):
        """
        Зарегистрировать callback при истечении контекста.
        
        Args:
            user_id: ID пользователя
            callback: Асинхронная функция callback(user_id: str) -> None
        """
        self.expiry_callbacks[user_id].append(callback)
    
    async def start_expiry_checker(self, interval_seconds: int = 3600):
        """
        Запустить периодическую проверку истечения.
        
        Args:
            interval_seconds: Интервал проверки в секундах
        """
        async def check_loop():
            while True:
                await asyncio.sleep(interval_seconds)
                await self._check_expired_contexts()
        
        self._check_task = asyncio.create_task(check_loop())
    
    async def _check_expired_contexts(self):
        """Проверить истекшие контексты и вызвать callbacks."""
        now = datetime.now()
        expired = []
        
        for user_id, (_, timestamp) in list(self.contexts.items()):
            if now - timestamp > self.ttl:
                expired.append(user_id)
        
        for user_id in expired:
            # Вызываем callbacks
            if user_id in self.expiry_callbacks:
                for callback in self.expiry_callbacks[user_id]:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(user_id)
                        else:
                            callback(user_id)
                    except Exception as e:
                        logger.error(f"Expiry callback failed for user {user_id}: {e}")
            
            # Удаляем контекст
            del self.contexts[user_id]
            logger.info(f"Context expired for user {user_id}")
    
    async def stop_expiry_checker(self):
        """Остановить проверку истечения."""
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass


# ============================================================================
# ПРОМЕТЕЙ МЕТРИКИ
# ============================================================================

class PrometheusMetrics:
    """Метрики для Prometheus."""
    
    def __init__(self):
        """Инициализация метрик Prometheus."""
        self._metrics_available = False
        
        try:
            from prometheus_client import Gauge, Counter, Histogram
            self._metrics_available = True
            
            # Метрики контекстов
            self.contexts_total = Gauge('contexts_total', 'Total number of contexts')
            self.context_size_bytes = Histogram('context_size_bytes', 'Context size in bytes', buckets=[1000, 5000, 10000, 50000, 100000])
            self.rate_limit_hits = Counter('rate_limit_hits_total', 'Rate limit hits', ['user_id'])
            self.message_processing_time = Histogram('message_processing_seconds', 'Message processing time', buckets=[0.1, 0.5, 1.0, 2.0, 5.0])
            
            # Системные метрики
            self.memory_usage = Gauge('memory_usage_bytes', 'Memory usage')
            self.cpu_usage = Gauge('cpu_usage_percent', 'CPU usage')
            
            logger.info("Prometheus metrics initialized")
        except ImportError:
            logger.warning("prometheus_client not available, Prometheus metrics disabled")
    
    def update(self, context_manager: MonitoredContextManager, rate_limiter: RateLimiter):
        """
        Обновить метрики.
        
        Args:
            context_manager: Менеджер контекстов
            rate_limiter: Rate limiter
        """
        if not self._metrics_available:
            return
        
        try:
            import sys
            import psutil
            
            # Контексты
            self.contexts_total.set(len(context_manager.contexts))
            
            # Размеры контекстов
            for context, _ in context_manager.contexts.values():
                try:
                    size = sys.getsizeof(context.to_dict())
                    self.context_size_bytes.observe(size)
                except Exception:
                    pass
            
            # Системные метрики
            process = psutil.Process()
            self.memory_usage.set(process.memory_info().rss)
            self.cpu_usage.set(process.cpu_percent())
        except Exception as e:
            logger.error(f"Failed to update Prometheus metrics: {e}")
    
    async def start_updater(self, context_manager: MonitoredContextManager, 
                           rate_limiter: RateLimiter, interval_seconds: int = 15):
        """
        Запустить периодическое обновление метрик.
        
        Args:
            context_manager: Менеджер контекстов
            rate_limiter: Rate limiter
            interval_seconds: Интервал обновления в секундах
        """
        while True:
            try:
                self.update(context_manager, rate_limiter)
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Prometheus metrics updater: {e}")
                await asyncio.sleep(interval_seconds)


# Глобальный экземпляр метрик Prometheus (опционально)
prometheus_metrics: Optional[PrometheusMetrics] = None

try:
    prometheus_metrics = PrometheusMetrics()
except Exception:
    pass
