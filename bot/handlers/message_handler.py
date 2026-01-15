"""
Основной обработчик сообщений - входная точка с интеграцией всех компонентов.
Интегрирует: Context + Intent + DialogManager + RulesEngine
"""

from typing import Optional, Dict, Any
from core.context import get_user_context, DialogState, save_user_context, reset_user_context
from core.intent import get_intent_parser, parse_intent
from core.dialog_manager import DialogManager
from core.rules_engine import get_rules_engine
from bot.handlers.feedback_handler import FeedbackHandler


class MessageHandler:
    """Главный обработчик сообщений - связывает все компоненты."""

    def __init__(self):
        self.intent_parser = get_intent_parser()
        self.dialog_manager = DialogManager()
        self.rules_engine = get_rules_engine()
        self.feedback_handler = FeedbackHandler()

    def handle_message(self, user_id: str, text: str) -> str:
        """Основной метод обработки сообщения."""
        try:
            print(f"\n{'=' * 50}")
            print(f"📨 Сообщение от {user_id}: {text}")

            # 1. Получаем контекст пользователя (НИКОГДА не теряется)
            context = get_user_context(user_id)
            print(f"📊 Контекст до: state={context.active_step.name}, "
                  f"material={context.material}, op={context.operation}")

            # 2. Парсим намерение (только извлекаем данные)
            intent_result = parse_intent(text)
            print(f"🎯 Интент: {intent_result.intent} (conf: {intent_result.confidence:.2f})")

            # 3. Обрабатываем специальные случаи без изменения состояния
            special_response = self._handle_special_cases(user_id, text, intent_result, context)
            if special_response:
                context.add_conversation_turn("user", text)
                context.add_conversation_turn("assistant", special_response)
                return special_response

            # 4. Определяем, нужно ли передать управление feedback_handler
            if intent_result.intent in ['correction', 'feedback']:
                return self.feedback_handler.handle_feedback(
                    user_id, text, intent_result, context
                )

            # 5. Обновляем контекст из распарсенных данных
            self._update_context_from_intent(context, intent_result)

            # 6. Передаем управление DialogManager (FSM)
            response, next_state = self.dialog_manager.process(
                context, intent_result.data, text
            )

            # 7. Если мы в состоянии рекомендаций, добавляем расчеты
            if next_state == DialogState.RECOMMENDING:
                response = self._enhance_with_calculations(context, response)

            # 8. Логируем и сохраняем
            context.add_conversation_turn("user", text)
            context.add_conversation_turn("assistant", response)

            if context.is_dirty():
                save_user_context(user_id)

            print(f"💬 Ответ: {response[:100]}...")
            print(f"🔄 Следующее состояние: {next_state.name}")
            print(f"{'=' * 50}\n")

            return response

        except Exception as e:
            print(f"❌ Ошибка в MessageHandler: {e}")
            import traceback
            traceback.print_exc()
            return self._get_error_response()

    def _handle_special_cases(self, user_id: str, text: str,
                              intent_result, context) -> Optional[str]:
        """Обрабатывает специальные случаи без изменения состояния."""
        text_lower = text.lower().strip()

        # ЖЁСТКОЕ ПРАВИЛО: /help НЕ меняет состояние
        if text_lower.startswith('/help'):
            return self._get_help_response(context)

        # ЖЁСТКОЕ ПРАВИЛО: /reset сбрасывает только по команде
        if text_lower.startswith('/reset'):
            reset_user_context(user_id)
            return "🔄 Контекст сброшен. Начинаем новую задачу!\n\nКакой материал обрабатываем?"

        # ЖЁСТКОЕ ПРАВИЛО: /context показывает что помнит
        if text_lower.startswith('/context'):
            return self._show_context_info(context)

        return None

    def _update_context_from_intent(self, context, intent_result):
        """Обновляет контекст из распарсенных данных."""
        data = intent_result.data

        # Материал
        if data.get('material'):
            if not context.material or data.get('material_confidence', 0) > context.confidence.get('material', 0):
                context.update(material=data['material'])

        # Операция
        if data.get('operation'):
            if not context.operation or data.get('operation_confidence', 0) > context.confidence.get('operation', 0):
                context.update(operation=data['operation'])

        # Диаметры (особая логика для целей)
        if data.get('diameter'):
            dia = data['diameter']

            # Проверяем на цель обработки (X → Y)
            original_text = data.get('original_text', '').lower()
            if '→' in original_text or 'до' in original_text:
                if not context.start_diameter:
                    context.update(start_diameter=dia)
                else:
                    context.update(target_diameter=dia, current_diameter=dia)
            else:
                context.update(current_diameter=dia)
                if not context.start_diameter:
                    context.update(start_diameter=dia)

        # Чистота поверхности
        if data.get('surface_roughness'):
            context.update(surface_roughness=data['surface_roughness'])
            if "finishing" not in context.modes:
                context.modes.append("finishing")
            context.active_mode = "finishing"

        # Режимы
        if data.get('modes'):
            for mode in data['modes']:
                if mode not in context.modes:
                    context.modes.append(mode)

    def _enhance_with_calculations(self, context, base_response: str) -> str:
        """Добавляет расчеты к ответу в состоянии рекомендаций."""
        if not context.has_enough_for_recommendation():
            return base_response

        try:
            # Определяем режим
            mode = "finishing" if context.is_finishing_operation() else "roughing"

            # Получаем параметры
            params = self.rules_engine.get_cutting_parameters(
                material=context.material,
                operation=context.operation,
                diameter=context.current_diameter or context.target_diameter,
                mode=mode,
                surface_roughness=context.surface_roughness
            )

            # Формируем текстовую рекомендацию
            recommendation = self.rules_engine.get_recommendation_text(
                material=context.material,
                operation=context.operation,
                diameter=context.current_diameter or context.target_diameter,
                parameters=params,
                context=context.to_dict() if context.has_goal() else None
            )

            return recommendation

        except Exception as e:
            print(f"Ошибка при расчете рекомендаций: {e}")
            return base_response

    def _get_help_response(self, context) -> str:
        """Возвращает контекстно-зависимую справку."""
        help_text = "🆘 **Контекстно-зависимая справка**\n\n"

        help_text += "🤖 **Что я помню:**\n"
        if context.material:
            help_text += f"• Материал: **{context.material}**\n"
        if context.operation:
            help_text += f"• Операция: **{context.operation}**\n"
        if context.current_diameter:
            help_text += f"• Диаметр: **Ø{context.current_diameter} мм**\n"
        if context.has_goal():
            help_text += f"• Цель: **с Ø{context.start_diameter} до Ø{context.target_diameter}**\n"
        if context.surface_roughness:
            help_text += f"• Чистота: **Ra {context.surface_roughness}**\n"

        help_text += "\n💡 **Что можно сделать дальше:**\n"

        if context.active_step == DialogState.COLLECTING_CONTEXT:
            missing = context.get_missing_fields()
            if missing:
                help_text += f"• Уточните: **{', '.join(missing)}**\n"
            else:
                help_text += "• Скажите **'давай расчет'** или **'посчитай'**\n"

        elif context.active_step == DialogState.RECOMMENDING:
            help_text += "• Скажите **'где?'** чтобы повторить рекомендации\n"
            help_text += "• Укажите **'исправь [параметр] на [значение]'**\n"
            help_text += "• Или просто **'спасибо'** для завершения\n"

        help_text += "\n🔄 **Команды:**\n"
        help_text += "/help - эта справка\n"
        help_text += "/reset - начать новую задачу\n"
        help_text += f"/context - подробнее (сейчас: {context.active_step.name})\n\n"
        help_text += "➡️ **Продолжаем диалог там, где остановились.**"

        context.mark_help_shown()
        return help_text

    def _show_context_info(self, context) -> str:
        """Показывает подробную информацию о контексте."""
        info = "📊 **Текущий контекст:**\n\n"

        # Основные данные
        info += "**Данные:**\n"
        info += f"• Материал: {context.material or '❌ не указан'}\n"
        info += f"• Операция: {context.operation or '❌ не указана'}\n"
        info += f"• Текущий диаметр: {context.current_diameter or '❌ не указан'}\n"

        # Цель обработки
        if context.has_goal():
            info += f"\n**🎯 Цель обработки:**\n"
            info += f"• С Ø{context.start_diameter} до Ø{context.target_diameter}\n"
            info += f"• Припуск: {context.get_removal_amount():.1f} мм на сторону\n"
            if context.surface_roughness:
                info += f"• Чистота: Ra {context.surface_roughness}\n"
            info += f"• Тип: {'чистовая' if context.is_finishing_operation() else 'черновая'}\n"

        # Состояние FSM
        info += f"\n**🔄 Состояние FSM:** {context.active_step.name}\n"

        # История
        info += f"\n**📝 История диалога:**\n"
        info += f"• Сообщений: {len(context.conversation_history)}\n"
        info += f"• Рекомендаций дано: {len(context.recommendations_given)}\n"
        info += f"• Исправлений получено: {len(context.corrections_received)}\n"

        # Проверки
        info += f"\n**✅ Проверки:**\n"
        info += f"• Минимум данных: {'✓' if context.has_minimum_data() else '✗'}\n"
        info += f"• Достаточно для рекомендации: {'✓' if context.has_enough_for_recommendation() else '✗'}\n"
        info += f"• Заблокирован: {'✓' if context.is_locked() else '✗'}\n"

        info += f"\n🆔 ID сессии: {context.session_id}"

        return info

    def _get_error_response(self) -> str:
        """Возвращает ответ при ошибке."""
        return (
            "❌ Произошла внутренняя ошибка.\n\n"
            "Попробуйте:\n"
            "1. Переформулировать запрос\n"
            "2. Использовать /reset для новой задачи\n"
            "3. Написать разработчикам если проблема повторяется\n\n"
            "⚠️  Контекст сохранён, можно продолжать диалог."
        )


# Глобальный экземпляр
_message_handler = MessageHandler()


def get_message_handler() -> MessageHandler:
    """Возвращает глобальный обработчик сообщений."""
    return _message_handler


def handle_message(user_id: str, text: str) -> str:
    """Упрощенный интерфейс для обработки сообщений."""
    return _message_handler.handle_message(user_id, text)