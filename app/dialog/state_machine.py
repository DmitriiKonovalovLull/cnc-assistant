"""
State Machine для управления состояниями диалога.
Строгий контроль переходов и защита от некорректных изменений состояния.
"""

import logging
from typing import Optional, Dict
from datetime import datetime

from app.dialog.constants import DialogState, ALLOWED_TRANSITIONS

logger = logging.getLogger(__name__)


class StateMachine:
    """
    State Machine для управления состояниями пользователей.
    
    Правила:
    - Только допустимые переходы разрешены
    - Все переходы логируются
    - Нельзя менять state напрямую, только через transition()
    """
    
    def __init__(self):
        """
        Инициализация State Machine.
        """
        # Хранилище состояний: user_id -> DialogState
        self._states: Dict[int, DialogState] = {}
        
        # История переходов: user_id -> [(timestamp, from_state, to_state, reason)]
        self._history: Dict[int, list] = {}
    
    def get(self, user_id: int) -> DialogState:
        """
        Получить текущее состояние пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Текущее состояние (по умолчанию IDLE)
        """
        return self._states.get(user_id, DialogState.IDLE)
    
    def set(self, user_id: int, state: DialogState, reason: str = "manual") -> bool:
        """
        Установить состояние (без проверки переходов).
        Используется только для начальной установки или сброса.
        
        Args:
            user_id: ID пользователя
            state: Новое состояние
            reason: Причина изменения
            
        Returns:
            True если успешно
        """
        previous_state = self._states.get(user_id, DialogState.IDLE)
        
        self._states[user_id] = state
        
        # Логируем переход
        self._log_transition(user_id, previous_state, state, reason)
        
        logger.info(
            f"State SET: user_id={user_id}, "
            f"{previous_state.value} -> {state.value}, reason={reason}"
        )
        
        return True
    
    def transition(self, user_id: int, new_state: DialogState, reason: str = "transition") -> bool:
        """
        Выполнить переход состояния с проверкой допустимости.
        
        Args:
            user_id: ID пользователя
            new_state: Новое состояние
            reason: Причина перехода
            
        Returns:
            True если переход выполнен, False если недопустим
        """
        current_state = self.get(user_id)
        
        # Проверяем допустимость перехода
        if not self._is_transition_allowed(current_state, new_state):
            logger.warning(
                f"Invalid transition blocked: user_id={user_id}, "
                f"{current_state.value} -> {new_state.value}, reason={reason}"
            )
            return False
        
        # Выполняем переход
        self._states[user_id] = new_state
        
        # Логируем переход
        self._log_transition(user_id, current_state, new_state, reason)
        
        logger.info(
            f"State TRANSITION: user_id={user_id}, "
            f"{current_state.value} -> {new_state.value}, reason={reason}"
        )
        
        return True
    
    def reset(self, user_id: int, reason: str = "reset_command") -> bool:
        """
        Сбросить состояние в IDLE.
        
        Args:
            user_id: ID пользователя
            reason: Причина сброса
            
        Returns:
            True если успешно
        """
        return self.set(user_id, DialogState.IDLE, reason)
    
    def _is_transition_allowed(self, from_state: DialogState, to_state: DialogState) -> bool:
        """
        Проверить допустимость перехода.
        
        Args:
            from_state: Текущее состояние
            to_state: Целевое состояние
            
        Returns:
            True если переход допустим
        """
        # Всегда можно остаться в том же состоянии
        if from_state == to_state:
            return True
        
        # Проверяем список допустимых переходов
        allowed = ALLOWED_TRANSITIONS.get(from_state, [])
        return to_state in allowed
    
    def _log_transition(self, user_id: int, from_state: DialogState, 
                       to_state: DialogState, reason: str) -> None:
        """
        Логировать переход состояния.
        
        Args:
            user_id: ID пользователя
            from_state: Предыдущее состояние
            to_state: Новое состояние
            reason: Причина перехода
        """
        if user_id not in self._history:
            self._history[user_id] = []
        
        self._history[user_id].append({
            'timestamp': datetime.utcnow().isoformat(),
            'from_state': from_state.value,
            'to_state': to_state.value,
            'reason': reason,
        })
        
        # Ограничиваем историю последними 100 переходами
        if len(self._history[user_id]) > 100:
            self._history[user_id] = self._history[user_id][-100:]
    
    def get_history(self, user_id: int, limit: int = 10) -> list:
        """
        Получить историю переходов пользователя.
        
        Args:
            user_id: ID пользователя
            limit: Максимум записей
            
        Returns:
            Список переходов
        """
        history = self._history.get(user_id, [])
        return history[-limit:]
    
    def clear_history(self, user_id: int) -> None:
        """
        Очистить историю пользователя.
        
        Args:
            user_id: ID пользователя
        """
        if user_id in self._history:
            del self._history[user_id]
