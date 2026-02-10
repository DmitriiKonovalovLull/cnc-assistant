"""
Адаптер для интеграции LLM в будущем.
Абстракция для работы с языковыми моделями.
"""

import logging
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
from enum import Enum

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Провайдеры LLM."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"
    CUSTOM = "custom"


class LLMAdapter(ABC):
    """
    Абстрактный адаптер для работы с LLM.
    Позволяет легко переключаться между разными провайдерами.
    """
    
    @abstractmethod
    async def generate_recommendation(
        self,
        context: Dict[str, Any],
        user_message: str
    ) -> Dict[str, Any]:
        """
        Сгенерировать рекомендацию на основе контекста.
        
        Args:
            context: Контекст задачи обработки
            user_message: Сообщение пользователя
            
        Returns:
            Словарь с рекомендацией и объяснением
        """
        pass
    
    @abstractmethod
    async def make_assumptions(
        self,
        context: Dict[str, Any],
        missing_fields: List[str]
    ) -> Dict[str, Any]:
        """
        Сделать предположения для недостающих полей.
        
        Args:
            context: Текущий контекст
            missing_fields: Список недостающих полей
            
        Returns:
            Словарь с предположениями и их обоснованиями
        """
        pass
    
    @abstractmethod
    async def explain_recommendation(
        self,
        recommendation: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """
        Объяснить рекомендацию естественным языком.
        
        Args:
            recommendation: Рекомендация калькулятора
            context: Контекст задачи
            
        Returns:
            Текстовое объяснение
        """
        pass
    
    @abstractmethod
    async def format_response(
        self,
        action: str,
        data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """
        Форматировать ответ пользователю.
        
        Args:
            action: Тип действия (clarify, calculate, error)
            data: Данные для форматирования
            context: Контекст диалога
            
        Returns:
            Отформатированный текст ответа
        """
        pass


class RuleBasedLLMAdapter(LLMAdapter):
    """
    Правило-основанный адаптер (текущая реализация).
    Использует существующую логику без реального LLM.
    """
    
    def __init__(self):
        """Инициализация правило-основанного адаптера."""
        logger.info("Using rule-based LLM adapter (no actual LLM)")
    
    async def generate_recommendation(
        self,
        context: Dict[str, Any],
        user_message: str
    ) -> Dict[str, Any]:
        """Генерирует рекомендацию через существующие калькуляторы."""
        # Используем существующую логику
        from app.services.recommendation import get_turning_recommendation
        
        recommendation = get_turning_recommendation(
            material=context.get('material', 'сталь'),
            operation=context.get('operation', 'токарка'),
            machine_type=context.get('machine_type', 'токарный ЧПУ'),
            mode=context.get('mode', 'черновая'),
            diameter_start_mm=context.get('diameter_start'),
            diameter_end_mm=context.get('diameter_end'),
            tool_material=context.get('tool_material', 'твердый сплав')
        )
        
        return {
            'recommendation': recommendation,
            'explanation': self._generate_explanation(recommendation, context),
            'confidence': 0.8
        }
    
    async def make_assumptions(
        self,
        context: Dict[str, Any],
        missing_fields: List[str]
    ) -> Dict[str, Any]:
        """Делает предположения через AssumptionEngine."""
        from app.core.assumptions import AssumptionEngine
        from app.services.knowledge_service import KnowledgeService
        
        knowledge_service = KnowledgeService()
        await knowledge_service.initialize()
        
        assumption_engine = AssumptionEngine(knowledge_service)
        
        # Создаем временный Context для предположений
        from app.core.context import Context
        temp_context = Context()
        for key, value in context.items():
            if hasattr(temp_context, key):
                setattr(temp_context, key, value)
        
        temp_context = assumption_engine.make_assumptions(temp_context)
        
        assumptions = {}
        for field in missing_fields:
            if hasattr(temp_context, field):
                value = getattr(temp_context, field)
                if value:
                    metadata = temp_context.get_field_metadata(field)
                    assumptions[field] = {
                        'value': value,
                        'confidence': metadata.confidence if metadata else 0.7,
                        'reasoning': metadata.reasoning if metadata else 'Предположено на основе контекста'
                    }
        
        return assumptions
    
    async def explain_recommendation(
        self,
        recommendation: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """Генерирует объяснение рекомендации."""
        return self._generate_explanation(recommendation, context)
    
    async def format_response(
        self,
        action: str,
        data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """Форматирует ответ через существующие функции."""
        # Используем существующие функции форматирования
        if action == 'clarify':
            from app.bot.telegram_bot import format_clarification_request
            from app.core.context import Context
            temp_context = Context()
            for key, value in context.items():
                if hasattr(temp_context, key):
                    setattr(temp_context, key, value)
            return format_clarification_request(temp_context, data.get('missing_fields', []))
        
        elif action == 'calculate':
            from app.bot.telegram_bot import format_recommendation
            from app.core.context import Context
            temp_context = Context()
            for key, value in context.items():
                if hasattr(temp_context, key):
                    setattr(temp_context, key, value)
            return format_recommendation(data.get('recommendation', {}), temp_context)
        
        return str(data)
    
    def _generate_explanation(self, recommendation: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Генерирует объяснение рекомендации."""
        lines = []
        
        material = context.get('material', 'сталь')
        mode = context.get('mode', 'черновая')
        
        lines.append(f"Для материала {material} и режима {mode} рекомендую:")
        lines.append(f"• Скорость резания: {recommendation.get('vc', 0):.0f} м/мин")
        lines.append(f"• Обороты: {recommendation.get('rpm', 0):.0f} об/мин")
        lines.append(f"• Подача: {recommendation.get('feed', 0):.2f} мм/об")
        lines.append(f"• Глубина: {recommendation.get('ap', 0):.1f} мм")
        
        return "\n".join(lines)


class LLMFactory:
    """Фабрика для создания LLM адаптеров."""
    
    @staticmethod
    def create_adapter(provider: LLMProvider = LLMProvider.LOCAL, **kwargs) -> LLMAdapter:
        """
        Создать адаптер для указанного провайдера.
        
        Args:
            provider: Провайдер LLM
            **kwargs: Дополнительные параметры для адаптера
            
        Returns:
            Экземпляр LLMAdapter
        """
        if provider == LLMProvider.LOCAL:
            return RuleBasedLLMAdapter()
        
        elif provider == LLMProvider.OPENAI:
            # TODO: Реализовать OpenAI адаптер
            logger.warning("OpenAI adapter not implemented, using rule-based")
            return RuleBasedLLMAdapter()
        
        elif provider == LLMProvider.ANTHROPIC:
            # TODO: Реализовать Anthropic адаптер
            logger.warning("Anthropic adapter not implemented, using rule-based")
            return RuleBasedLLMAdapter()
        
        else:
            return RuleBasedLLMAdapter()
