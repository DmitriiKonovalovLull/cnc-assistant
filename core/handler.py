"""
Интеллектуальный обработчик с мультиязычностью, памятью и обучением.
"""

from typing import Optional, Dict, Any, List
from core.context import get_user_context, DialogState, context_manager
from core.parser import IntelligentParser
from core.dialog_manager import DialogManager
from core.calculator import CuttingCalculator
from core.language import set_language, get_translator
from core.memory.memory_manager import MemoryManager, ContextWithMemory


class IntelligentHandler:
    """Обработчик с мультиязычностью, FSM и долговременной памятью."""

    def __init__(self):
        self.parser = IntelligentParser()
        self.dialog_manager = DialogManager()
        self.calculator = CuttingCalculator()
        self.translator = get_translator()
        self.memory_manager = MemoryManager()

        # Кэш для быстрого доступа к памяти пользователей
        self._user_memory_wrappers: Dict[str, ContextWithMemory] = {}

    def handle_message(self, user_id: str, text: str) -> str:
        """Обрабатывает сообщение с памятью и обучением."""
        try:
            # Получаем контекст с памятью
            context_wrapper = self._get_context_with_memory(user_id)
            context = context_wrapper.context

            print(f"\n{'=' * 50}")
            print(f"Обработка для пользователя: {user_id}")
            print(f"Сообщение: {text}")
            print(f"Текущее состояние: {context.active_step.name}")

            # Парсим сообщение
            parsed = self.parser.parse(text)
            print(f"Парсинг: {parsed}")

            # Устанавливаем язык
            self._set_language_from_parsed(parsed)

            # Добавляем сообщение в историю
            context.add_conversation_turn("user", text)

            # Проверяем специальные команды
            special_response = self._check_special_commands(user_id, text, parsed)
            if special_response:
                context.add_conversation_turn("assistant", special_response)
                return special_response

            # Применяем персонализированные предложения из памяти
            self._apply_learned_patterns(context_wrapper)

            # Обрабатываем запросы на расчет
            if parsed.get('is_calculation_request') or parsed.get('intent') == 'get_calculation':
                response = self._handle_calculation_request_with_memory(user_id, parsed, context)
                context.add_conversation_turn("assistant", response)

                # Логируем успешный расчет
                if "🧮" in response or "🔢" in response or "⚙️" in response:
                    self._log_successful_calculation(user_id, context, parsed, response)

                return response

            # Обновляем контекст из распарсенных данных
            self._update_context_with_memory(context, parsed, context_wrapper)

            # Обрабатываем через DialogManager
            response, next_state = self.dialog_manager.process_step(context, parsed)

            # Проверяем наличие исправлений в ответе пользователя
            corrections = self._extract_corrections_from_response(text, response, context)
            if corrections:
                self._log_corrections(user_id, corrections, context)

            # Добавляем персонализацию в ответ
            response = self._personalize_response(response, context_wrapper)

            # Добавляем ответ в историю
            context.add_conversation_turn("assistant", response)

            # Сохраняем если были изменения
            if context.is_dirty():
                from core.context import save_user_context
                save_user_context(user_id)

            # Логируем завершение диалога если нужно
            if next_state == DialogState.COMPLETED:
                self._log_completed_dialog(user_id, context, response)

            print(f"Ответ: {response[:100]}...")
            print(f"Следующее состояние: {next_state.name}")
            print(f"{'=' * 50}\n")

            return response

        except Exception as e:
            print(f"Ошибка в обработчике: {e}")
            import traceback
            traceback.print_exc()
            return self.translator.translate("error_restart",
                                             "Что-то пошло не так. Начнем заново? /start")

    def _get_context_with_memory(self, user_id: str) -> ContextWithMemory:
        """Получает контекст с оберткой памяти."""
        if user_id not in self._user_memory_wrappers:
            context = get_user_context(user_id)
            context_wrapper = ContextWithMemory(user_id)
            context_wrapper.context = context
            self._user_memory_wrappers[user_id] = context_wrapper
        return self._user_memory_wrappers[user_id]

    def _set_language_from_parsed(self, parsed: Dict[str, Any]):
        """Устанавливает язык из распарсенных данных."""
        if 'detected_language' in parsed:
            set_language(parsed['detected_language'])
            print(f"DEBUG: Установлен язык: {parsed['detected_language']}")

        if 'language' in parsed:
            set_language(parsed['language'])
            print(f"DEBUG: Установлен язык по команде: {parsed['language']}")

    def _check_special_commands(self, user_id: str, text: str, parsed: Dict[str, Any]) -> Optional[str]:
        """Проверяет специальные команды."""
        text_lower = text.lower().strip()

        # Сброс контекста
        if text_lower == '/reset' or text_lower == 'сброс':
            from core.context import reset_user_context
            reset_user_context(user_id)

            # Очищаем кэш
            if user_id in self._user_memory_wrappers:
                del self._user_memory_wrappers[user_id]

            return self.translator.translate("reset_success",
                                             "✅ Контекст сброшен. Начнём новую задачу.\n\nКакой материал обрабатываем?")

        # Показать историю
        elif text_lower == '/history' or text_lower == 'история':
            return self._show_user_history(user_id)

        # Показать статистику
        elif text_lower == '/stats' or text_lower == 'статистика':
            return self._show_user_stats(user_id)

        # Помощь
        elif text_lower == '/help' or text_lower == 'помощь':
            return self._show_help()

        return None

    def _apply_learned_patterns(self, context_wrapper: ContextWithMemory):
        """Применяет изученные паттерны из памяти."""
        context = context_wrapper.context

        # Получаем персонализированные предложения
        suggestions = context_wrapper.get_personalized_suggestions()

        for param, suggestion in suggestions.items():
            if suggestion["confidence"] > 0.7:  # Высокая уверенность
                if hasattr(context, param):
                    current_value = getattr(context, param)

                    # Применяем только если поле пустое или уверенность выше
                    current_conf = context.confidence.get(param, 0.0)
                    if not current_value or suggestion["confidence"] > current_conf:
                        # Формируем причину
                        source_map = {
                            "user_history": "вашей истории использования",
                            "similar_cases": "похожих случаев",
                            "global_pattern": "общих паттернов"
                        }
                        reason = f"На основе {source_map.get(suggestion.get('source', ''), 'истории')}"

                        context.update_field(
                            param,
                            suggestion["value"],
                            source="memory",
                            confidence=suggestion["confidence"],
                            reason=reason
                        )

                        print(f"Применен паттерн из памяти: {param} = {suggestion['value']} "
                              f"(уверенность: {suggestion['confidence']:.0%})")

    def _update_context_with_memory(self, context, parsed: Dict[str, Any],
                                    context_wrapper: ContextWithMemory):
        """Обновляет контекст с учетом памяти."""

        # Материал
        if 'material' in parsed and parsed['material']:
            material = parsed['material']

            # Проверяем, есть ли у пользователя предпочтения по этому материалу
            user_memory = self.memory_manager.get_user_memory(context.user_id)
            material_count = user_memory.preferred_materials.get(material, 0)

            # Повышаем уверенность если материал часто используется
            base_confidence = parsed.get('material_confidence', 0.9)
            if material_count > 0:
                bonus = min(0.1, material_count * 0.02)
                base_confidence = min(1.0, base_confidence + bonus)

            if not context.material or context.confidence.get('material', 0) < base_confidence:
                context.update_field(
                    "material",
                    material,
                    source="user",
                    confidence=base_confidence
                )

        # Операция
        if 'operation' in parsed and parsed['operation']:
            operation = parsed['operation']

            # Аналогично для операции
            user_memory = self.memory_manager.get_user_memory(context.user_id)
            operation_count = user_memory.preferred_operations.get(operation, 0)

            base_confidence = parsed.get('operation_confidence', 0.9)
            if operation_count > 0:
                bonus = min(0.1, operation_count * 0.02)
                base_confidence = min(1.0, base_confidence + bonus)

            if not context.operation or context.confidence.get('operation', 0) < base_confidence:
                context.update_field(
                    "operation",
                    operation,
                    source="user",
                    confidence=base_confidence
                )

        # Режимы обработки
        if 'modes' in parsed and parsed['modes']:
            for mode in parsed['modes']:
                if mode not in context.modes:
                    context.modes.append(mode)
                    context.confidence['modes'] = parsed.get('modes_confidence', 0.8)

        # Числовые параметры с учетом типичных значений
        for param in ['diameter', 'overhang', 'width', 'depth', 'depth_of_cut']:
            if param in parsed and parsed[param] is not None:
                try:
                    value = float(parsed[param])

                    # Проверяем типичное значение пользователя
                    typical_value = context_wrapper.user_memory.get_typical_value(param)
                    if typical_value and abs(value - typical_value) / typical_value < 0.3:
                        # Значение близко к типичному - повышаем уверенность
                        confidence = 0.9
                    else:
                        confidence = 0.8

                    if not getattr(context, param, None):
                        context.update_field(
                            param,
                            value,
                            source="user",
                            confidence=confidence
                        )
                except (ValueError, TypeError):
                    pass

        # Инструмент
        if 'tool' in parsed and parsed['tool']:
            context.update_field(
                "tool",
                parsed['tool'],
                source="user",
                confidence=parsed.get('tool_confidence', 0.8)
            )

    def _handle_calculation_request_with_memory(self, user_id: str, parsed: Dict[str, Any],
                                                context) -> str:
        """Обрабатывает запрос на расчёт с учетом памяти."""

        # Получаем персонализированные предложения
        context_wrapper = self._get_context_with_memory(user_id)
        suggestions = context_wrapper.get_personalized_suggestions()

        # Обогащаем распарсенные данные предложениями из памяти
        enriched_parsed = parsed.copy()
        for param, suggestion in suggestions.items():
            if suggestion["confidence"] > 0.8 and param not in enriched_parsed:
                enriched_parsed[param] = suggestion["value"]
                enriched_parsed[f"{param}_confidence"] = suggestion["confidence"]
                print(f"Добавлено из памяти: {param} = {suggestion['value']}")

        # Выполняем расчет
        return self._handle_calculation_request(enriched_parsed)

    def _handle_calculation_request(self, parsed: Dict[str, Any]) -> str:
        """Обрабатывает запрос на расчёт (базовая логика)."""
        # [Ваш существующий код _handle_calculation_request]
        # ... (оставляем как есть)

        # Для примера:
        diameter = parsed.get('diameter')
        material = parsed.get('material', 'сталь')

        if diameter and material:
            # Упрощенный расчет для примера
            result = {
                "material": material,
                "diameter": diameter,
                "recommended_rpm": 1000,
                "recommended_feed": 0.2,
                "cutting_speed": 150,
                "notes": ["Расчет с учетом данных из памяти"]
            }
            return self._format_calculation_result(result, "general")

        return "Не хватает данных для расчета."

    def _extract_corrections_from_response(self, user_text: str, bot_response: str,
                                           context) -> List[Dict[str, Any]]:
        """Извлекает исправления из ответа пользователя."""
        corrections = []

        # Простые паттерны для обнаружения исправлений
        correction_patterns = [
            (r'нет\s*,?\s*(\w+)\s*(\d+\.?\d*)', "value_correction"),
            (r'исправь\s+(\w+)\s+на\s+(\d+\.?\d*)', "value_correction"),
            (r'(\w+)\s+(\d+\.?\d*)\s+-\s+это\s+много', "value_too_high"),
            (r'(\w+)\s+(\d+\.?\d*)\s+-\s+это\s+мало', "value_too_low"),
        ]

        for pattern, correction_type in correction_patterns:
            import re
            matches = re.findall(pattern, user_text.lower())
            for match in matches:
                if len(match) == 2:
                    param, value = match

                    # Пытаемся понять, какое значение исправляется
                    # Ищем числа в предыдущем ответе бота
                    bot_numbers = re.findall(r'\d+\.?\d*', bot_response)

                    if bot_numbers:
                        wrong_value = float(bot_numbers[-1]) if bot_numbers else None
                        correct_value = float(value)

                        correction = {
                            "wrong": {param: wrong_value},
                            "correct": {param: correct_value},
                            "type": correction_type,
                            "context": context.to_dict()
                        }
                        corrections.append(correction)

        return corrections

    def _log_corrections(self, user_id: str, corrections: List[Dict[str, Any]], context):
        """Логирует исправления от пользователя."""
        for correction in corrections:
            self.memory_manager.log_correction(
                user_id,
                correction["wrong"],
                correction["correct"],
                correction.get("context", {})
            )

            print(f"Записано исправление: {correction['wrong']} -> {correction['correct']}")

    def _log_successful_calculation(self, user_id: str, context, parsed: Dict[str, Any],
                                    response: str):
        """Логирует успешный расчет для обучения."""
        # Собираем параметры расчета
        calculation_params = {}
        for param in ['diameter', 'overhang', 'width', 'depth', 'depth_of_cut', 'material', 'operation']:
            if param in parsed and parsed[param]:
                calculation_params[param] = parsed[param]
            elif hasattr(context, param) and getattr(context, param):
                calculation_params[param] = getattr(context, param)

        # Логируем как успешный диалог
        dialog_data = {
            "user_id": user_id,
            "context": context.to_dict(),
            "calculation_params": calculation_params,
            "response": response,
            "outcome": "successful_calculation",
            "timestamp": context.last_updated.isoformat()
        }

        # Сохраняем в памяти
        user_memory = self.memory_manager.get_user_memory(user_id)
        if "material" in calculation_params and "operation" in calculation_params:
            user_memory.update_preferences(
                calculation_params["material"],
                calculation_params["operation"],
                {k: v for k, v in calculation_params.items() if isinstance(v, (int, float))}
            )
            self.memory_manager._save_user_memory(user_memory)

        print(f"Записано успешный расчет в память пользователя {user_id}")

    def _log_completed_dialog(self, user_id: str, context, final_response: str):
        """Логирует завершенный диалог."""
        self.memory_manager.log_dialog(
            context,
            context.conversation_history,
            context.corrections_received,
            final_response
        )
        print(f"Завершенный диалог записан в память для пользователя {user_id}")

    def _personalize_response(self, response: str, context_wrapper: ContextWithMemory) -> str:
        """Добавляет персонализацию в ответ."""
        user_memory = context_wrapper.user_memory

        # Если у пользователя есть история
        if user_memory.total_dialogs > 0:
            favorite_material = user_memory.get_favorite_material()

            if favorite_material and "материал" in response.lower():
                personal_note = f"\n\n📝 *На заметку:* Вы чаще всего работаете с **{favorite_material}**."
                response += personal_note

            # Добавляем статистику если пользователь опытный
            if user_memory.total_dialogs > 5:
                stats_note = f"\n🎯 *Ваша статистика:* {user_memory.total_dialogs} диалогов, " \
                             f"{len(user_memory.corrections_history)} исправлений учтены."
                response += stats_note

        return response

    def _show_user_history(self, user_id: str) -> str:
        """Показывает историю пользователя."""
        user_memory = self.memory_manager.get_user_memory(user_id)

        if user_memory.total_dialogs == 0:
            return "📊 У вас пока нет истории взаимодействий."

        # Самый частый материал
        favorite_material = user_memory.get_favorite_material()
        material_count = user_memory.preferred_materials.get(favorite_material, 0) if favorite_material else 0

        # Самый частый операция
        favorite_operation = max(user_memory.preferred_operations.items(),
                                 key=lambda x: x[1])[0] if user_memory.preferred_operations else "нет данных"
        operation_count = user_memory.preferred_operations.get(favorite_operation, 0)

        # Типичные параметры
        typical_diameter = user_memory.get_typical_value("diameter")
        typical_feed = user_memory.get_typical_value("feed")

        history_text = (
            f"📊 **Ваша история использования:**\n\n"
            f"• **Всего диалогов:** {user_memory.total_dialogs}\n"
            f"• **Первое использование:** {user_memory.first_seen.strftime('%d.%m.%Y')}\n"
            f"• **Последняя активность:** {user_memory.last_seen.strftime('%d.%m.%Y %H:%M')}\n\n"

            f"**Предпочтения:**\n"
            f"• Чаще всего материал: **{favorite_material or 'нет данных'}** ({material_count} раз)\n"
            f"• Чаще всего операция: **{favorite_operation}** ({operation_count} раз)\n"
        )

        if typical_diameter:
            history_text += f"• Типичный диаметр: **Ø{typical_diameter:.1f} мм**\n"
        if typical_feed:
            history_text += f"• Типичная подача: **{typical_feed:.3f} мм/об**\n"

        history_text += f"\n**Исправления учтены:** {len(user_memory.corrections_history)}\n"

        if user_memory.custom_rules:
            history_text += f"\n**Ваши правила:** {len(user_memory.custom_rules)}\n"

        return history_text

    def _show_user_stats(self, user_id: str) -> str:
        """Показывает статистику пользователя."""
        from datetime import datetime

        user_memory = self.memory_manager.get_user_memory(user_id)

        days_active = (datetime.now() - user_memory.first_seen).days
        if days_active == 0:
            days_active = 1

        dialogs_per_day = user_memory.total_dialogs / days_active

        stats_text = (
            f"📈 **Статистика использования:**\n\n"
            f"• **Активность:** {days_active} дней\n"
            f"• **Среднее в день:** {dialogs_per_day:.1f} диалогов\n"
            f"• **Исправления/диалог:** {len(user_memory.corrections_history) / max(user_memory.total_dialogs, 1):.1f}\n\n"

            f"**Топ материалов:**\n"
        )

        # Топ 3 материала
        top_materials = sorted(user_memory.preferred_materials.items(),
                               key=lambda x: x[1], reverse=True)[:3]
        for material, count in top_materials:
            percentage = (count / user_memory.total_dialogs * 100) if user_memory.total_dialogs > 0 else 0
            stats_text += f"• {material}: {count} раз ({percentage:.0f}%)\n"

        stats_text += f"\n**Уровень опыта:** "
        if user_memory.total_dialogs > 20:
            stats_text += "🎓 Эксперт"
        elif user_memory.total_dialogs > 10:
            stats_text += "📚 Опытный"
        elif user_memory.total_dialogs > 3:
            stats_text += "📖 Начинающий"
        else:
            stats_text += "🆕 Новый пользователь"

        return stats_text

    def _show_help(self) -> str:
        """Показывает справку."""
        help_text = (
            "🆘 **Справка по командам:**\n\n"

            "**Основные команды:**\n"
            "• /reset или 'сброс' - начать новую задачу\n"
            "• /history или 'история' - показать вашу историю\n"
            "• /stats или 'статистика' - показать статистику\n"
            "• /help или 'помощь' - эта справка\n\n"

            "**Примеры запросов:**\n"
            "• 'алюминий токарка черновая диаметр 50'\n"
            "• 'посчитай для стали 45 расточка'\n"
            "• 'фрезеровка титан фреза 12 мм'\n\n"

            "**Корректировки:**\n"
            "• 'нет, подача 0.3 слишком большая'\n"
            "• 'исправь скорость на 150'\n"
            "• 'это много, сделай глубину 2 мм'\n\n"

            "🤖 *Примечание:* Я запоминаю ваши предпочтения и становлюсь точнее со временем!"
        )

        return help_text


# ==================== ИНИЦИАЛИЗАЦИЯ ====================

# Создаем глобальный экземпляр обработчика
intelligent_handler = IntelligentHandler()


# Упрощенные функции для импорта
def handle_user_message(user_id: str, text: str) -> str:
    """Обрабатывает сообщение пользователя."""
    return intelligent_handler.handle_message(user_id, text)


def reset_user_dialog(user_id: str) -> str:
    """Сбрасывает диалог пользователя."""
    return intelligent_handler.handle_reset(user_id)