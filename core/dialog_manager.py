# core/dialog_manager.py
from typing import Tuple, List
from .context import CuttingContext, DialogState
from .assumptions import AssumptionEngine
from .recommendations import ReasoningRecommender
from .calculator import CuttingCalculator
from .language import get_translator


class DialogManager:
    """Управляет FSM диалога."""

    def __init__(self):
        self.assumptions = AssumptionEngine()
        self.recommender = ReasoningRecommender()
        self.calculator = CuttingCalculator()
        self.translator = get_translator()

    def process_step(self, context: CuttingContext, parsed_data: dict) -> Tuple[str, DialogState]:
        """
        Обрабатывает текущий шаг и возвращает ответ + следующее состояние.
        """
        current_state = context.active_step

        # Применяем предположения
        assumption_messages = self.assumptions.apply_assumptions(context)

        # Определяем следующее состояние
        next_state = self._determine_next_state(context, parsed_data)

        # Генерируем ответ
        response = self._generate_response(
            context=context,
            current_state=current_state,
            next_state=next_state,
            parsed_data=parsed_data,
            assumption_messages=assumption_messages
        )

        # Обновляем контекст
        context.active_step = next_state
        context.step_history.append(current_state)

        return response, next_state

    def _determine_next_state(self, context: CuttingContext, parsed_data: dict) -> DialogState:
        """Определяет следующее состояние FSM."""

        # Если пользователь явно запросил расчет
        if parsed_data.get('is_calculation_request'):
            return DialogState.COMPLETED  # Специальная ветка

        # FSM переходы
        if context.active_step == DialogState.WAITING_START:
            if context.material or parsed_data.get('material'):
                return DialogState.COLLECTING_CONTEXT
            return DialogState.WAITING_START

        elif context.active_step == DialogState.COLLECTING_CONTEXT:
            missing = self._get_missing_fields(context)
            if missing:
                return DialogState.CLARIFYING_MISSING
            elif context.modes:
                return DialogState.SETTING_ACTIVE_MODE
            else:
                return DialogState.COLLECTING_CONTEXT

        elif context.active_step == DialogState.CLARIFYING_MISSING:
            if self._has_minimum_data(context):
                return DialogState.SETTING_ACTIVE_MODE
            return DialogState.CLARIFYING_MISSING

        elif context.active_step == DialogState.SETTING_ACTIVE_MODE:
            if context.active_mode:
                mode_type = "roughing" if "чернов" in context.active_mode else "finishing"
                return DialogState.RECOMMENDING_ROUGHING if mode_type == "roughing" else DialogState.RECOMMENDING_FINISHING
            return DialogState.SETTING_ACTIVE_MODE

        elif context.active_step == DialogState.RECOMMENDING_ROUGHING:
            if "черновая" in context.recommendations_given and "чистовая" in context.modes:
                return DialogState.RECOMMENDING_FINISHING
            return DialogState.AWAITING_FEEDBACK

        elif context.active_step == DialogState.RECOMMENDING_FINISHING:
            return DialogState.AWAITING_FEEDBACK

        elif context.active_step == DialogState.AWAITING_FEEDBACK:
            return DialogState.COMPLETED

        return DialogState.WAITING_START

    def _generate_response(self, context, current_state, next_state, parsed_data, assumption_messages):
        """Генерирует ответ на основе состояния."""

        response_parts = []

        # Добавляем сообщения о предположениях
        if assumption_messages:
            response_parts.extend(assumption_messages)

        # Генерируем основной ответ
        if next_state == DialogState.WAITING_START:
            return self.translator.translate("what_material", "Какой материал обрабатываем?")

        elif next_state == DialogState.CLARIFYING_MISSING:
            missing = self._get_missing_fields(context)
            questions = []
            if "material" in missing:
                questions.append(self.translator.translate("what_material", "Какой материал?"))
            if "operation" in missing:
                questions.append(self.translator.translate("what_operation", "Какая операция?"))
            return "\n".join(questions)

        elif next_state == DialogState.SETTING_ACTIVE_MODE:
            if context.modes:
                return self.translator.translate("choose_mode", f"Выберите режим: {', '.join(context.modes)}")
            return self.translator.translate("what_mode", "Какой режим обработки?")

        elif next_state == DialogState.RECOMMENDING_ROUGHING:
            recommendation = self.recommender.get_recommendation(context, "roughing")
            response_parts.append(recommendation)

        elif next_state == DialogState.RECOMMENDING_FINISHING:
            recommendation = self.recommender.get_recommendation(context, "finishing")
            response_parts.append(recommendation)

        elif next_state == DialogState.AWAITING_FEEDBACK:
            return self.translator.translate("feedback_question", "Всё подходит или нужны корректировки?")

        return "\n\n".join(response_parts) if response_parts else self.translator.translate("continue", "Продолжаем?")

    def _get_missing_fields(self, context: CuttingContext) -> List[str]:
        """Возвращает список недостающих полей."""
        missing = []
        if not context.material:
            missing.append("material")
        if not context.operation:
            missing.append("operation")
        return missing

    def _has_minimum_data(self, context: CuttingContext) -> bool:
        """Проверяет, достаточно ли данных."""
        return bool(context.material and context.operation)