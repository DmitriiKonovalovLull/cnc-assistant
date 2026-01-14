"""
Главный обработчик сообщений.
Связывает парсер, контекст, предположения и рекомендации.
"""

import random
from core.context import get_context
from core.parser import SimpleParser
from core.assumptions import AssumptionEngine
from core.human_recommendations import HumanRecommender
from core.variations import ResponseVariations


class MessageHandler:
    """Обработчик входящих сообщений."""

    def __init__(self):
        self.parser = SimpleParser()
        self.assumption_engine = AssumptionEngine()
        self.recommender = HumanRecommender()

    def handle_message(self, user_id, text):
        """
        Обрабатывает сообщение пользователя.
        Возвращает ответ бота.
        """
        # Получаем контекст пользователя
        context = get_context(user_id)

        # Парсим сообщение
        parsed = self.parser.parse(text)

        # === ПЕРВЫМ ДЕЛОМ - КОМАНДЫ ===
        if 'command' in parsed:
            if parsed['command'] == 'get_recommendations':
                return self._handle_get_recommendations(context)
            elif parsed['command'] == 'continue':
                return self._handle_continue(context)

        # === СПЕЦИАЛЬНЫЕ ЗАПРОСЫ ===
        if 'query' in parsed:
            if parsed['query'] == 'ask_mode':
                return "Уточни режим обработки: черновая или чистовая?"
            elif parsed['query'] == 'ask_tool':
                return "Какой инструмент используешь? Например: резец, фреза, сверло"

        # === ОБНОВЛЯЕМ КОНТЕКСТ ===
        for field, value in parsed.items():
            if field not in ['command', 'query'] and value:
                confidence = 0.9
                # Уменьшаем уверенность для предположений из текста
                if field in ['mode', 'tool'] and not any(
                        keyword in text.lower() for keyword in ['черн', 'чист', 'рез', 'фрез', 'сверл']):
                    confidence = 0.6
                context.update(field, value, source="parser", confidence=confidence)

        # === ПРИМЕНЯЕМ ПРЕДПОЛОЖЕНИЯ ===
        assumptions = self.assumption_engine.apply_assumptions(context)

        # === ГЕНЕРИРУЕМ ОТВЕТ ===
        if assumptions:
            assumption_text = "\n".join(assumptions)

            # В 20% случаев добавляем сомнение к предположениям
            if random.random() < 0.2:
                doubt = ResponseVariations.get_doubt_response()
                response = f"{assumption_text}\n\n{doubt}\n\n{self._generate_variative_response(context)}"
            else:
                response = f"{assumption_text}\n\n{self._generate_variative_response(context)}"
        else:
            response = self._generate_variative_response(context)

        # Отладочная информация (можно отключить)
        debug = f"\n\n[Debug] {context.get_state()}"

        return response + debug

    def _generate_variative_response(self, context):
        """Генерирует вариативный интеллектуальный ответ."""

        # Если контекст пустой
        if not context.has_minimum_data():
            return ResponseVariations.get_greeting()

        parts = []

        if context.material:
            parts.append(f"▸ Материал: {context.material}")
        if context.operation:
            parts.append(f"▸ Операция: {context.operation}")
        if context.tool:
            parts.append(f"▸ Инструмент: {context.tool}")
        if context.mode:
            parts.append(f"▸ Режим: {context.mode}")
        if context.diameter:
            parts.append(f"▸ Диаметр: {context.diameter} мм")
        if context.length:
            parts.append(f"▸ Длина: {context.length} мм")

        if parts:
            state = "\n".join(parts)

            # 1. Есть материал, но нет операции
            if context.material and not context.operation:
                return f"{state}\n\n{ResponseVariations.get_material_response(context.material)}"

            # 2. Есть материал и операция, но нет режима
            elif context.material and context.operation and not context.mode:
                # В 30% случаев задаем дополнительный вопрос
                if random.random() < 0.3 and context.diameter:
                    return f"{state}\n\nДиаметр {context.diameter} мм - это много или мало для такой задачи?"
                elif random.random() < 0.2:
                    return f"{state}\n\n{ResponseVariations.get_clarification_question()}"
                else:
                    return f"{state}\n\n{ResponseVariations.get_operation_response(context.operation)}"

            # 3. Всё собрано (материал, операция, режим)
            elif context.material and context.operation and context.mode:
                # Добавляем сомнение или уточнение в 40% случаев
                if random.random() < 0.4:
                    if context.diameter and random.random() < 0.5:
                        try:
                            dia = float(context.diameter.replace(',', '.'))
                            if dia < 10:
                                clarification = f"Диаметр всего {dia} мм - уверен в параметрах?"
                            elif dia > 50:
                                clarification = f"Диаметр {dia} мм - станок справится?"
                            else:
                                clarification = ResponseVariations.get_clarification_question()
                        except:
                            clarification = ResponseVariations.get_clarification_question()
                    else:
                        clarification = ResponseVariations.get_clarification_question()

                    return f"{state}\n\n{clarification}\n\n(или напиши 'совет' для рекомендаций)"
                else:
                    return f"{state}\n\n{ResponseVariations.get_complete_response()}"

            # 4. Другие случаи
            else:
                # Иногда добавляем сомнение (20% шанс)
                if random.random() < 0.2:
                    doubt = ResponseVariations.get_doubt_response()
                    return f"{state}\n\n{doubt}"
                elif random.random() < 0.3:
                    return f"{state}\n\nЧто-то ещё уточнить?"
                else:
                    return f"👌 {state}\n\nПродолжаем?"

        # Если ничего не распознали
        return ResponseVariations.get_confused_response()

    def _handle_get_recommendations(self, context):
        """Обработка запроса рекомендаций."""
        if not context.material or not context.operation:
            return (
                "Чтобы дать совет, мне нужно знать:\n"
                "• Что за материал?\n"
                "• Какая операция?\n\n"
                "Например: 'сталь 45 токарка черновая'"
            )

        # Передаем контекст в рекомендации для персонализации
        recommendation = self.recommender.get_recommendation(context)

        # В 25% случаев добавляем сомнение к рекомендациям
        if random.random() < 0.25:
            doubt = ResponseVariations.get_doubt_response()
            full_response = self.recommender.format_response(context, recommendation)
            return f"{full_response}\n\n💭 {doubt}"
        else:
            return self.recommender.format_response(context, recommendation)

    def _handle_continue(self, context):
        """Обработка продолжения."""
        if context.material and context.operation:
            return self._handle_get_recommendations(context)
        else:
            # Вариативный ответ
            responses = [
                "Что будем обрабатывать? Укажите материал и операцию.",
                "Начнем с начала: какой материал и операция?",
                "Расскажи про материал и что с ним делать?",
                "Сначала материал и операция, потом рекомендации."
            ]
            return random.choice(responses)