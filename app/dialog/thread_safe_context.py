"""
Thread-safe Context Manager для защиты от race conditions.
Использует asyncio.Lock для каждого пользователя.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from collections import defaultdict

from app.dialog.context_manager import DialogContext, ContextManager

logger = logging.getLogger(__name__)


class ThreadSafeContextManager(ContextManager):
    """
    Thread-safe версия ContextManager.
    Защищает от race conditions при одновременном доступе.
    """
    
    def __init__(self):
        """Инициализация thread-safe менеджера."""
        super().__init__()
        # Блокировки для каждого пользователя
        self._locks: Dict[int, asyncio.Lock] = defaultdict(lambda: asyncio.Lock())
    
    async def get_async(self, user_id: int) -> DialogContext:
        """
        Получить контекст пользователя (async, thread-safe).
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Контекст пользователя
        """
        async with self._locks[user_id]:
            return self.get(user_id)
    
    async def update_async(self, user_id: int, **kwargs) -> None:
        """
        Обновить контекст пользователя (async, thread-safe).
        
        Args:
            user_id: ID пользователя
            **kwargs: Поля для обновления
        """
        async with self._locks[user_id]:
            self.update(user_id, **kwargs)
    
    async def clear_async(self, user_id: int) -> None:
        """
        Очистить контекст пользователя (async, thread-safe).
        
        Args:
            user_id: ID пользователя
        """
        async with self._locks[user_id]:
            self.clear(user_id)
    
    async def clear_all_async(self, user_id: int) -> None:
        """
        Полная очистка контекста (async, thread-safe).
        
        Args:
            user_id: ID пользователя
        """
        async with self._locks[user_id]:
            self.clear_all(user_id)
    
    def cleanup_lock(self, user_id: int) -> None:
        """
        Удалить блокировку пользователя (после удаления контекста).
        
        Args:
            user_id: ID пользователя
        """
        if user_id in self._locks:
            del self._locks[user_id]
            logger.debug(f"Lock cleaned up for user_id={user_id}")
