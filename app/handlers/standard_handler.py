"""Обработчик поиска стандартов."""

import logging
from typing import Dict, Any

from app.core.session import Session

logger = logging.getLogger(__name__)


def handle_standard_lookup(text: str, session: Session, metadata: Dict, **kwargs) -> Dict[str, Any]:
    """
    Обработка поиска стандарта.
    
    Pipeline: Cache → Database → Fallback
    
    Args:
        text: Текст сообщения
        session: Сессия пользователя
        metadata: Метаданные интента
        **kwargs: Дополнительные параметры (db_session, cache_manager)
        
    Returns:
        Словарь с результатом обработки
    """
    # Проверяем на "это не то"
    text_lower = text.lower()
    if any(x in text_lower for x in ["это не то", "не то", "неправильно", "ошибка"]):
        return handle_standard_mark_suspicious(text, session, metadata, **kwargs)
    
    try:
        # Получаем сессию БД и кэш из kwargs
        db_session = kwargs.get('db_session')
        cache_manager = kwargs.get('cache_manager')
        
        # Используем репозиторий для работы с БД
        if db_session:
            from standards.database.standard_repository import StandardRepository
            from standards.utils.standard_normalizer import parse_standard_designation
            
            # Парсим стандарт из текста
            parsed = parse_standard_designation(text)
            if not parsed:
                standard_type = metadata.get('standard_type')
                standard_number = metadata.get('standard_number')
            else:
                standard_type = parsed['type']
                standard_number = parsed.get('full_number', '')
            
            if not standard_type or not standard_number:
                return {
                    'success': False,
                    'message': 'Не удалось распознать стандарт. Укажите формат: ГОСТ 7798-30, ОСТ 33056-80',
                    'session': session.to_dict()
                }
            
            # Ищем в БД через репозиторий
            repository = StandardRepository(db_session, cache_manager)
            
            # Нормализуем family для поиска
            family = standard_type.upper()
            if family == 'ОСТ':
                family = 'OST'
            
            # Извлекаем код из номера
            code = standard_number.replace('-', ' ').strip()
            
            standard_data = repository.find_by_code(family, code)
            
            if standard_data:
                # Стандарт найден в БД
                session.set_standard(f"{standard_type} {standard_number}")
                
                # Форматируем ответ
                message = format_standard_from_db(standard_data)
                
                return {
                    'success': True,
                    'message': message,
                    'session': session.to_dict(),
                    'standard_info': standard_data,
                    'source': 'database'
                }
            else:
                # Стандарт не найден - предлагаем скачать
                return {
                    'success': False,
                    'message': (
                        f'❌ <b>Стандарт {standard_type} {standard_number} не найден в базе.</b>\n\n'
                        '💡 <b>Что можно сделать:</b>\n'
                        '1. Загрузить файл стандарта (PDF)\n'
                        '2. Ввести параметры детали вручную\n'
                        '3. Продолжить без стандарта'
                    ),
                    'session': session.to_dict(),
                    'source': 'not_found'
                }
        
        # Fallback: используем существующий StandardService
        from app.services.standard_service import StandardService
        
        standard_type = metadata.get('standard_type')
        standard_number = metadata.get('standard_number')
        
        if not standard_type or not standard_number:
            return {
                'success': False,
                'message': 'Не удалось распознать стандарт. Укажите формат: ГОСТ 7798-30, ОСТ 33056-80',
                'session': session.to_dict()
            }
        
        service = StandardService()
        standard_info = service.get_standard_info(standard_type, standard_number)
        
        session.set_standard(f"{standard_type} {standard_number}")
        
        message = service.format_standard_info(standard_info)
        
        return {
            'success': True,
            'message': message,
            'session': session.to_dict(),
            'standard_info': standard_info,
            'source': 'service'
        }
    
    except Exception as e:
        logger.error(f"Error in standard lookup: {e}", exc_info=True)
        return {
            'success': False,
            'message': f'Ошибка при поиске стандарта: {str(e)}',
            'session': session.to_dict()
        }


def handle_standard_mark_suspicious(text: str, session: Session, metadata: Dict, **kwargs) -> Dict[str, Any]:
    """
    Обработка "это не то" - пометить стандарт как подозрительный.
    
    Args:
        text: Текст сообщения
        session: Сессия пользователя
        metadata: Метаданные интента
        **kwargs: Дополнительные параметры
        
    Returns:
        Словарь с результатом обработки
    """
    db_session = kwargs.get('db_session')
    cache_manager = kwargs.get('cache_manager')
    
    if not db_session:
        return {
            'success': False,
            'message': 'База данных недоступна',
            'session': session.to_dict()
        }
    
    try:
        from standards.database.standard_repository import StandardRepository
        
        repository = StandardRepository(db_session, cache_manager)
        
        # Получаем текущий стандарт из сессии
        current_standard = session.current_standard
        if not current_standard:
            return {
                'success': False,
                'message': 'Не указан стандарт для проверки',
                'session': session.to_dict()
            }
        
        # Парсим стандарт
        from standards.utils.standard_normalizer import parse_standard_designation
        parsed = parse_standard_designation(current_standard)
        
        if not parsed:
            return {
                'success': False,
                'message': 'Не удалось распознать стандарт',
                'session': session.to_dict()
            }
        
        # Ищем стандарт в БД
        family = parsed['type'].upper()
        if family == 'ОСТ':
            family = 'OST'
        
        code = parsed.get('full_number', '')
        standard_data = repository.find_by_code(family, code)
        
        if not standard_data:
            return {
                'success': False,
                'message': 'Стандарт не найден в базе',
                'session': session.to_dict()
            }
        
        # Помечаем как подозрительный
        if repository.mark_as_suspicious(standard_data['id']):
            return {
                'success': True,
                'message': (
                    f'✅ <b>Стандарт {current_standard} помечен как подозрительный.</b>\n\n'
                    'Будет выполнена принудительная перепроверка при следующем обновлении.'
                ),
                'session': session.to_dict()
            }
        else:
            return {
                'success': False,
                'message': 'Не удалось пометить стандарт',
                'session': session.to_dict()
            }
    
    except Exception as e:
        logger.error(f"Error marking standard as suspicious: {e}", exc_info=True)
        return {
            'success': False,
            'message': f'Ошибка: {str(e)}',
            'session': session.to_dict()
        }


def format_standard_from_db(standard_data: Dict[str, Any]) -> str:
    """
    Форматировать данные стандарта из БД для пользователя.
    
    Args:
        standard_data: Данные стандарта из БД
        
    Returns:
        Отформатированное сообщение
    """
    lines = [
        f"📘 <b>{standard_data.get('full_code', 'Unknown')}</b>"
    ]
    
    if standard_data.get('title'):
        lines.append(f"\n{standard_data['title']}")
    
    if standard_data.get('year'):
        lines.append(f"\n📅 Год: {standard_data['year']}")
    
    if standard_data.get('status') == 'suspicious':
        lines.append("\n⚠️ <b>Требует проверки</b>")
    
    if standard_data.get('tables'):
        lines.append(f"\n📋 Распарсенные данные: {len(standard_data['tables'])} разделов")
    
    return "\n".join(lines)

