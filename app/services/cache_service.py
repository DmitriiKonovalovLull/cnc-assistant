"""
Сервис кэширования для оптимизации производительности.
Поддерживает кэширование расчетов, знаний и других данных.
"""

import logging
import hashlib
import json
from typing import Any, Optional, Callable, Dict
from datetime import datetime, timedelta
from functools import wraps
from threading import Lock

logger = logging.getLogger(__name__)


class CacheService:
    """
    Сервис кэширования с поддержкой TTL и инвалидации.
    """
    
    def __init__(self, default_ttl_seconds: int = 3600):
        """
        Инициализация сервиса кэширования.
        
        Args:
            default_ttl_seconds: Время жизни кэша по умолчанию (секунды)
        """
        self.default_ttl = timedelta(seconds=default_ttl_seconds)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """
        Получить значение из кэша.
        
        Args:
            key: Ключ кэша
            
        Returns:
            Значение или None если не найдено или истекло
        """
        with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            expires_at = entry.get('expires_at')
            
            if expires_at and datetime.now() > expires_at:
                # Истекло - удаляем
                del self._cache[key]
                return None
            
            return entry.get('value')
    
    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """
        Сохранить значение в кэш.
        
        Args:
            key: Ключ кэша
            value: Значение для кэширования
            ttl_seconds: Время жизни в секундах (None = по умолчанию)
        """
        with self._lock:
            ttl = timedelta(seconds=ttl_seconds) if ttl_seconds else self.default_ttl
            expires_at = datetime.now() + ttl
            
            self._cache[key] = {
                'value': value,
                'expires_at': expires_at,
                'created_at': datetime.now()
            }
    
    def delete(self, key: str) -> bool:
        """
        Удалить значение из кэша.
        
        Args:
            key: Ключ кэша
            
        Returns:
            True если удалено, False если не найдено
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self) -> int:
        """Очистить весь кэш."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count
    
    def clear_expired(self) -> int:
        """Очистить истекшие записи."""
        now = datetime.now()
        expired_keys = []
        
        with self._lock:
            for key, entry in list(self._cache.items()):
                expires_at = entry.get('expires_at')
                if expires_at and now > expires_at:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
        
        return len(expired_keys)
    
    def generate_key(self, prefix: str, *args, **kwargs) -> str:
        """
        Сгенерировать ключ кэша из параметров.
        
        Args:
            prefix: Префикс ключа
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
            
        Returns:
            Хэш ключ
        """
        # Сериализуем аргументы в строку
        key_parts = [prefix]
        
        if args:
            key_parts.append(json.dumps(args, sort_keys=True, default=str))
        
        if kwargs:
            key_parts.append(json.dumps(kwargs, sort_keys=True, default=str))
        
        key_string = ':'.join(key_parts)
        
        # Генерируем хэш
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def stats(self) -> Dict[str, Any]:
        """Получить статистику кэша."""
        with self._lock:
            now = datetime.now()
            total = len(self._cache)
            expired = sum(
                1 for entry in self._cache.values()
                if entry.get('expires_at') and now > entry.get('expires_at')
            )
            
            return {
                'total_entries': total,
                'expired_entries': expired,
                'active_entries': total - expired
            }


# Глобальный экземпляр кэша
_cache_service = CacheService()


def cached(ttl_seconds: Optional[int] = None, key_prefix: Optional[str] = None):
    """
    Декоратор для кэширования результатов функций.
    
    Args:
        ttl_seconds: Время жизни кэша в секундах
        key_prefix: Префикс ключа кэша (по умолчанию имя функции)
    
    Example:
        @cached(ttl_seconds=3600)
        def expensive_calculation(param1, param2):
            ...
    """
    def decorator(func: Callable) -> Callable:
        prefix = key_prefix or f"{func.__module__}.{func.__name__}"
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Генерируем ключ кэша
            cache_key = _cache_service.generate_key(prefix, *args, **kwargs)
            
            # Пытаемся получить из кэша
            cached_value = _cache_service.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {prefix}")
                return cached_value
            
            # Выполняем функцию
            logger.debug(f"Cache miss: {prefix}")
            result = func(*args, **kwargs)
            
            # Сохраняем в кэш
            _cache_service.set(cache_key, result, ttl_seconds)
            
            return result
        
        return wrapper
    
    return decorator


def cached_async(ttl_seconds: Optional[int] = None, key_prefix: Optional[str] = None):
    """
    Декоратор для кэширования результатов асинхронных функций.
    """
    def decorator(func: Callable) -> Callable:
        prefix = key_prefix or f"{func.__module__}.{func.__name__}"
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = _cache_service.generate_key(prefix, *args, **kwargs)
            
            cached_value = _cache_service.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {prefix}")
                return cached_value
            
            logger.debug(f"Cache miss: {prefix}")
            result = await func(*args, **kwargs)
            
            _cache_service.set(cache_key, result, ttl_seconds)
            
            return result
        
        return wrapper
    
    return decorator
