"""
Rate Limiter - защита от spam и злоупотреблений.
Ограничивает количество запросов от пользователя.
"""

import asyncio
import logging
import time
from typing import Dict, Optional
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate Limiter для защиты от spam.
    
    Ограничения:
    - Максимум N запросов в окне времени
    - Sliding window алгоритм
    """
    
    def __init__(
        self,
        max_requests: int = 30,
        window_seconds: int = 60,
        block_duration: int = 300  # 5 минут блокировки
    ):
        """
        Инициализация rate limiter.
        
        Args:
            max_requests: Максимум запросов в окне
            window_seconds: Размер окна в секундах
            block_duration: Длительность блокировки в секундах
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.block_duration = block_duration
        
        # История запросов: user_id -> [timestamps]
        self._request_history: Dict[int, list] = defaultdict(list)
        
        # Блокированные пользователи: user_id -> unblock_timestamp
        self._blocked_users: Dict[int, float] = {}
        
        # Блокировки для thread-safety
        self._locks: Dict[int, asyncio.Lock] = defaultdict(lambda: asyncio.Lock())
    
    async def check_rate_limit(self, user_id: int) -> tuple[bool, Optional[str]]:
        """
        Проверить rate limit для пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            (allowed, reason) - разрешен ли запрос и причина если нет
        """
        async with self._locks[user_id]:
            current_time = time.time()
            
            # Проверяем блокировку
            if user_id in self._blocked_users:
                unblock_time = self._blocked_users[user_id]
                if current_time < unblock_time:
                    remaining = int(unblock_time - current_time)
                    return False, f"Rate limit exceeded. Blocked for {remaining} seconds."
                else:
                    # Блокировка истекла
                    del self._blocked_users[user_id]
            
            # Очищаем старые запросы (outside window)
            window_start = current_time - self.window_seconds
            self._request_history[user_id] = [
                ts for ts in self._request_history[user_id]
                if ts > window_start
            ]
            
            # Проверяем лимит
            request_count = len(self._request_history[user_id])
            
            if request_count >= self.max_requests:
                # Блокируем пользователя
                self._blocked_users[user_id] = current_time + self.block_duration
                logger.warning(
                    f"Rate limit exceeded for user_id={user_id}: "
                    f"{request_count} requests in {self.window_seconds}s"
                )
                return False, f"Rate limit exceeded. Maximum {self.max_requests} requests per {self.window_seconds} seconds."
            
            # Регистрируем запрос
            self._request_history[user_id].append(current_time)
            
            return True, None
    
    async def reset_user(self, user_id: int) -> None:
        """
        Сбросить историю пользователя.
        
        Args:
            user_id: ID пользователя
        """
        async with self._locks[user_id]:
            if user_id in self._request_history:
                del self._request_history[user_id]
            if user_id in self._blocked_users:
                del self._blocked_users[user_id]
            logger.info(f"Rate limit reset for user_id={user_id}")
    
    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Получить статистику пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Словарь со статистикой
        """
        current_time = time.time()
        window_start = current_time - self.window_seconds
        
        requests = [
            ts for ts in self._request_history.get(user_id, [])
            if ts > window_start
        ]
        
        is_blocked = user_id in self._blocked_users
        unblock_time = self._blocked_users.get(user_id, 0)
        
        return {
            'requests_in_window': len(requests),
            'max_requests': self.max_requests,
            'window_seconds': self.window_seconds,
            'is_blocked': is_blocked,
            'unblock_at': datetime.fromtimestamp(unblock_time).isoformat() if is_blocked else None,
        }
