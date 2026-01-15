"""
Интеллектуальный обработчик с мультиязычностью.
"""

import re
import random
from core.context import get_context, reset_context
from core.parser import IntelligentParser
from core.assumptions import AssumptionEngine
from core.recommendations import ReasoningRecommender
from core.calculator import CuttingCalculator
from core.language import set_language, get_translator  # Новый импорт


class IntelligentHandler:
    """Обработчик с мультиязычностью."""

    def __init__(self):
        self.parser = IntelligentParser()
        self.assumptions = AssumptionEngine()
        self.recommender = ReasoningRecommender()
        self.calculator = CuttingCalculator()
        self.translator = get_translator()

    def handle_message(self, user_id, text):
        """Обрабатывает одно сообщение с учетом языка."""
        try:
            context = get_context(user_id)
            parsed = self.parser.parse(text)

            print(f"DEBUG: '{text}' -> {parsed}")

            # Устанавливаем язык если определили
            if 'detected_language' in parsed:
                set_language(parsed['detected_language'])
                print(f"DEBUG: Установлен язык: {parsed['detected_language']}")

            if 'language' in parsed:
                set_language(parsed['language'])
                print(f"DEBUG: Установлен язык по команде: {parsed['language']}")

            # Если это запрос на расчёт
            if parsed.get('is_calculation_request') or parsed.get('intent') == 'get_calculation':
                return self._handle_calculation_request(context, parsed, text)

            # Стандартная обработка
            if 'intent' in parsed:
                if parsed['intent'] == 'get_advice':
                    return self._handle_advice_request(context)

            # Обновление контекста
            self._update_context_smartly(context, parsed)

            # Применение предположений
            assumption_actions = self.assumptions.apply_assumptions(context)

            # Выполнение шага
            return self._execute_single_step(context, assumption_actions, text)

        except Exception as e:
            print(f"Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return self.translator.translate("error_restart", "Что-то пошло не так. Начнем заново? /start")

    def _handle_calculation_request(self, context, parsed, original_text):
        """Обрабатывает запрос на расчёт."""

        # Извлекаем параметры из парсера
        diameter = parsed.get('diameter')
        overhang = parsed.get('overhang')
        width = parsed.get('width')
        depth = parsed.get('depth')
        material = parsed.get('material', 'сталь')

        # Если есть все 4 параметра - делаем расчёт расточки
        if all(param is not None for param in [diameter, overhang, width, depth]):
            result = self.calculator.calculate_for_boring(
                diameter=diameter,
                overhang=overhang,
                width=width,
                depth=depth,
                material=material
            )

            # Форматируем с переводом
            calculation = self.translator.format_calculation(result)

            explanation = (
                    "🧮 **" + self.translator.translate("calculation_based_on", "Расчёт выполнен на основе") + ":**\n"
                                                                                                              "• " + self.translator.translate(
                "cutting_formulas", "Формул резания для расточных операций") + "\n"
                                                                               "• " + self.translator.translate(
                "rigidity_coefficients", "Коэффициентов жёсткости при большом вылете") + "\n"
                                                                                         "• " + self.translator.translate(
                "material_corrections", "Практических поправок для материала") + "\n"
                                                                                 "• " + self.translator.translate(
                "vibration_limits", "Ограничений по вибрациям") + "\n\n"
            )

            return explanation + calculation

        # Если только диаметр + материал - расчёт токарки
        elif diameter and material:
            # Создаём временный контекст
            class TempContext:
                def __init__(self):
                    self.material = material
                    self.operation = 'токарная'
                    self.active_mode = 'черновая'
                    self.diameter = str(diameter)
                    self.confidence = {'material': 0.9, 'operation': 0.9}

            temp_context = TempContext()
            result = self.calculator.calculate_for_turning(temp_context)

            if result:
                calculation = self.translator.format_calculation(result)

                explanation = (
                        f"🔢 **" + self.translator.translate("calculation_for", "Расчёт для") +
                        f" {self.translator.translate_material(material)}, Ø{diameter} мм:**\n\n"
                        "**" + self.translator.translate("calculation_basis", "Основа расчёта") + ":**\n"
                                                                                                  "• " + self.translator.translate(
                    "basic_cutting_speeds", "Базовые скорости резания для материала") + "\n"
                                                                                        f"• " + self.translator.translate(
                    "diameter_for_rpm", "Диаметр {diameter} мм для расчёта оборотов") + "\n"
                                                                                        "• " + self.translator.translate(
                    "standard_feeds", "Стандартные подачи для черновой обработки") + "\n\n"
                )

                return explanation + calculation

        # Не хватает данных
        return (
                "🧐 " + self.translator.translate("calculation_request_detected",
                                                 "Вижу запрос на расчёт, но нужно больше данных.") + "\n\n"
                                                                                                     "**" + self.translator.translate(
            "for_exact_calculation", "Для точного расчёта укажите") + ":**\n"
                                                                      "• **" + self.translator.translate("diameter",
                                                                                                         "Диаметр") + "** " + self.translator.translate(
            "hole_part", "отверстия/детали") + " (мм)\n"
                                               "• **" + self.translator.translate("material",
                                                                                  "Материал") + "** (титан, сталь, алюминий...)\n"
                                                                                                "• **" + self.translator.translate(
            "operation", "Операция") + "** (токарка, расточка, фрезеровка)\n\n"
                                       "**" + self.translator.translate("examples", "Примеры") + ":**\n"
                                                                                                 "• 'расточка диаметр 200 титан вылет 150'\n"
                                                                                                 "• 'посчитай для стали 45 диаметр 80'\n"
                                                                                                 "• 'какие обороты для алюминия 50 мм'"
        )

    def _update_context_smartly(self, context, parsed):
        """Обновляет контекст с учётом языка."""

        # Активируем диалог при любом сообщении
        context.is_dialog_active = True

        # Если контекст в состоянии завершения - сбрасываем его
        if context.active_step == "feedback":
            context.active_step = "processing"

        # Материал
        if 'material' in parsed and parsed['material']:
            if not context.material or context.confidence.get('material', 0) < 0.7:
                context.update("material", parsed['material'],
                               confidence=parsed.get('material_confidence', 0.9))

        # Операция
        if 'operation' in parsed and parsed['operation']:
            if not context.operation or context.confidence.get('operation', 0) < 0.7:
                context.update("operation", parsed['operation'],
                               confidence=parsed.get('operation_confidence', 0.9))

        # Режимы
        if 'modes' in parsed and parsed['modes']:
            for mode in parsed['modes']:
                if mode not in context.modes:
                    context.modes.append(mode)
                    context.confidence['modes'] = parsed.get('modes_confidence', 0.8)

        # Диаметр и другие параметры
        for param in ['diameter', 'overhang', 'width', 'depth']:
            if param in parsed and parsed[param] is not None:
                if not getattr(context, param, None):
                    setattr(context, param, parsed[param])

    def _execute_single_step(self, context, assumption_actions, original_text):
        """Выполняет один шаг с переводом."""

        next_step = context.move_to_next_step()
        print(f"DEBUG: Следующий шаг: {next_step}")

        if next_step == "waiting_start":
            return self.translator.translate("what_material", "Какой материал обрабатываем?")

        elif next_step == "clarify_missing":
            return self._clarify_missing(context, assumption_actions)

        elif next_step == "set_active_mode":
            return self._set_active_mode(context, assumption_actions)

        elif next_step.startswith("recommend_"):
            mode_type = "roughing" if "roughing" in next_step else "finishing"
            return self._give_recommendation(context, mode_type, assumption_actions)

        elif next_step == "feedback":
            return self._ask_for_feedback(context)

        return self.translator.translate("what_next", "Что дальше?")

    def _clarify_missing(self, context, assumption_actions):
        """Уточняет недостающие данные."""

        response_parts = []

        if assumption_actions:
            response_parts.append(" ".join(assumption_actions))

        if not context.material:
            response_parts.append(self.translator.translate("what_material", "Какой материал обрабатываем?"))

        elif not context.operation:
            response_parts.append(self.translator.translate("what_operation", "Какая операция? (токарка/фрезеровка)"))

        elif not context.modes and not assumption_actions:
            response_parts.append(self.translator.translate("what_mode", "Какой режим обработки?"))

        if len(response_parts) > 1:
            return "\n\n".join(response_parts)
        else:
            return response_parts[0] if response_parts else self.translator.translate("continue", "Продолжаем?")

    def _set_active_mode(self, context, assumption_actions):
        """Устанавливает активный режим."""

        if assumption_actions:
            base = " ".join(assumption_actions)
        elif context.modes:
            if 'черновая' in context.modes:
                context.active_mode = 'черновая'
                base = self.translator.translate("start_with_roughing", "Начнём с черновой обработки.")
            else:
                context.active_mode = context.modes[0]
                base = self.translator.translate("start_with_mode", f"Начнём с {context.active_mode} обработки.")
        else:
            base = self.translator.translate("what_mode_needed", "Какой режим обработки нужен?")

        return f"{base}\n\n{self.translator.translate('if_not_correct', 'Если не так — поправь.')}"

    def _give_recommendation(self, context, mode_type, assumption_actions):
        """Даёт рекомендации с переводом."""

        if context.active_mode:
            context.recommendations_given.append(context.active_mode)

        # Генерируем рекомендации
        recommendation = self.recommender.get_recommendation(context)

        response_parts = []

        if assumption_actions:
            response_parts.append(" ".join(assumption_actions))

        response_parts.append(recommendation)

        # Добавляем возможность расчёта
        if context.diameter:
            try:
                dia = float(str(context.diameter).replace(',', '.'))
                if dia > 0:
                    response_parts.append(
                        f"\n📊 **{self.translator.translate('can_calculate', 'Могу сделать точный расчёт для')} Ø{dia} мм.**\n"
                        f"{self.translator.translate('write_calculate', 'Напиши \"посчитай\" или \"расчёт\".')}"
                    )
            except:
                pass

        response_parts.append(
            f"\n**{self.translator.translate('if_parameters_not_suitable', 'Если параметры не подходят — скажи.')}**")

        return "\n\n".join(response_parts)

    def _handle_advice_request(self, context):
        """Обрабатывает запрос советов."""

        if context.has_minimum_data():
            return self._give_recommendation(context, "roughing", [])
        else:
            missing = []
            if not context.material:
                missing.append(self.translator.translate("material", "материал"))
            if not context.operation:
                missing.append(self.translator.translate("operation", "операция"))

            return (
                f"{self.translator.translate('to_give_advice', 'Чтобы дать совет, нужно знать')}: {', '.join(missing)}.\n\n"
                f"**{self.translator.translate('write_all_at_once', 'Напиши сразу всё, например')}:**\n"
                f"• 'алюминий токарка черновая'\n"
                f"• 'сталь 45 фрезеровка Ø50'\n"
                f"• 'титан расточка вылет 100'"
            )

    def _ask_for_feedback(self, context):
        """Спрашивает обратную связь."""

        options = [
            f"• {self.translator.translate('try_other_parameters', 'Попробовать другие параметры')}",
            f"• {self.translator.translate('new_task', 'Новая задача')} (/reset)",
            f"• {self.translator.translate('or_all_clear', 'Или всё понятно?')}"
        ]

        return (
                f"✅ {self.translator.translate('everything_discussed', 'По этой задаче всё обсудили.')}\n\n"
                f"**{self.translator.translate('what_next', 'Что дальше?')}**\n" + "\n".join(options)
        )