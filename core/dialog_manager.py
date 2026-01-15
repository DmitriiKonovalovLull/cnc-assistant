"""
УСИЛЕННЫЙ DIALOG MANAGER - жёсткий FSM, который НИКОГДА не теряет контекст
"""

from typing import Tuple, List, Dict, Any, Optional
from datetime import datetime
from .context import CuttingContext, DialogState
from .assumptions import AssumptionEngine
from .recommendations import ReasoningRecommender
from .calculator import CuttingCalculator
from .language import get_translator


class DialogManager:
    """Жёсткий FSM - ЕДИНСТВЕННЫЙ, кто меняет состояния."""

    def __init__(self):
        self.assumptions = AssumptionEngine()
        self.recommender = ReasoningRecommender()
        self.calculator = CuttingCalculator()
        self.translator = get_translator()

        # Журнал переходов для отладки
        self.transition_log = []

    def process(self, context: CuttingContext, parsed_data: dict, user_input: str) -> Tuple[str, DialogState]:
        """
        Обрабатывает ввод пользователя и возвращает (ответ, следующее_состояние).
        НИКОГДА не сбрасывает контекст!
        """
        current_state = context.active_step

        # Логируем входные данные
        self._log_transition(context, user_input, parsed_data, current_state)

        # 1. Обрабатываем специальные случаи (без изменения состояния!)
        special_response = self._handle_special_cases(context, user_input, parsed_data)
        if special_response:
            return special_response, current_state  # Остаёмся в том же состоянии!

        # 2. Обновляем контекст из распарсенных данных
        self._update_context_safely(context, parsed_data)

        # 3. Определяем следующее состояние
        next_state = self._determine_next_state(context, parsed_data, user_input)

        # 4. Применяем предположения если нужно
        assumption_messages = []
        if next_state in [DialogState.COLLECTING_CONTEXT, DialogState.PROCESSING_GOAL]:
            assumption_messages = self.assumptions.apply_assumptions(context)

        # 5. Генерируем ответ
        response = self._generate_response(
            context=context,
            current_state=current_state,
            next_state=next_state,
            parsed_data=parsed_data,
            user_input=user_input,
            assumption_messages=assumption_messages
        )

        # 6. Обновляем состояние ТОЛЬКО если оно изменилось
        if next_state != current_state:
            context.step_history.append(current_state)
            context.active_step = next_state

        # 7. Сохраняем ход разговора
        context.add_conversation_turn("user", user_input)
        context.add_conversation_turn("assistant", response)

        return response, next_state

    def _handle_special_cases(self, context: CuttingContext, user_input: str, parsed_data: dict) -> Optional[str]:
        """
        Обрабатывает специальные случаи, которые НЕ меняют состояние.
        """
        input_lower = user_input.lower().strip()

        # 1. /help - НЕ меняет состояние!
        if input_lower.startswith('/help'):
            return self._get_help_response(context)

        # 2. Обратная связь "где?", "не подходит" и т.д.
        feedback_phrases = [
            "где?", "не подходит", "нет, ", "не так", "исправь",
            "неправильно", "что-то не то", "другое", "не то"
        ]

        if any(phrase in input_lower for phrase in feedback_phrases):
            return self._handle_feedback(context, user_input)

        # 3. Уточняющие вопросы
        if any(word in input_lower for word in ["что", "как", "почему", "зачем"]):
            return self._handle_clarification(context, user_input)

        return None

    def _get_help_response(self, context: CuttingContext) -> str:
        """Возвращает справку НЕ меняя состояния."""
        # Помечаем, что справка показана
        context.mark_help_shown()

        help_text = (
            "🆘 **Справка - CNC Assistant**\n\n"

            "🤖 **Я помню контекст:**\n"
        )

        # Показываем, что бот помнит
        if context.material:
            help_text += f"• Материал: **{context.material}**\n"
        if context.operation:
            help_text += f"• Операция: **{context.operation}**\n"
        if context.current_diameter:
            help_text += f"• Диаметр: **Ø{context.current_diameter} мм**\n"
        if context.has_goal():
            help_text += f"• Цель: **с Ø{context.start_diameter} до Ø{context.target_diameter}**\n"

        help_text += (
            "\n💡 **Примеры запросов:**\n"
            "• `токарка алюминия диаметр 50`\n"
            "• `титан с 200 до 150 чистота 0.8`\n"
            "• `фрезеровка стали 45 чистовая`\n\n"

            "🔄 **Исправления:**\n"
            "• `нет, подача 0.3 слишком большая`\n"
            "• `исправь обороты на 1200`\n"
            "• `это много, сделай глубину 2`\n\n"

            "📚 **Команды:**\n"
            "/help - эта справка\n"
            "/reset - начать новую задачу\n"
            "/context - что я помню\n\n"

            f"⚙️ **Текущее состояние:** {context.active_step.name}\n"
            "➡️ **Продолжаем диалог там, где остановились.**"
        )

        return help_text

    def _handle_feedback(self, context: CuttingContext, user_input: str) -> str:
        """Обрабатывает отрицательную обратную связь."""
        input_lower = user_input.lower()

        # Анализируем, что именно не подходит
        if "подач" in input_lower or "feed" in input_lower:
            return "Понял, не подходит подача. Какую подачу поставить?"
        elif "оборот" in input_lower or "скорость" in input_lower or "rpm" in input_lower:
            return "Понял, не подходят обороты. Какие обороты поставить?"
        elif "глубин" in input_lower or "depth" in input_lower:
            return "Понял, не подходит глубина резания. Какую глубину поставить?"
        elif "инструмент" in input_lower or "tool" in input_lower:
            return "Понял, не подходит инструмент. Какой инструмент использовать?"
        else:
            return "Понял, что-то не подходит. Уточните: подача, обороты, глубина или инструмент?"

    def _handle_clarification(self, context: CuttingContext, user_input: str) -> str:
        """Обрабатывает уточняющие вопросы."""
        input_lower = user_input.lower()

        if "что" in input_lower and "делать" in input_lower:
            return "Нужно уточнить: какой материал обрабатываем и что с ним делаем?"

        if "как" in input_lower and ("рассчит" in input_lower or "счита" in input_lower):
            return "Я рассчитываю режимы на основе правил обработки материалов. Если что-то не так — поправьте!"

        return "Можете уточнить вопрос? Например: 'какую подачу поставить?' или 'какие обороты?'"

    def _update_context_safely(self, context: CuttingContext, parsed_data: dict):
        """Безопасно обновляет контекст из распарсенных данных."""

        # Материал
        if 'material' in parsed_data and parsed_data['material']:
            if not context.material or parsed_data.get('material_confidence', 0) > context.confidence.get('material',
                                                                                                          0):
                context.material = parsed_data['material']
                context.confidence['material'] = parsed_data.get('material_confidence', 0.9)

        # Операция
        if 'operation' in parsed_data and parsed_data['operation']:
            if not context.operation or parsed_data.get('operation_confidence', 0) > context.confidence.get('operation',
                                                                                                            0):
                context.operation = parsed_data['operation']
                context.confidence['operation'] = parsed_data.get('operation_confidence', 0.9)

        # Диаметры (особая логика!)
        if 'diameter' in parsed_data and parsed_data['diameter'] is not None:
            try:
                dia = float(parsed_data['diameter'])

                # Ищем указание цели (X → Y)
                if '→' in parsed_data.get('original_text', '') or 'до' in parsed_data.get('original_text', ''):
                    # Это указание цели: X до Y
                    if not context.start_diameter:
                        context.start_diameter = dia
                    else:
                        context.target_diameter = dia
                        context.current_diameter = dia
                else:
                    # Просто диаметр
                    context.current_diameter = dia
                    if not context.start_diameter:
                        context.start_diameter = dia

            except (ValueError, TypeError):
                pass

        # Чистота поверхности
        if 'surface_roughness' in parsed_data and parsed_data['surface_roughness']:
            try:
                context.surface_roughness = float(parsed_data['surface_roughness'])
                if "finishing" not in context.modes:
                    context.modes.append("finishing")
                context.active_mode = "finishing"
            except (ValueError, TypeError):
                pass

        # Режимы
        if 'modes' in parsed_data and parsed_data['modes']:
            for mode in parsed_data['modes']:
                if mode not in context.modes:
                    context.modes.append(mode)

        # Другие параметры
        for param in ['depth_of_cut', 'cutting_length', 'overhang', 'width']:
            if param in parsed_data and parsed_data[param] is not None:
                try:
                    value = float(parsed_data[param])
                    setattr(context, param, value)
                except (ValueError, TypeError):
                    pass

    def _determine_next_state(self, context: CuttingContext, parsed_data: dict, user_input: str) -> DialogState:
        """Определяет следующее состояние FSM."""
        current_state = context.active_step

        # ЖЁСТКОЕ ПРАВИЛО: если есть цель → сразу к обработке цели
        if context.has_goal() and current_state in [DialogState.WAITING_START, DialogState.COLLECTING_CONTEXT]:
            return DialogState.PROCESSING_GOAL

        # ЖЁСТКОЕ ПРАВИЛО: если достаточно данных → рекомендация
        if context.has_enough_for_recommendation() and current_state in [DialogState.COLLECTING_CONTEXT,
                                                                         DialogState.PROCESSING_GOAL]:
            return DialogState.RECOMMENDING

        # Определяем переходы
        if current_state == DialogState.WAITING_START:
            # Если есть хоть какие-то данные → собираем контекст
            if parsed_data.get('material') or parsed_data.get('operation') or context.material or context.operation:
                return DialogState.COLLECTING_CONTEXT
            return DialogState.WAITING_START

        elif current_state == DialogState.COLLECTING_CONTEXT:
            if context.has_goal():
                return DialogState.PROCESSING_GOAL
            elif context.has_enough_for_recommendation():
                return DialogState.RECOMMENDING
            elif context.get_missing_fields():
                return DialogState.COLLECTING_CONTEXT
            else:
                return DialogState.COLLECTING_CONTEXT

        elif current_state == DialogState.PROCESSING_GOAL:
            # Цель обработана → рекомендация
            return DialogState.RECOMMENDING

        elif current_state == DialogState.RECOMMENDING:
            # Получили обратную связь → обрабатываем
            if any(phrase in user_input.lower() for phrase in ["где?", "не подходит", "нет, ", "не так"]):
                return DialogState.AWAITING_FEEDBACK
            # Рекомендация дана → завершение
            elif len(context.recommendations_given) > 0:
                return DialogState.COMPLETED
            else:
                return DialogState.RECOMMENDING

        elif current_state == DialogState.AWAITING_FEEDBACK:
            # Получили уточнение → перерасчёт
            if parsed_data.get('material') or parsed_data.get('operation') or parsed_data.get('diameter'):
                return DialogState.RECOMMENDING
            else:
                return DialogState.AWAITING_FEEDBACK

        elif current_state == DialogState.COMPLETED:
            # Новый запрос → начинаем заново
            if parsed_data.get('material') or parsed_data.get('operation'):
                return DialogState.COLLECTING_CONTEXT
            else:
                return DialogState.COMPLETED

        # Если не нашли переходов → остаёмся в текущем состоянии
        return current_state

    def _generate_response(self, context: CuttingContext, current_state: DialogState,
                           next_state: DialogState, parsed_data: dict,
                           user_input: str, assumption_messages: List[str]) -> str:
        """Генерирует ответ на основе состояния."""

        # Собираем все части ответа
        response_parts = []

        # 1. Сообщения о предположениях
        if assumption_messages:
            response_parts.extend(assumption_messages)

        # 2. Основной ответ в зависимости от следующего состояния
        if next_state == DialogState.WAITING_START:
            if not context.material and not context.operation:
                return "Какой материал обрабатываем?"
            else:
                # Уже что-то знаем, но не всё
                return self._ask_for_missing(context)

        elif next_state == DialogState.COLLECTING_CONTEXT:
            return self._acknowledge_and_continue(context, parsed_data)

        elif next_state == DialogState.PROCESSING_GOAL:
            return self._acknowledge_goal(context)

        elif next_state == DialogState.RECOMMENDING:
            return self._give_recommendation(context)

        elif next_state == DialogState.AWAITING_FEEDBACK:
            return self._ask_for_feedback(context, user_input)

        elif next_state == DialogState.COMPLETED:
            return self._complete_dialog(context)

        # Если состояние не изменилось
        if next_state == current_state:
            # Повторяем последний вопрос или даём подсказку
            last_assistant = next(
                (msg for msg in reversed(context.conversation_history)
                 if msg.get("role") == "assistant"),
                None
            )
            if last_assistant:
                return f"({context.active_step.name}) {last_assistant.get('content', 'Продолжаем?')}"

        return "Продолжаем?"

    def _ask_for_missing(self, context: CuttingContext) -> str:
        """Спрашивает недостающие данные."""
        missing = context.get_missing_fields()

        if not missing:
            return "Кажется, у меня есть все данные. Что дальше?"

        questions = []
        if "материал" in missing and not context.material:
            questions.append("Какой материал обрабатываем?")
        if "операция" in missing and not context.operation:
            questions.append("Какая операция? (токарка, фрезеровка, расточка)")
        if "диаметр" in missing and not context.current_diameter:
            questions.append("Какой диаметр?")

        if len(questions) == 1:
            return questions[0]
        else:
            return "\n".join(questions)

    def _acknowledge_and_continue(self, context: CuttingContext, parsed_data: dict) -> str:
        """Подтверждает полученные данные и продолжает."""
        acknowledged = []

        if parsed_data.get('material'):
            acknowledged.append(f"Материал: **{parsed_data['material']}**")
        if parsed_data.get('operation'):
            acknowledged.append(f"Операция: **{parsed_data['operation']}**")
        if parsed_data.get('diameter'):
            acknowledged.append(f"Диаметр: **Ø{parsed_data['diameter']} мм**")

        if acknowledged:
            response = "✅ Запомнил: " + ", ".join(acknowledged)

            # Спрашиваем следующее
            missing = context.get_missing_fields()
            if missing:
                response += "\n\n" + self._ask_for_missing(context)

            return response

        return "Продолжаем?"

    def _acknowledge_goal(self, context: CuttingContext) -> str:
        """Подтверждает понимание цели обработки."""
        if not context.has_goal():
            return "Какую цель обработки вы ставите?"

        removal = self._get_removal_amount(context.start_diameter, context.target_diameter)
        is_finishing = context.is_finishing_operation()

        response = (
            f"🎯 **Понял цель:**\n\n"
            f"• Материал: **{context.material}**\n"
            f"• Операция: **{context.operation}**\n"
            f"• Цель: **с Ø{context.start_diameter} до Ø{context.target_diameter} мм**\n"
            f"• Припуск: **{removal:.1f} мм** на сторону\n"
        )

        if context.surface_roughness:
            response += f"• Требуемая чистота: **Ra {context.surface_roughness}**\n"

        response += f"\nЭто **{'чистовая' if is_finishing else 'черновая'}** обработка.\n\n"

        if is_finishing:
            response += "Рассчитываю режимы для чистовой обработки..."
        else:
            response += "Рассчитываю режимы для черновой обработки..."

        return response

    def _get_removal_amount(self, start_dia: Optional[float], target_dia: Optional[float]) -> float:
        """Рассчитывает припуск на сторону."""
        if start_dia and target_dia:
            return (start_dia - target_dia) / 2
        return 0.0

    def _give_recommendation(self, context: CuttingContext) -> str:
        """Даёт рекомендации."""
        # Отмечаем, что рекомендация дана
        mode_type = "finishing" if context.is_finishing_operation() else "roughing"
        context.recommendations_given.append(mode_type)

        # Получаем рекомендации
        recommendation = self.recommender.get_recommendation(context)

        # Формируем заголовок
        if context.has_goal():
            header = f"🎯 **Рекомендации для достижения цели:**"
        else:
            header = f"⚙️ **Рекомендации по режимам:**"

        response = f"{header}\n\n{recommendation}\n\n"

        # Добавляем вопросы для обратной связи
        response += "**Всё подходит?** Если нет — просто скажите что исправить."

        return response

    def _ask_for_feedback(self, context: CuttingContext, user_input: str) -> str:
        """Спрашивает обратную связь."""
        return "Что именно не подходит: подача, обороты или глубина резания?"

    def _complete_dialog(self, context: CuttingContext) -> str:
        """Завершает диалог."""
        context.complete_dialog()

        return (
            "✅ **Задача решена!**\n\n"
            "Если нужно что-то ещё — просто напишите.\n"
            "Для новой задачи используйте /reset"
        )

    def _log_transition(self, context: CuttingContext, user_input: str,
                        parsed_data: dict, current_state: DialogState):
        """Логирует переходы для отладки."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": context.user_id,
            "input": user_input,
            "parsed": {k: v for k, v in parsed_data.items() if v is not None},
            "from_state": current_state.name,
            "context_snapshot": {
                "material": context.material,
                "operation": context.operation,
                "diameter": context.current_diameter,
                "has_goal": context.has_goal(),
                "has_enough": context.has_enough_for_recommendation()
            }
        }
        self.transition_log.append(log_entry)

        # Ограничиваем размер лога
        if len(self.transition_log) > 100:
            self.transition_log = self.transition_log[-50:]


# ======================
# УПРОЩЕННАЯ ВЕРСИЯ ДЛЯ ТЕСТИРОВАНИЯ
# ======================

class SimpleDialogManager:
    """Упрощенный DialogManager для быстрого старта."""

    def __init__(self):
        self.translator = get_translator()

    def process(self, context: CuttingContext, parsed_data: dict, user_input: str) -> Tuple[str, DialogState]:
        """Упрощенная обработка для Дня 1."""

        # Обновляем контекст
        if parsed_data.get('material'):
            context.material = parsed_data['material']
        if parsed_data.get('operation'):
            context.operation = parsed_data['operation']
        if parsed_data.get('diameter'):
            try:
                context.current_diameter = float(parsed_data['diameter'])
            except:
                pass

        # Определяем следующее состояние
        current_state = context.active_step

        if current_state == DialogState.WAITING_START:
            if context.material or context.operation:
                next_state = DialogState.COLLECTING_CONTEXT
                response = self._acknowledge_data(context, parsed_data)
            else:
                next_state = DialogState.WAITING_START
                response = "Какой материал обрабатываем?"

        elif current_state == DialogState.COLLECTING_CONTEXT:
            if context.has_enough_for_recommendation():
                next_state = DialogState.RECOMMENDING
                response = self._give_simple_recommendation(context)
            else:
                next_state = DialogState.COLLECTING_CONTEXT
                response = self._ask_for_missing_simple(context)

        elif current_state == DialogState.RECOMMENDING:
            next_state = DialogState.COMPLETED
            response = "✅ Рекомендации даны. Для новой задачи используйте /reset"

        else:
            next_state = current_state
            response = "Продолжаем?"

        # Обновляем состояние
        if next_state != current_state:
            context.step_history.append(current_state)
            context.active_step = next_state

        # Сохраняем историю
        context.add_conversation_turn("user", user_input)
        context.add_conversation_turn("assistant", response)

        return response, next_state

    def _acknowledge_data(self, context: CuttingContext, parsed_data: dict) -> str:
        """Подтверждает полученные данные."""
        parts = []
        if parsed_data.get('material'):
            parts.append(f"Материал: **{parsed_data['material']}**")
        if parsed_data.get('operation'):
            parts.append(f"Операция: **{parsed_data['operation']}**")
        if parsed_data.get('diameter'):
            parts.append(f"Диаметр: **Ø{parsed_data['diameter']} мм**")

        if parts:
            response = "✅ Запомнил: " + ", ".join(parts)

            # Спрашиваем недостающее
            missing = []
            if not context.material:
                missing.append("материал")
            if not context.operation:
                missing.append("операцию")
            if not context.current_diameter:
                missing.append("диаметр")

            if missing:
                response += f"\n\nЧто ещё нужно? ({', '.join(missing)})"

            return response

        return "Что дальше?"

    def _ask_for_missing_simple(self, context: CuttingContext) -> str:
        """Спрашивает недостающие данные."""
        if not context.material:
            return "Какой материал?"
        elif not context.operation:
            return "Какая операция? (токарка/фрезеровка)"
        elif not context.current_diameter:
            return "Какой диаметр?"
        else:
            return "Готов дать рекомендации. Продолжаем?"

    def _give_simple_recommendation(self, context: CuttingContext) -> str:
        """Даёт простые рекомендации."""
        if context.material == "алюминий":
            speed = "250-350 м/мин"
            feed = "0.2-0.4 мм/об"
            notes = "Используйте острый инструмент"
        elif context.material == "сталь":
            speed = "80-150 м/мин"
            feed = "0.1-0.3 мм/об"
            notes = "Требуется охлаждение"
        elif context.material == "титан":
            speed = "40-80 м/мин"
            feed = "0.08-0.15 мм/об"
            notes = "Малая подача, обязательно охлаждение"
        else:
            speed = "100-200 м/мин"
            feed = "0.1-0.2 мм/об"
            notes = "Базовые рекомендации"

        return (
            f"⚙️ **Рекомендации для {context.material}:**\n\n"
            f"• Скорость резания: **{speed}**\n"
            f"• Подача: **{feed}**\n"
            f"• Примечания: {notes}\n\n"
            f"**Если что-то не подходит — скажите!**"
        )
