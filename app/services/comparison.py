"""
Сравнение рекомендаций бота с решениями оператора.
Анализ различий и причин отклонений.
"""

import logging
from typing import Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ComparisonReason(Enum):
    """Причины различий между рекомендацией и решением оператора."""
    LOWER_DUE_TO_MACHINE = "lower_machine"  # Снижено из-за ограничений станка
    LOWER_DUE_TO_TOOL = "lower_tool"  # Снижено из-за инструмента
    LOWER_DUE_TO_EXPERIENCE = "lower_experience"  # Снижено по опыту
    HIGHER_DUE_TO_PRODUCTIVITY = "higher_productivity"  # Увеличено для производительности
    HIGHER_DUE_TO_QUALITY = "higher_quality"  # Изменено для качества
    SAME_AS_STANDARD = "same_standard"  # Соответствует стандарту
    CUSTOM_REASON = "custom"  # Уникальное решение


@dataclass
class ComparisonResult:
    """Результат сравнения рекомендации и решения оператора."""
    parameter: str  # vc, rpm, feed, ap
    bot_value: float
    user_value: float
    difference_percent: float
    reason: ComparisonReason
    explanation: str


class ComparisonService:
    """
    Сервис для сравнения рекомендаций бота с решениями операторов.
    """
    
    def __init__(self):
        """Инициализация сервиса сравнения."""
        pass
    
    def compare_recommendation_with_user_decision(
        self,
        bot_recommendation: Dict[str, Any],
        user_decision: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Сравнить рекомендацию бота с решением оператора.
        
        Args:
            bot_recommendation: Рекомендация бота
            user_decision: Решение оператора
            context: Контекст задачи
            
        Returns:
            Словарь с результатами сравнения
        """
        comparisons = []
        
        # Сравниваем каждый параметр
        parameters = {
            'vc': ('vc_m_min', 'vc', 'Скорость резания'),
            'rpm': ('rpm', 'rpm', 'Обороты'),
            'feed': ('feed_mm_rev', 'feed', 'Подача'),
            'ap': ('ap_mm', 'ap', 'Глубина резания')
        }
        
        for param_key, (bot_key, user_key, display_name) in parameters.items():
            bot_val = bot_recommendation.get(bot_key) or bot_recommendation.get(param_key)
            user_val = user_decision.get(user_key) or user_decision.get(param_key)
            
            if bot_val and user_val and bot_val > 0:
                diff_percent = ((user_val - bot_val) / bot_val) * 100
                
                # Определяем причину различия
                reason = self._determine_reason(param_key, diff_percent, context, bot_val, user_val)
                
                # Формируем объяснение
                explanation = self._generate_explanation(param_key, diff_percent, reason, context)
                
                comparisons.append({
                    'parameter': param_key,
                    'display_name': display_name,
                    'bot_value': bot_val,
                    'user_value': user_val,
                    'difference_percent': diff_percent,
                    'reason': reason.value,
                    'explanation': explanation
                })
        
        # Общая оценка
        overall_assessment = self._assess_overall_difference(comparisons)
        
        return {
            'comparisons': comparisons,
            'overall_assessment': overall_assessment,
            'is_similar': overall_assessment['similarity_score'] > 0.8,
            'has_significant_differences': any(
                abs(c['difference_percent']) > 30 for c in comparisons
            )
        }
    
    def _determine_reason(
        self,
        parameter: str,
        diff_percent: float,
        context: Dict[str, Any],
        bot_value: float,
        user_value: float
    ) -> ComparisonReason:
        """
        Определить причину различия между рекомендацией и решением.
        
        Args:
            parameter: Параметр (vc, rpm, feed, ap)
            diff_percent: Процент различия
            context: Контекст задачи
            bot_value: Значение бота
            user_value: Значение оператора
            
        Returns:
            Причина различия
        """
        # Если значения близки (в пределах 10%)
        if abs(diff_percent) < 10:
            return ComparisonReason.SAME_AS_STANDARD
        
        # Если оператор снизил параметры
        if diff_percent < -10:
            # Проверяем ограничения станка
            machine_max_rpm = context.get('machine_max_rpm')
            if parameter == 'rpm' and machine_max_rpm and user_value < machine_max_rpm * 0.8:
                return ComparisonReason.LOWER_DUE_TO_MACHINE
            
            # Проверяем ограничения инструмента
            tool_radius = context.get('tool_radius')
            if parameter == 'ap' and tool_radius and user_value < tool_radius * 1.5:
                return ComparisonReason.LOWER_DUE_TO_TOOL
            
            # По опыту
            return ComparisonReason.LOWER_DUE_TO_EXPERIENCE
        
        # Если оператор увеличил параметры
        if diff_percent > 10:
            # Для производительности
            if parameter in ['rpm', 'feed']:
                return ComparisonReason.HIGHER_DUE_TO_PRODUCTIVITY
            
            # Для качества
            if parameter == 'ap':
                return ComparisonReason.HIGHER_DUE_TO_QUALITY
        
        return ComparisonReason.CUSTOM_REASON
    
    def _generate_explanation(
        self,
        parameter: str,
        diff_percent: float,
        reason: ComparisonReason,
        context: Dict[str, Any]
    ) -> str:
        """
        Сгенерировать объяснение различия.
        
        Args:
            parameter: Параметр
            diff_percent: Процент различия
            reason: Причина
            context: Контекст
            
        Returns:
            Текстовое объяснение
        """
        explanations = {
            ComparisonReason.LOWER_DUE_TO_MACHINE: f"Снижено из-за ограничений станка",
            ComparisonReason.LOWER_DUE_TO_TOOL: f"Снижено из-за характеристик инструмента",
            ComparisonReason.LOWER_DUE_TO_EXPERIENCE: f"Снижено по опыту работы с этим материалом",
            ComparisonReason.HIGHER_DUE_TO_PRODUCTIVITY: f"Увеличено для повышения производительности",
            ComparisonReason.HIGHER_DUE_TO_QUALITY: f"Изменено для улучшения качества обработки",
            ComparisonReason.SAME_AS_STANDARD: f"Соответствует стандартным рекомендациям",
            ComparisonReason.CUSTOM_REASON: f"Уникальное решение оператора"
        }
        
        base_explanation = explanations.get(reason, "Уникальное решение")
        
        if abs(diff_percent) > 30:
            base_explanation += f" (отклонение {abs(diff_percent):.0f}%)"
        
        return base_explanation
    
    def _assess_overall_difference(self, comparisons: list) -> Dict[str, Any]:
        """
        Оценить общее различие между рекомендацией и решением.
        
        Args:
            comparisons: Список сравнений параметров
            
        Returns:
            Общая оценка
        """
        if not comparisons:
            return {
                'similarity_score': 0.0,
                'assessment': 'Нет данных для сравнения'
            }
        
        # Вычисляем среднее отклонение
        avg_diff = sum(abs(c['difference_percent']) for c in comparisons) / len(comparisons)
        
        # Оценка схожести (0-1, где 1 = идентично)
        similarity_score = max(0.0, 1.0 - (avg_diff / 100.0))
        
        # Качественная оценка
        if similarity_score > 0.9:
            assessment = "Очень близко к рекомендации"
        elif similarity_score > 0.7:
            assessment = "Близко к рекомендации с небольшими отклонениями"
        elif similarity_score > 0.5:
            assessment = "Умеренные различия с рекомендацией"
        else:
            assessment = "Значительные различия с рекомендацией"
        
        return {
            'similarity_score': similarity_score,
            'average_difference_percent': avg_diff,
            'assessment': assessment
        }
