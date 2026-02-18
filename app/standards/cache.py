"""
Redis Cache для стандартов.
Ускоряет работу: Cache → 1-5 мс вместо Database → 5-20 мс.
"""

import logging
import json
from typing import Optional, Dict, Any
from datetime import timedelta

from app.core.config import settings

logger = logging.getLogger(__name__)

# Пробуем импортировать Redis
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available, using in-memory cache")


class CacheManager:
    """
    Менеджер кэширования стандартов.
    Поддерживает Redis (если доступен) или in-memory кэш.
    """
    
    def __init__(self):
        """Инициализация менеджера кэша."""
        self.redis_client = None
        self.memory_cache = {}  # Fallback in-memory кэш
        
        if settings.REDIS_ENABLED and REDIS_AVAILABLE:
            try:
                self.redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True
                )
                # Проверяем подключение
                self.redis_client.ping()
                logger.info("Redis cache connected")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}, using memory cache")
                self.redis_client = None
    
    def _make_key(self, family: str, code: str) -> str:
        """
        Создать ключ кэша.
        
        Args:
            family: Семейство стандарта
            code: Код стандарта
            
        Returns:
            Ключ кэша
        """
        return f"standard:{family.upper()}:{code}"
    
    def get(self, family: str, code: str) -> Optional[Dict[str, Any]]:
        """
        Получить стандарт из кэша.
        
        Args:
            family: Семейство стандарта
            code: Код стандарта
            
        Returns:
            Данные стандарта или None
        """
        key = self._make_key(family, code)
        
        # Пробуем Redis
        if self.redis_client:
            try:
                cached = self.redis_client.get(key)
                if cached:
                    logger.debug(f"Cache HIT (Redis): {key}")
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"Redis error: {e}, falling back to memory cache")
        
        # Fallback: in-memory кэш
        if key in self.memory_cache:
            logger.debug(f"Cache HIT (memory): {key}")
            return self.memory_cache[key]
        
        logger.debug(f"Cache MISS: {key}")
        return None
    
    def set(self, family: str, code: str, data: Dict[str, Any]) -> bool:
        """
        Сохранить стандарт в кэш.
        
        Args:
            family: Семейство стандарта
            code: Код стандарта
            data: Данные стандарта
            
        Returns:
            True если успешно
        """
        key = self._make_key(family, code)
        
        # Пробуем Redis
        if self.redis_client:
            try:
                self.redis_client.setex(
                    key,
                    timedelta(hours=settings.CACHE_TTL_HOURS),
                    json.dumps(data, ensure_ascii=False, default=str)
                )
                logger.debug(f"Cached in Redis: {key}")
                return True
            except Exception as e:
                logger.warning(f"Redis error: {e}, falling back to memory cache")
        
        # Fallback: in-memory кэш
        self.memory_cache[key] = data
        logger.debug(f"Cached in memory: {key}")
        return True
    
    def delete(self, family: str, code: str) -> bool:
        """
        Удалить стандарт из кэша.
        
        Args:
            family: Семейство стандарта
            code: Код стандарта
            
        Returns:
            True если успешно
        """
        key = self._make_key(family, code)
        
        # Удаляем из Redis
        if self.redis_client:
            try:
                self.redis_client.delete(key)
            except Exception:
                pass
        
        # Удаляем из памяти
        self.memory_cache.pop(key, None)
        
        return True
    
    def clear(self) -> bool:
        """
        Очистить весь кэш.
        
        Returns:
            True если успешно
        """
        # Очищаем Redis
        if self.redis_client:
            try:
                keys = self.redis_client.keys("standard:*")
                if keys:
                    self.redis_client.delete(*keys)
            except Exception:
                pass
        
        # Очищаем память
        self.memory_cache.clear()
        
        return True
