"""
Unit of Work паттерн для атомарных операций.
"""

import logging
from typing import List, Tuple, Optional, Any
from app.core.context import Context

logger = logging.getLogger(__name__)


class UnitOfWork:
    """Единица работы для атомарных операций."""
    
    def __init__(self, db_session: Optional[Any] = None):
        """
        Инициализация Unit of Work.
        
        Args:
            db_session: Сессия базы данных (опционально)
        """
        self.db_session = db_session
        self.contexts_to_save: List[Tuple[Context, str]] = []
        self._committed = False
        self._rolled_back = False
    
    def register_context(self, context: Context, user_id: str):
        """
        Зарегистрировать контекст для сохранения.
        
        Args:
            context: Контекст для сохранения
            user_id: ID пользователя
        """
        if self._committed or self._rolled_back:
            raise RuntimeError("UnitOfWork уже закоммичен или откачен")
        self.contexts_to_save.append((context, user_id))
    
    def commit(self):
        """Атомарно сохранить все изменения."""
        if self._committed:
            logger.warning("UnitOfWork уже закоммичен")
            return
        
        if self._rolled_back:
            raise RuntimeError("Нельзя закоммитить после отката")
        
        try:
            # Импортируем динамически чтобы избежать циклических зависимостей
            from app.bot.context_manager import context_manager, file_storage, user_contexts
            from app.bot.telegram_bot.main import context_repository
            from app.bot.telegram_bot.utils import ensure_context_user_id
            
            # Сохраняем все контексты
            for context, user_id in self.contexts_to_save:
                ensure_context_user_id(context, user_id)
                
                # Используем context_manager если доступен
                if context_manager:
                    context_manager.set(user_id, context)
                
                # Используем файловое хранилище если доступно
                if file_storage:
                    file_storage.set(user_id, context)
                
                # Используем репозиторий если доступен
                if context_repository:
                    context_repository.save_context(context)
                else:
                    # Fallback на старый способ (в памяти)
                    user_contexts[user_id] = context
            
            # Коммитим сессию БД если есть
            if self.db_session:
                self.db_session.commit()
            
            self._committed = True
            logger.debug(f"UnitOfWork committed: {len(self.contexts_to_save)} contexts saved")
        
        except Exception as e:
            logger.error(f"Error committing UnitOfWork: {e}", exc_info=True)
            self.rollback()
            raise
    
    def rollback(self):
        """Откатить изменения."""
        if self._rolled_back:
            return
        
        try:
            # Откатываем сессию БД если есть
            if self.db_session:
                self.db_session.rollback()
            
            self.contexts_to_save.clear()
            self._rolled_back = True
            logger.debug("UnitOfWork rolled back")
        
        except Exception as e:
            logger.error(f"Error rolling back UnitOfWork: {e}", exc_info=True)
    
    def __enter__(self):
        """Поддержка контекстного менеджера."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Автоматический коммит или откат при выходе из контекста."""
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
