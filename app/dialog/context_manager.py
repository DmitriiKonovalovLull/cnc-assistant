"""
Context Manager - управление контекстом диалога.
Хранит данные пользователя отдельно от состояния.
"""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class DialogContext:
    """
    Контекст диалога пользователя.
    Хранит данные для расчетов и работы со стандартами.
    """
    # Материал
    material: Optional[str] = None
    
    # Размеры
    diameter_from: Optional[float] = None
    diameter_to: Optional[float] = None
    length: Optional[float] = None
    
    # Операция
    operation: Optional[str] = None
    
    # Количество
    quantity: Optional[int] = None
    
    # Стандарт
    standard_code: Optional[str] = None
    standard_family: Optional[str] = None
    
    # Дополнительные данные
    extra_data: Dict[str, Any] = field(default_factory=dict)
    
    def clear(self) -> None:
        """Очистить весь контекст."""
        self.material = None
        self.diameter_from = None
        self.diameter_to = None
        self.length = None
        self.operation = None
        self.quantity = None
        self.standard_code = None
        self.standard_family = None
        self.extra_data.clear()
    
    def clear_calculation(self) -> None:
        """Очистить только данные расчета (оставить стандарт если есть)."""
        self.material = None
        self.diameter_from = None
        self.diameter_to = None
        self.length = None
        self.operation = None
        self.quantity = None
    
    def clear_standard(self) -> None:
        """Очистить только данные стандарта."""
        self.standard_code = None
        self.standard_family = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать контекст в словарь."""
        return asdict(self)
    
    def is_calculation_ready(self) -> bool:
        """
        Проверить готовность к расчету.
        
        Returns:
            True если есть все необходимые данные
        """
        return (
            self.material is not None and
            self.operation is not None and
            (self.diameter_from is not None or self.diameter_to is not None)
        )


class ContextManager:
    """
    Менеджер контекстов пользователей.
    Хранит и управляет контекстами диалогов.
    """
    
    def __init__(self):
        """Инициализация менеджера контекстов."""
        # Хранилище контекстов: user_id -> DialogContext
        self._contexts: Dict[int, DialogContext] = {}
    
    def get(self, user_id: int) -> DialogContext:
        """
        Получить контекст пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Контекст пользователя (создается если не существует)
        """
        if user_id not in self._contexts:
            self._contexts[user_id] = DialogContext()
        
        return self._contexts[user_id]
    
    def clear(self, user_id: int) -> None:
        """
        Очистить контекст пользователя.
        
        Args:
            user_id: ID пользователя
        """
        if user_id in self._contexts:
            self._contexts[user_id].clear()
            logger.info(f"Context cleared for user_id={user_id}")
    
    def clear_all(self, user_id: int) -> None:
        """
        Полная очистка контекста пользователя (включая удаление объекта).
        
        Args:
            user_id: ID пользователя
        """
        if user_id in self._contexts:
            del self._contexts[user_id]
            logger.info(f"Context fully cleared (deleted) for user_id={user_id}")
    
    def clear_calculation(self, user_id: int) -> None:
        """
        Очистить только данные расчета.
        
        Args:
            user_id: ID пользователя
        """
        if user_id in self._contexts:
            self._contexts[user_id].clear_calculation()
            logger.info(f"Calculation context cleared for user_id={user_id}")
    
    def clear_standard(self, user_id: int) -> None:
        """
        Очистить только данные стандарта.
        
        Args:
            user_id: ID пользователя
        """
        if user_id in self._contexts:
            self._contexts[user_id].clear_standard()
            logger.info(f"Standard context cleared for user_id={user_id}")
    
    def update(self, user_id: int, **kwargs) -> None:
        """
        Обновить контекст пользователя.
        
        Args:
            user_id: ID пользователя
            **kwargs: Поля для обновления
        """
        context = self.get(user_id)
        
        for key, value in kwargs.items():
            if hasattr(context, key):
                setattr(context, key, value)
                logger.debug(f"Updated context[{key}]={value} for user_id={user_id}")
            else:
                # Сохраняем в extra_data
                context.extra_data[key] = value
    
    def remove(self, user_id: int) -> None:
        """
        Удалить контекст пользователя.
        
        Args:
            user_id: ID пользователя
        """
        if user_id in self._contexts:
            del self._contexts[user_id]
            logger.info(f"Context removed for user_id={user_id}")
