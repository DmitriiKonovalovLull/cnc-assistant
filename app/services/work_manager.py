"""
Менеджер работ пользователя.
Позволяет сохранять, просматривать и управлять работами под номерами.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from app.core.context import Context

logger = logging.getLogger(__name__)


class WorkManager:
    """
    Менеджер для управления работами пользователя.
    Работы сохраняются под номерами для быстрого доступа.
    """
    
    def __init__(self, db_session: Session):
        """
        Инициализация менеджера работ.
        
        Args:
            db_session: SQLAlchemy сессия
        """
        self.db_session = db_session
    
    def create_work(
        self,
        user_id: str,
        work_number: Optional[str] = None,
        description: Optional[str] = None,
        context: Optional[Context] = None
    ) -> Optional[str]:
        """
        Создать новую работу.
        
        Args:
            user_id: ID пользователя
            work_number: Номер работы (если не указан - генерируется автоматически)
            description: Описание работы
            context: Контекст работы
            
        Returns:
            Номер работы или None при ошибке
        """
        try:
            # Генерируем номер работы если не указан
            if not work_number:
                work_number = self._generate_work_number(user_id)
            
            # Проверяем, не существует ли уже работа с таким номером
            existing = self.get_work(user_id, work_number)
            if existing:
                logger.warning(f"Work {work_number} already exists for user {user_id}")
                return None
            
            # Сохраняем работу в БД
            work_data = {
                'work_number': work_number,
                'user_id': user_id,
                'description': description or '',
                'context': context.to_dict() if context else {},
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # Сохраняем в UserDecision с пометкой что это сохраненная работа
            from app.storage.models import UserDecision
            import json
            
            # Получаем значения диаметров и длины из контекста, используя 0 по умолчанию
            diameter_start = (context.diameter_start if context and context.diameter_start is not None else 0)
            diameter_end = (context.diameter_end if context and context.diameter_end is not None else 0)
            length = (context.length if context and context.length is not None else 0)
            
            decision = UserDecision(
                id=f"work_{user_id}_{work_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                user_id=user_id,
                diameter_start_mm=diameter_start,
                diameter_end_mm=diameter_end,
                length_mm=length,
                operation_type='saved_work',
                user_rpm=0,
                user_feed_mm_rev=0,
                user_ap_mm=0,
                comparison_choice='custom',
                full_context_json=json.dumps({
                    'work_number': work_number,
                    'description': description,
                    'context': work_data['context'],
                    'is_saved_work': True
                }, ensure_ascii=False, default=str),
                source='telegram',
                session_id=f"work_{work_number}"
            )
            
            self.db_session.add(decision)
            self.db_session.commit()
            
            logger.info(f"Created work {work_number} for user {user_id}")
            return work_number
        
        except Exception as e:
            logger.error(f"Error creating work: {e}", exc_info=True)
            self.db_session.rollback()
            return None
    
    def get_work(self, user_id: str, work_number: str) -> Optional[Dict[str, Any]]:
        """
        Получить работу по номеру.
        
        Args:
            user_id: ID пользователя
            work_number: Номер работы
            
        Returns:
            Данные работы или None
        """
        try:
            from app.storage.models import UserDecision
            import json
            
            decision = self.db_session.query(UserDecision).filter_by(
                user_id=user_id,
                session_id=f"work_{work_number}"
            ).first()
            
            if not decision:
                return None
            
            full_context = json.loads(decision.full_context_json) if decision.full_context_json else {}
            
            if full_context.get('is_saved_work'):
                return {
                    'work_number': work_number,
                    'description': full_context.get('description', ''),
                    'context': full_context.get('context', {}),
                    'created_at': decision.timestamp.isoformat() if decision.timestamp else None
                }
            
            return None
        
        except Exception as e:
            logger.error(f"Error getting work: {e}", exc_info=True)
            return None
    
    def list_works(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Получить список работ пользователя.
        
        Args:
            user_id: ID пользователя
            limit: Максимальное количество работ
            
        Returns:
            Список работ
        """
        try:
            from app.storage.models import UserDecision
            import json
            
            decisions = self.db_session.query(UserDecision).filter_by(
                user_id=user_id
            ).filter(
                UserDecision.session_id.like('work_%')
            ).order_by(UserDecision.timestamp.desc()).limit(limit).all()
            
            works = []
            for decision in decisions:
                if decision.full_context_json:
                    full_context = json.loads(decision.full_context_json)
                    if full_context.get('is_saved_work'):
                        work_number = full_context.get('work_number', 'unknown')
                        works.append({
                            'work_number': work_number,
                            'description': full_context.get('description', ''),
                            'created_at': decision.timestamp.isoformat() if decision.timestamp else None
                        })
            
            return works
        
        except Exception as e:
            logger.error(f"Error listing works: {e}", exc_info=True)
            return []
    
    def update_work(
        self,
        user_id: str,
        work_number: str,
        description: Optional[str] = None,
        context: Optional[Context] = None
    ) -> bool:
        """
        Обновить работу.
        
        Args:
            user_id: ID пользователя
            work_number: Номер работы
            description: Новое описание (если None - не обновляется)
            context: Новый контекст (если None - не обновляется)
            
        Returns:
            True если успешно обновлено
        """
        try:
            work = self.get_work(user_id, work_number)
            if not work:
                return False
            
            from app.storage.models import UserDecision
            import json
            
            decision = self.db_session.query(UserDecision).filter_by(
                user_id=user_id,
                session_id=f"work_{work_number}"
            ).first()
            
            if not decision:
                return False
            
            # Загружаем существующий контекст
            full_context = json.loads(decision.full_context_json) if decision.full_context_json else {}
            
            # Сохраняем важные поля
            if 'is_saved_work' not in full_context:
                full_context['is_saved_work'] = True
            if 'work_number' not in full_context:
                full_context['work_number'] = work_number
            
            # Обновляем описание только если оно передано (даже если пустое)
            if description is not None:
                full_context['description'] = description
            
            # Обновляем контекст только если он передан
            if context:
                full_context['context'] = context.to_dict()
                # Обновляем диаметры в записи UserDecision
                decision.diameter_start_mm = context.diameter_start if context.diameter_start is not None else 0
                decision.diameter_end_mm = context.diameter_end if context.diameter_end is not None else 0
                decision.length_mm = context.length if context.length is not None else 0
            
            # Обновляем время изменения
            full_context['updated_at'] = datetime.now().isoformat()
            
            # Сохраняем обновленный контекст
            decision.full_context_json = json.dumps(full_context, ensure_ascii=False, default=str)
            self.db_session.commit()
            
            logger.info(f"Updated work {work_number} for user {user_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error updating work: {e}", exc_info=True)
            self.db_session.rollback()
            return False
    
    def delete_work(self, user_id: str, work_number: str) -> bool:
        """
        Удалить работу.
        
        Args:
            user_id: ID пользователя
            work_number: Номер работы
            
        Returns:
            True если успешно удалено
        """
        try:
            from app.storage.models import UserDecision
            
            decision = self.db_session.query(UserDecision).filter_by(
                user_id=user_id,
                session_id=f"work_{work_number}"
            ).first()
            
            if decision:
                self.db_session.delete(decision)
                self.db_session.commit()
                logger.info(f"Deleted work {work_number} for user {user_id}")
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"Error deleting work: {e}", exc_info=True)
            self.db_session.rollback()
            return False
    
    def load_work_to_context(self, user_id: str, work_number: str) -> Optional[Context]:
        """
        Загрузить работу в контекст.
        
        Args:
            user_id: ID пользователя
            work_number: Номер работы
            
        Returns:
            Context с данными работы или None
        """
        work = self.get_work(user_id, work_number)
        if not work:
            return None
        
        try:
            from app.core.context import Context
            context = Context.from_dict(work.get('context', {}))
            context.user_id = user_id
            context.session_id = f"work_{work_number}"
            return context
        except Exception as e:
            logger.error(f"Error loading work to context: {e}", exc_info=True)
            return None
    
    def _generate_work_number(self, user_id: str) -> str:
        """
        Сгенерировать уникальный номер работы.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Номер работы (формат: W001, W002 и т.д.)
        """
        works = self.list_works(user_id, limit=1000)
        
        if not works:
            return "W001"
        
        # Находим максимальный номер
        max_num = 0
        for work in works:
            work_num = work.get('work_number', '')
            if work_num.startswith('W'):
                try:
                    num = int(work_num[1:])
                    max_num = max(max_num, num)
                except ValueError:
                    pass
        
        return f"W{max_num + 1:03d}"
