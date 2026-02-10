"""
Репозиторий для хранения контекста пользователей.
Поддерживает персистентное хранение для масштабируемости.
"""

import logging
import json
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.core.context import Context

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


class ContextRepository:
    """
    Репозиторий для управления контекстом пользователей.
    Поддерживает кэширование в памяти и персистентное хранение в БД.
    """
    
    def __init__(self, db_session: Optional[Session] = None, cache_ttl_minutes: int = 60):
        """
        Инициализация репозитория.
        
        Args:
            db_session: SQLAlchemy сессия для БД (опционально)
            cache_ttl_minutes: Время жизни кэша в памяти (минуты)
        """
        self.db_session = db_session
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        
        # Кэш в памяти (для быстрого доступа)
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
    
    def get_context(self, user_id: str, session_id: Optional[str] = None) -> Optional[Context]:
        """
        Получить контекст пользователя.
        
        Args:
            user_id: ID пользователя
            session_id: ID сессии (опционально)
            
        Returns:
            Context или None если не найден
        """
        # Используем только user_id для ключа (не session_id), чтобы контекст сохранялся между сообщениями
        cache_key = f"{user_id}"
        
        # Проверяем кэш в памяти
        if cache_key in self._memory_cache:
            cache_time = self._cache_timestamps.get(cache_key)
            if cache_time and datetime.now() - cache_time < self.cache_ttl:
                try:
                    return Context.from_dict(self._memory_cache[cache_key])
                except Exception as e:
                    logger.warning(f"Failed to restore context from cache: {e}")
        
        # Загружаем из БД если доступна
        if self.db_session:
            try:
                context_data = self._load_from_db(user_id, session_id)
                if context_data:
                    context = Context.from_dict(context_data)
                    # Обновляем кэш
                    self._memory_cache[cache_key] = context_data
                    self._cache_timestamps[cache_key] = datetime.now()
                    return context
            except Exception as e:
                logger.error(f"Failed to load context from DB: {e}", exc_info=True)
        
        return None
    
    def save_context(self, context: Context) -> bool:
        """
        Сохранить контекст пользователя.
        
        Args:
            context: Контекст для сохранения
            
        Returns:
            True если успешно сохранено
        """
        if not context.user_id:
            logger.warning("Cannot save context without user_id")
            return False
        
        # Используем только user_id для ключа (не session_id), чтобы контекст сохранялся между сообщениями
        cache_key = f"{context.user_id}"
        context_dict = context.to_dict()
        
        # Сохраняем в кэш
        self._memory_cache[cache_key] = context_dict
        self._cache_timestamps[cache_key] = datetime.now()
        
        # Сохраняем в БД асинхронно (если доступна)
        if self.db_session:
            try:
                self._save_to_db(context)
            except Exception as e:
                logger.error(f"Failed to save context to DB: {e}", exc_info=True)
                return False
        
        return True
    
    def delete_context(self, user_id: str, session_id: Optional[str] = None) -> bool:
        """Удалить контекст пользователя."""
        # Используем только user_id для ключа (не session_id), чтобы контекст сохранялся между сообщениями
        cache_key = f"{user_id}"
        
        # Удаляем из кэша
        self._memory_cache.pop(cache_key, None)
        self._cache_timestamps.pop(cache_key, None)
        
        # Удаляем из БД
        if self.db_session:
            try:
                self._delete_from_db(user_id, session_id)
            except Exception as e:
                logger.error(f"Failed to delete context from DB: {e}", exc_info=True)
                return False
        
        return True
    
    def clear_expired_cache(self) -> int:
        """Очистить истекший кэш."""
        now = datetime.now()
        expired_keys = [
            key for key, timestamp in self._cache_timestamps.items()
            if now - timestamp >= self.cache_ttl
        ]
        
        for key in expired_keys:
            self._memory_cache.pop(key, None)
            self._cache_timestamps.pop(key, None)
        
        return len(expired_keys)
    
    def _load_from_db(self, user_id: str, session_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """Загрузить контекст из БД."""
        # TODO: Реализовать загрузку из БД когда будет таблица для контекста
        # Пока используем full_context_json из UserDecision
        try:
            from app.storage.models import UserDecision
            
            query = self.db_session.query(UserDecision).filter_by(
                user_id=user_id
            ).order_by(UserDecision.timestamp.desc()).first()
            
            if query and query.full_context_json:
                return json.loads(query.full_context_json)
        except Exception as e:
            logger.debug(f"No context found in DB: {e}")
        
        return None
    
    def _save_to_db(self, context: Context) -> None:
        """Сохранить контекст в БД."""
        # TODO: Реализовать сохранение в отдельную таблицу для контекста
        # Пока сохраняем в full_context_json при сохранении решения
        pass
    
    def _delete_from_db(self, user_id: str, session_id: Optional[str]) -> None:
        """Удалить контекст из БД."""
        # TODO: Реализовать удаление из БД
        pass
