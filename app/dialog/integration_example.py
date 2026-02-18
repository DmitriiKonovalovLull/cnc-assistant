"""
Пример интеграции нового MessageProcessor с существующим handler.py.

Этот файл показывает как интегрировать новую систему диалога
с существующим кодом без полной переписи handler.py.
"""

import logging
from typing import Dict, Any, Optional

from app.dialog import MessageProcessor, DialogState, Intent

logger = logging.getLogger(__name__)


class DialogIntegration:
    """
    Интеграция новой системы диалога с существующим handler.
    
    Использование:
    1. Создать экземпляр DialogIntegration в handler.py
    2. Вызывать process_message() перед старой логикой
    3. Если result['handled'] == True - использовать новый pipeline
    4. Если False - использовать старую логику как fallback
    """
    
    def __init__(self):
        """Инициализация интеграции."""
        self.processor = MessageProcessor()
        self.enabled = True  # Можно отключить для постепенного перехода
    
    def process_message(
        self, 
        user_id: int, 
        message: str,
        has_photo: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Обработать сообщение через новый pipeline.
        
        Args:
            user_id: ID пользователя
            message: Текст сообщения
            has_photo: Есть ли фото (для будущей интеграции)
            **kwargs: Дополнительные параметры
            
        Returns:
            Словарь с полями:
            - handled: bool - обработано ли новым pipeline
            - response: str - ответ пользователю
            - state: DialogState - новое состояние
            - intent: Intent - определенный интент
            - metadata: dict - дополнительная информация
            - use_old_handler: bool - использовать ли старый handler как fallback
        """
        if not self.enabled:
            return {
                'handled': False,
                'use_old_handler': True
            }
        
        # Если есть фото - пока используем старый handler
        if has_photo:
            return {
                'handled': False,
                'use_old_handler': True
            }
        
        try:
            # Обрабатываем через новый pipeline
            result = self.processor.process(user_id, message, **kwargs)
            
            # Определяем нужно ли использовать старый handler
            # Для некоторых интентов можно использовать старый handler для детальной обработки
            use_old_handler = False
            
            # Например, для CALCULATION_READY можно использовать старый расчетный движок
            if result['state'] == DialogState.CALCULATION_READY:
                use_old_handler = True
            
            return {
                'handled': True,
                'response': result['response'],
                'state': result['state'],
                'intent': result['intent'],
                'metadata': result.get('metadata', {}),
                'use_old_handler': use_old_handler
            }
        
        except Exception as e:
            logger.error(f"Error in new dialog pipeline: {e}", exc_info=True)
            # При ошибке используем старый handler
            return {
                'handled': False,
                'use_old_handler': True,
                'error': str(e)
            }
    
    def get_state(self, user_id: int) -> DialogState:
        """
        Получить текущее состояние пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Текущее состояние
        """
        return self.processor.state_machine.get(user_id)
    
    def get_context(self, user_id: int) -> Dict[str, Any]:
        """
        Получить контекст пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Контекст в виде словаря
        """
        context = self.processor.context_manager.get(user_id)
        return context.to_dict()


# Пример использования в handler.py:
"""
# В начале handler.py:
from app.dialog.integration_example import DialogIntegration

dialog_integration = DialogIntegration()

# В методе обработки сообщения:
async def _process_message_internal(self, user_text: str, user_id: int, ...):
    # Пробуем новый pipeline
    dialog_result = dialog_integration.process_message(
        user_id=user_id,
        message=user_text,
        has_photo=bool(image_data)
    )
    
    if dialog_result['handled']:
        # Используем новый pipeline
        if not dialog_result.get('use_old_handler', False):
            # Полностью новый pipeline
            return {
                'message': dialog_result['response'],
                'state': dialog_result['state'].value,
                'intent': dialog_result['intent'].value
            }
        else:
            # Новый pipeline определил интент/состояние, но используем старый handler для детальной обработки
            # Например, для расчетов используем старый движок
            # Продолжаем со старой логикой, но с обновленным состоянием
            pass
    
    # Fallback на старую логику
    # ... существующий код handler.py ...
"""
