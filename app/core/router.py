"""
Router - маршрутизация сообщений по интентам.
Intent → Handler → Response
"""

import logging
from typing import Dict, Any, Optional

from app.core.intent_system import Intent, IntentDetector
from app.core.session import Session

logger = logging.getLogger(__name__)


class MessageRouter:
    """
    Маршрутизатор сообщений.
    Определяет намерение и направляет в соответствующий обработчик.
    """
    
    def __init__(self):
        """Инициализация роутера."""
        self.intent_detector = IntentDetector()
        self.handlers = {}
        self._register_handlers()
    
    def _register_handlers(self):
        """Зарегистрировать обработчики для каждого интента."""
        # Импортируем обработчики (будут созданы отдельно)
        # Пока используем заглушки
        self.handlers = {
            Intent.GREETING: self._handle_greeting,
            Intent.HELP: self._handle_help,
            Intent.STANDARD_LOOKUP: self._handle_standard_lookup,
            Intent.PROCESS_CALCULATION: self._handle_process_calculation,
            Intent.FIT_CALCULATION: self._handle_fit_calculation,
            Intent.THREAD_CALCULATION: self._handle_thread_calculation,
            Intent.SURFACE_CALCULATION: self._handle_surface_calculation,
            Intent.POWER_CHECK: self._handle_power_check,
            Intent.DOWNLOAD_STANDARDS: self._handle_download_standards,
            Intent.STANDARD_INTEGRITY_CHECK: self._handle_integrity_check,
            Intent.ADMIN_CHECK: self._handle_admin_check,
            Intent.UNKNOWN: self._handle_unknown,
        }
    
    def route(self, message_text: str, session: Session, **kwargs) -> Dict[str, Any]:
        """
        Маршрутизировать сообщение.
        
        Args:
            message_text: Текст сообщения
            session: Сессия пользователя
            **kwargs: Дополнительные параметры (user_id, image_data и т.д.)
            
        Returns:
            Словарь с результатом обработки
        """
        # Определяем намерение
        intent_metadata = self.intent_detector.get_intent_metadata(message_text)
        intent = intent_metadata['intent']
        
        logger.info(f"Routing message: intent={intent.value}, text={message_text[:50]}")
        
        # Очищаем сессию при приветствии или отмене
        if intent == Intent.GREETING:
            session.clear()
        
        # Получаем обработчик
        handler = self.handlers.get(intent, self._handle_unknown)
        
        # Вызываем обработчик
        try:
            result = handler(message_text, session, intent_metadata, **kwargs)
            result['intent'] = intent.value
            return result
        except Exception as e:
            logger.error(f"Error in handler for {intent.value}: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'Ошибка обработки: {str(e)}',
                'intent': intent.value
            }
    
    # ========================================================================
    # ОБРАБОТЧИКИ
    # ========================================================================
    
    def _handle_greeting(self, text: str, session: Session, metadata: Dict, **kwargs) -> Dict[str, Any]:
        """Обработка приветствия."""
        return {
            'success': True,
            'message': (
                '👋 <b>Инженерная система CNC готова.</b>\n\n'
                'Выберите:\n'
                '1. Расчёт режимов\n'
                '2. Резьба\n'
                '3. Посадки\n'
                '4. Стандарты\n'
                '5. Проверка базы нормалей'
            ),
            'session': session.to_dict()
        }
    
    def _handle_help(self, text: str, session: Session, metadata: Dict, **kwargs) -> Dict[str, Any]:
        """Обработка запроса помощи."""
        return {
            'success': True,
            'message': (
                '📚 <b>Возможности системы:</b>\n\n'
                '• Расчёт режимов резания\n'
                '• Работа с резьбами (M, шаг, допуск)\n'
                '• Расчёт посадок и допусков\n'
                '• Работа со стандартами (ГОСТ, ОСТ, ISO, DIN)\n'
                '• Проверка мощности резания\n'
                '• Управление базой стандартов\n\n'
                'Просто опишите задачу текстом!'
            ),
            'session': session.to_dict()
        }
    
    def _handle_standard_lookup(self, text: str, session: Session, metadata: Dict, **kwargs) -> Dict[str, Any]:
        """Обработка поиска стандарта."""
        # Импортируем обработчик стандартов
        from app.handlers.standard_handler import handle_standard_lookup
        return handle_standard_lookup(text, session, metadata, **kwargs)
    
    def _handle_process_calculation(self, text: str, session: Session, metadata: Dict, **kwargs) -> Dict[str, Any]:
        """Обработка расчёта режимов обработки."""
        from app.handlers.process_handler import handle_process_calculation
        return handle_process_calculation(text, session, metadata, **kwargs)
    
    def _handle_fit_calculation(self, text: str, session: Session, metadata: Dict, **kwargs) -> Dict[str, Any]:
        """Обработка расчёта посадок."""
        from app.handlers.fit_handler import handle_fit_calculation
        return handle_fit_calculation(text, session, metadata, **kwargs)
    
    def _handle_thread_calculation(self, text: str, session: Session, metadata: Dict, **kwargs) -> Dict[str, Any]:
        """Обработка расчёта резьбы."""
        from app.handlers.thread_handler import handle_thread_calculation
        return handle_thread_calculation(text, session, metadata, **kwargs)
    
    def _handle_surface_calculation(self, text: str, session: Session, metadata: Dict, **kwargs) -> Dict[str, Any]:
        """Обработка расчёта шероховатости."""
        from app.handlers.surface_handler import handle_surface_calculation
        return handle_surface_calculation(text, session, metadata, **kwargs)
    
    def _handle_power_check(self, text: str, session: Session, metadata: Dict, **kwargs) -> Dict[str, Any]:
        """Обработка проверки мощности."""
        from app.handlers.power_handler import handle_power_check
        return handle_power_check(text, session, metadata, **kwargs)
    
    def _handle_download_standards(self, text: str, session: Session, metadata: Dict, **kwargs) -> Dict[str, Any]:
        """Обработка загрузки стандартов."""
        from app.handlers.standards_handler import handle_download_standards
        return handle_download_standards(text, session, metadata, **kwargs)
    
    def _handle_integrity_check(self, text: str, session: Session, metadata: Dict, **kwargs) -> Dict[str, Any]:
        """Обработка проверки целостности базы стандартов."""
        from app.handlers.standards_handler import handle_integrity_check
        return handle_integrity_check(text, session, metadata, **kwargs)
    
    def _handle_admin_check(self, text: str, session: Session, metadata: Dict, **kwargs) -> Dict[str, Any]:
        """Обработка админских команд."""
        return {
            'success': False,
            'message': 'Админские функции в разработке',
            'session': session.to_dict()
        }
    
    def _handle_unknown(self, text: str, session: Session, metadata: Dict, **kwargs) -> Dict[str, Any]:
        """Обработка неизвестного запроса."""
        return {
            'success': False,
            'message': (
                '❓ Не понял запрос.\n\n'
                'Попробуйте:\n'
                '• "расчёт режимов для стали"\n'
                '• "ГОСТ 7798-30"\n'
                '• "проверка базы"\n'
                '• "помощь"'
            ),
            'session': session.to_dict()
        }
