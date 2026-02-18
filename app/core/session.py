"""
Session - управление сессией пользователя.
Хранит текущий контекст и очищается при приветствии/отмене.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class Session:
    """
    Сессия пользователя.
    Хранит текущий контекст работы.
    """
    
    def __init__(self, user_id: str):
        """
        Инициализация сессии.
        
        Args:
            user_id: ID пользователя
        """
        self.user_id = user_id
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        
        # Текущий контекст
        self.current_standard: Optional[str] = None
        self.current_material: Optional[str] = None
        self.current_machine: Optional[str] = None
        self.current_operation: Optional[str] = None
        
        # Рассчитанные значения
        self.calculated_values: Dict[str, Any] = {}
        
        # История операций
        self.history: list = []
    
    def clear(self) -> None:
        """
        Очистить сессию.
        Вызывается при приветствии или отмене.
        """
        logger.debug(f"Clearing session for user {self.user_id}")
        self.current_standard = None
        self.current_material = None
        self.current_machine = None
        self.current_operation = None
        self.calculated_values = {}
        # История не очищаем - она нужна для анализа
    
    def update_activity(self) -> None:
        """Обновить время последней активности."""
        self.last_activity = datetime.now()
    
    def set_standard(self, standard: str) -> None:
        """Установить текущий стандарт."""
        self.current_standard = standard
        self.update_activity()
        logger.debug(f"Session {self.user_id}: standard set to {standard}")
    
    def set_material(self, material: str) -> None:
        """Установить текущий материал."""
        self.current_material = material
        self.update_activity()
    
    def set_machine(self, machine: str) -> None:
        """Установить текущий станок."""
        self.current_machine = machine
        self.update_activity()
    
    def set_operation(self, operation: str) -> None:
        """Установить текущую операцию."""
        self.current_operation = operation
        self.update_activity()
    
    def add_calculated_value(self, key: str, value: Any) -> None:
        """Добавить рассчитанное значение."""
        self.calculated_values[key] = value
        self.update_activity()
    
    def add_to_history(self, event: str, data: Dict[str, Any]) -> None:
        """Добавить событие в историю."""
        self.history.append({
            'timestamp': datetime.now().isoformat(),
            'event': event,
            'data': data
        })
        self.update_activity()
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать сессию в словарь."""
        return {
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'current_standard': self.current_standard,
            'current_material': self.current_material,
            'current_machine': self.current_machine,
            'current_operation': self.current_operation,
            'calculated_values': self.calculated_values,
            'history_count': len(self.history)
        }
    
    def has_context(self) -> bool:
        """Проверить, есть ли контекст в сессии."""
        return any([
            self.current_standard,
            self.current_material,
            self.current_machine,
            self.current_operation
        ])
