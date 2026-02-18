"""
CacheManager - кэширование стандартов в памяти (Redis опционально).
Ускоряет работу бота: Redis → 5-20 мс вместо Internet → 1-5 сек.
"""

import logging
import json
from typing import Optional, Dict, Any
from datetime import timedelta

logger = logging.getLogger(__name__)

# TTL кэша (24 часа)
CACHE_TTL_HOURS = 24


class CacheManager:
    """
    Менеджер кэширования стандартов.
    Поддерживает Redis (если доступен) или in-memory кэш.
    """
    
    def __init__(self, redis_client=None):
        """
        Инициализация менеджера кэша.
        
        Args:
            redis_client: Redis клиент (опционально)
        """
        self.redis = redis_client
        self.memory_cache = {}  # Fallback in-memory кэш
    
    def _make_key(self, family: str, code: str) -> str:
        """
        Создать ключ кэша.
        
        Args:
            family: Семейство стандарта
            code: Код стандарта
            
        Returns:
            Ключ кэша
        """
        return f"standard:{family}:{code}"
    
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
        if self.redis:
            try:
                cached = self.redis.get(key)
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
        if self.redis:
            try:
                self.redis.setex(
                    key,
                    timedelta(hours=CACHE_TTL_HOURS),
                    json.dumps(data, ensure_ascii=False)
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
        if self.redis:
            try:
                self.redis.delete(key)
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
        if self.redis:
            try:
                # Удаляем все ключи стандартов
                keys = self.redis.keys("standard:*")
                if keys:
                    self.redis.delete(*keys)
            except Exception:
                pass
        
        # Очищаем память
        self.memory_cache.clear()
        
        return True
