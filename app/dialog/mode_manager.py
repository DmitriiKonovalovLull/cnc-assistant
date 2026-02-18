"""
Mode Manager - управление режимами работы бота.
Разделяет STANDARD_MODE, CNC_CALC_MODE, SIMPLE_CALCULATOR_MODE.
"""

import logging
from typing import Dict

from app.dialog.constants import DialogMode

logger = logging.getLogger(__name__)


class ModeManager:
    """
    Менеджер режимов работы бота.
    
    Режимы хранятся отдельно от состояний (State).
    Режим определяет общую логику работы, состояние - конкретный шаг в диалоге.
    """
    
    def __init__(self):
        """Инициализация менеджера режимов."""
        # Хранилище режимов: user_id -> DialogMode
        self._modes: Dict[int, DialogMode] = {}
    
    def get(self, user_id: int) -> DialogMode:
        """
        Получить текущий режим пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Текущий режим (по умолчанию IDLE)
        """
        return self._modes.get(user_id, DialogMode.IDLE)
    
    def set(self, user_id: int, mode: DialogMode, reason: str = "manual") -> None:
        """
        Установить режим пользователя.
        
        Args:
            user_id: ID пользователя
            mode: Новый режим
            reason: Причина изменения
        """
        previous_mode = self._modes.get(user_id, DialogMode.IDLE)
        self._modes[user_id] = mode
        
        logger.info(
            f"Mode changed: user_id={user_id}, "
            f"{previous_mode.value} -> {mode.value}, reason={reason}"
        )
    
    def reset(self, user_id: int, reason: str = "reset_command") -> None:
        """
        Сбросить режим в IDLE.
        
        Args:
            user_id: ID пользователя
            reason: Причина сброса
        """
        self.set(user_id, DialogMode.IDLE, reason)
    
    def clear(self, user_id: int) -> None:
        """
        Удалить режим пользователя.
        
        Args:
            user_id: ID пользователя
        """
        if user_id in self._modes:
            del self._modes[user_id]
            logger.info(f"Mode cleared for user_id={user_id}")
