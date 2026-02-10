"""
Сбор данных для обучения LLM.
Сохраняет: контекст → расчёт → решение человека → результат
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.core.context import Context

logger = logging.getLogger(__name__)


class DataCollector:
    """
    Сборщик данных для обучения LLM.
    Сохраняет полный цикл: вход → расчёт → решение оператора → результат.
    """
    
    def __init__(self, db_session: Session):
        """
        Инициализация сборщика данных.
        
        Args:
            db_session: SQLAlchemy сессия
        """
        self.db_session = db_session
    
    def collect_interaction(
        self,
        user_id: str,
        context: Context,
        bot_recommendation: Dict[str, Any],
        user_decision: Optional[Dict[str, Any]] = None,
        result: Optional[str] = None,
        feedback: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Собрать данные о взаимодействии.
        
        Args:
            user_id: ID пользователя
            context: Контекст задачи
            bot_recommendation: Рекомендация бота
            user_decision: Решение оператора (опционально)
            result: Результат операции (опционально)
            feedback: Обратная связь (опционально)
            
        Returns:
            True если успешно сохранено
        """
        try:
            from app.storage.models import save_user_decision
            
            # Формируем данные для сохранения
            geometry = {
                'diameter_start_mm': context.diameter_start or 0,
                'diameter_end_mm': context.diameter_end or 0,
                'length_mm': context.length or 0
            }
            
            operation = {
                'operation_type': context.operation or 'токарка',
                'mode': context.mode or 'черновая',
                'is_external': True
            }
            
            # Решение оператора (если есть)
            user_actual = user_decision or {
                'rpm': 0,
                'feed': 0,
                'ap': 0
            }
            
            # Определяем сравнение
            comparison_choice = 'custom'
            if user_decision:
                # Сравниваем с рекомендацией
                from app.services.comparison import ComparisonService
                comparison_service = ComparisonService()
                comparison_result = comparison_service.compare_recommendation_with_user_decision(
                    bot_recommendation,
                    user_decision,
                    context.to_dict()
                )
                
                if comparison_result.get('is_similar'):
                    comparison_choice = 'same'
                elif any(c['difference_percent'] < -10 for c in comparison_result.get('comparisons', [])):
                    comparison_choice = 'lower'
                elif any(c['difference_percent'] > 10 for c in comparison_result.get('comparisons', [])):
                    comparison_choice = 'higher'
            
            # Сохраняем решение
            decision = save_user_decision(
                session=self.db_session,
                user_id=user_id,
                geometry=geometry,
                operation=operation,
                bot_recommendation=bot_recommendation,
                user_actual=user_actual,
                comparison_choice=comparison_choice,
                source='telegram',
                session_id=context.session_id,
                full_context=context.to_dict()
            )
            
            # Если есть результат операции, обновляем запись
            if result and decision:
                decision.result_type = result
                if feedback:
                    decision.result_details = str(feedback)
                self.db_session.commit()
            
            logger.info(f"Collected interaction data for user {user_id}, decision ID: {decision.id if decision else 'None'}")
            return True
        
        except Exception as e:
            logger.error(f"Error collecting interaction data: {e}", exc_info=True)
            self.db_session.rollback()
            return False
    
    def collect_feedback(
        self,
        decision_id: str,
        result_type: str,
        details: Optional[str] = None,
        tool_life_minutes: Optional[float] = None,
        machining_time_minutes: Optional[float] = None
    ) -> bool:
        """
        Собрать обратную связь о результате операции.
        
        Args:
            decision_id: ID решения
            result_type: Тип результата (ok, chatter, tool_wear, etc.)
            details: Детали результата
            tool_life_minutes: Время работы инструмента
            machining_time_minutes: Время обработки
            
        Returns:
            True если успешно сохранено
        """
        try:
            from app.storage.models import UserDecision
            
            decision = self.db_session.query(UserDecision).filter_by(id=decision_id).first()
            if decision:
                decision.result_type = result_type
                decision.result_details = details
                decision.tool_life_minutes = tool_life_minutes
                decision.actual_machining_time_min = machining_time_minutes
                
                self.db_session.commit()
                logger.info(f"Collected feedback for decision {decision_id}")
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"Error collecting feedback: {e}", exc_info=True)
            self.db_session.rollback()
            return False
