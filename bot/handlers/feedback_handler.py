"""
Обработчик обратной связи и исправлений - для 👍 / ❌ / правок пользователей
"""

from typing import Dict, Any
from core.context import CuttingContext, DialogState
from core.memory.memory_manager import memory_manager
from core.rules_engine import get_rules_engine


class FeedbackHandler:
    """Обработчик обратной связи - учится на исправлениях."""

    def __init__(self):
        self.rules_engine = get_rules_engine()

    def handle_feedback(self, user_id: str, text: str,
                       intent_result, context: CuttingContext) -> str:
        """Обрабатывает обратную связь и исправления."""
        text_lower = text.lower().strip()

        # 1. "Где?" - повтор рекомендаций
        if any(phrase in text_lower for phrase in ["где?", "а где?", "так и где?", "повтори"]):
            return self._repeat_recommendations(context)

        # 2. Общие исправления "не подходит", "нет"
        if any(word in text_lower for word in ["не подходит", "нет,", "не так", "неправильно"]):
            return self._handle_general_feedback(context, text_lower)

        # 3. Конкретные исправления "исправь подачу на 0.2"
        if any(word in text_lower for word in ["исправь", "сделай", "поставь", "измени"]):
            return self._handle_specific_correction(user_id, context, text_lower, intent_result)

        # 4. Положительная обратная связь
        if any(word in text_lower for word in ["да,", "верно", "правильно", "спасибо", "хорошо"]):
            return self._handle_positive_feedback(user_id, context)

        # 5. Запрос альтернативы
        if any(word in text_lower for word in ["другое", "вариант", "ещё", "альтернатив"]):
            return self._handle_alternative_request(context)

        # Дефолтный ответ
        return "Понял обратную связь. Уточните, что именно не подходит?"

    def _repeat_recommendations(self, context: CuttingContext) -> str:
        """Повторяет последние рекомендации."""
        if not context.recommendations_given:
            return "Рекомендации ещё не давались. Давайте рассчитаем?"

        # Ищем последнюю рекомендацию в истории
        last_recommendation = None
        for msg in reversed(context.conversation_history):
            if msg.get("role") == "assistant" and any(
                marker in msg.get("content", "") for marker in ["⚙️", "🎯", "Рекомендации"]
            ):
                last_recommendation = msg.get("content")
                break

        if last_recommendation:
            return f"🔄 **Повтор рекомендаций:**\n\n{last_recommendation}"
        else:
            return self._regenerate_recommendations(context)

    def _regenerate_recommendations(self, context: CuttingContext) -> str:
        """Заново генерирует рекомендации."""
        if not context.has_enough_for_recommendation():
            return "Не хватает данных для рекомендаций. Уточните материал, операцию и диаметр."

        mode = "finishing" if context.is_finishing_operation() else "roughing"

        params = self.rules_engine.get_cutting_parameters(
            material=context.material,
            operation=context.operation,
            diameter=context.current_diameter or context.target_diameter,
            mode=mode,
            surface_roughness=context.surface_roughness
        )

        recommendation = self.rules_engine.get_recommendation_text(
            material=context.material,
            operation=context.operation,
            diameter=context.current_diameter or context.target_diameter,
            parameters=params,
            context=context.to_dict() if context.has_goal() else None
        )

        return recommendation

    def _handle_general_feedback(self, context: CuttingContext, text: str) -> str:
        """Обрабатывает общую обратную связь."""
        # Определяем, что именно не подходит
        if any(word in text for word in ["подач", "feed"]):
            return "Понял, не подходит подача. Какую подачу поставить?"
        elif any(word in text for word in ["оборот", "скорость", "rpm", "скорост"]):
            return "Понял, не подходят обороты. Какие обороты поставить?"
        elif any(word in text for word in ["глубин", "depth"]):
            return "Понял, не подходит глубина резания. Какую глубину поставить?"
        elif any(word in text for word in ["инструмент", "tool"]):
            return "Понял, не подходит инструмент. Какой инструмент использовать?"
        else:
            return "Понял, что-то не подходит. Уточните: подача, обороты, глубина или инструмент?"

    def _handle_specific_correction(self, user_id: str, context: CuttingContext,
                                   text: str, intent_result) -> str:
        """Обрабатывает конкретное исправление."""
        # Извлекаем параметр и значение
        import re

        # Паттерны для извлечения
        patterns = [
            r'исправь\s+(\w+)\s+на\s+(\d+[.,]?\d*)',
            r'сделай\s+(\w+)\s+(\d+[.,]?\d*)',
            r'поставь\s+(\w+)\s+(\d+[.,]?\d*)',
            r'(\w+)\s+(\d+[.,]?\d*)\s+вместо',
        ]

        param = None
        value = None
        unit = None

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                param_word = match.group(1).lower()
                value_str = match.group(2).replace(',', '.')

                # Определяем параметр
                if 'подач' in param_word or 'feed' in param_word:
                    param = 'feed'
                elif 'оборот' in param_word or 'скорость' in param_word or 'speed' in param_word:
                    param = 'speed'
                elif 'глубин' in param_word or 'depth' in param_word:
                    param = 'depth_of_cut'
                elif 'инструмент' in param_word or 'tool' in param_word:
                    param = 'tool'

                # Пробуем преобразовать значение
                try:
                    value = float(value_str)
                except:
                    value = value_str  # Для строковых значений (инструмент)

                break

        if param and value:
            # Сохраняем исправление в память
            correction = {
                "wrong": {param: getattr(context, param, None)},
                "correct": {param: value},
                "type": f"{param}_correction",
                "context": context.to_dict()
            }

            memory_manager.log_correction(
                user_id,
                correction["wrong"],
                correction["correct"],
                correction["context"]
            )

            # Обновляем контекст
            if hasattr(context, param):
                context.update(**{param: value})
                context.corrections_received.append(correction)

                return f"✅ Исправил {param} на **{value}**. Запомнил это исправление!"

        return "Не понял, что именно исправить. Пример: 'исправь подачу на 0.2'"

    def _handle_positive_feedback(self, user_id: str, context: CuttingContext) -> str:
        """Обрабатывает положительную обратную связь."""
        # Логируем успешный диалог
        if context.recommendations_given:
            memory_manager.learn_from_feedback(user_id, {
                "type": "positive",
                "parameters": context.to_dict(),
                "message": "Пользователь подтвердил корректность рекомендаций"
            })

            context.active_step = DialogState.COMPLETED

            return (
                "✅ Отлично! Рад, что помог.\n\n"
                "📚 **Запомнил ваши предпочтения:**\n"
                f"• Материал: **{context.material}**\n"
                f"• Операция: **{context.operation}**\n"
                f"• Диаметр: **Ø{context.current_diameter} мм**\n\n"
                "Для новой задачи используйте /reset"
            )

        return "Спасибо за обратную связь! Продолжаем?"

    def _handle_alternative_request(self, context: CuttingContext) -> str:
        """Предлагает альтернативные варианты."""
        if not context.has_enough_for_recommendation():
            return "Сначала нужно задать базовые параметры (материал, операция, диаметр)."

        # Предлагаем альтернативный режим
        current_mode = "finishing" if context.is_finishing_operation() else "roughing"
        alternative_mode = "roughing" if current_mode == "finishing" else "finishing"

        params = self.rules_engine.get_cutting_parameters(
            material=context.material,
            operation=context.operation,
            diameter=context.current_diameter or context.target_diameter,
            mode=alternative_mode,
            surface_roughness=context.surface_roughness
        )

        recommendation = self.rules_engine.get_recommendation_text(
            material=context.material,
            operation=context.operation,
            diameter=context.current_diameter or context.target_diameter,
            parameters=params,
            context=context.to_dict() if context.has_goal() else None
        )

        return f"🔄 **Альтернативный вариант ({alternative_mode}):**\n\n{recommendation}"


# Глобальный экземпляр
_feedback_handler = FeedbackHandler()


def get_feedback_handler() -> FeedbackHandler:
    """Возвращает глобальный обработчик обратной связи."""
    return _feedback_handler


def handle_feedback(user_id: str, text: str, intent_result, context) -> str:
    """Упрощенный интерфейс для обработки обратной связи."""
    return _feedback_handler.handle_feedback(user_id, text, intent_result, context)