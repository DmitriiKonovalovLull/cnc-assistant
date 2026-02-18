"""
Обработчики для работы со стандартами.
"""

import logging
from typing import Dict, Any

from app.core.session import Session

logger = logging.getLogger(__name__)


def handle_download_standards(text: str, session: Session, metadata: Dict, **kwargs) -> Dict[str, Any]:
    """
    Обработка запроса на загрузку стандартов.
    
    Args:
        text: Текст сообщения
        session: Сессия пользователя
        metadata: Метаданные интента
        **kwargs: Дополнительные параметры
        
    Returns:
        Словарь с результатом обработки
    """
    try:
        from standards.manager.standard_manager import StandardManager
        
        manager = StandardManager()
        result = manager.update_all()
        
        # Формируем сообщение
        lines = ["📥 <b>Обновление стандартов</b>\n"]
        
        for family_name, info in result.items():
            if family_name == 'integrity':
                continue
            
            if info.get('success'):
                count = info.get('count', 0)
                lines.append(f"✅ {family_name}: {count} стандартов")
            else:
                error = info.get('error', 'Unknown error')
                lines.append(f"❌ {family_name}: {error}")
        
        lines.append("\n<b>Обновление завершено.</b>")
        
        return {
            'success': True,
            'message': '\n'.join(lines),
            'session': session.to_dict()
        }
    
    except Exception as e:
        logger.error(f"Error downloading standards: {e}", exc_info=True)
        return {
            'success': False,
            'message': f'Ошибка при обновлении стандартов: {str(e)}',
            'session': session.to_dict()
        }


def handle_integrity_check(text: str, session: Session, metadata: Dict, **kwargs) -> Dict[str, Any]:
    """
    Обработка проверки целостности базы стандартов.
    
    Args:
        text: Текст сообщения
        session: Сессия пользователя
        metadata: Метаданные интента
        **kwargs: Дополнительные параметры
        
    Returns:
        Словарь с результатом обработки
    """
    try:
        from standards.manager.standard_manager import StandardManager
        
        manager = StandardManager()
        message = manager.format_status_message()
        
        return {
            'success': True,
            'message': message,
            'session': session.to_dict()
        }
    
    except Exception as e:
        logger.error(f"Error checking integrity: {e}", exc_info=True)
        return {
            'success': False,
            'message': f'Ошибка при проверке базы: {str(e)}',
            'session': session.to_dict()
        }
