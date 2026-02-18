"""
Единая функция сохранения контекста с использованием Unit of Work.
"""

import logging
from typing import Optional, Any
from app.core.context import Context
from app.bot.telegram_bot.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


def save_context_safe(context: Context, user_id: str, db_session: Optional[Any] = None) -> None:
    """
    Безопасно сохранить контекст с проверкой user_id.
    Использует Unit of Work для атомарности.
    
    Args:
        context: Контекст для сохранения
        user_id: ID пользователя
        db_session: Сессия БД (опционально)
    """
    from app.bot.telegram_bot.utils import ensure_context_user_id
    
    ensure_context_user_id(context, user_id)
    
    with UnitOfWork(db_session=db_session) as uow:
        uow.register_context(context, user_id)
        uow.commit()
