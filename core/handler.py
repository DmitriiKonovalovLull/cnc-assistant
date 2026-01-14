"""
Умный обработчик сообщений.
"""

import random
from core.context import get_context
from core.parser import SimpleParser
from core.assumptions import AssumptionEngine
from core.human_recommendations import HumanRecommender


class MessageHandler:
    """Обработчик сообщений."""

    def __init__(self):
        self.parser = SimpleParser()
        self.assumption_engine = AssumptionEngine()
        self.recommender = HumanRecommender()

        # Вариации
        self.greetings = [
            "Привет! Что будем обрабатывать?",
            "Здравствуй! Какая задача?",
            "Приветствую! Что делаем сегодня?",
            "Добрый день! Что обрабатываем?",
            "Привет! Готов помочь. Какая операция?"
        ]

        self.confused_responses = [
            "Не совсем понял... Можешь объяснить по-другому?",
            "Хм, не уверен что понял. Уточни?",
            "Запутался. Расскажи подробнее?",
            "Не совсем ясно. Повтори иначе?"
        ]

    def handle_message(self, user_id, text):
        """Обрабатывает сообщение."""
        try:
            context = get_context(user_id)
            parsed = self.parser.parse(text)

            print(f"DEBUG: Парсинг '{text}' -> {parsed}")

            # 1. Если это команда рекомендаций
            if 'command' in parsed and parsed['command'] == 'get_recommendations':
                print(f"DEBUG: Распознана команда рекомендаций")
                return self._get_recommendations(context)

            # 2. Если это положительный ответ (да, ок, хорошо)
            if 'response' in parsed and parsed['response'] == 'positive':
                print(f"DEBUG: Положительный ответ")
                return self._handle_positive_response(context)

            # 3. Обновляем контекст
            for field, value in parsed.items():
                if field not in ['command', 'query', 'response'] and value:
                    confidence = 0.9
                    # Если режим угадан из контекста - меньше уверенность
                    if field == 'mode' and 'черн' not in text.lower() and 'чист' not in text.lower():
                        confidence = 0.6
                    context.update(field, value, source="parser", confidence=confidence)

            # 4. Предположения
            assumptions = self.assumption_engine.apply_assumptions(context)

            # 5. Ответ
            response = self._generate_response(context, assumptions, text)

            return response

        except Exception as e:
            print(f"Ошибка в handle_message: {e}")
            import traceback
            traceback.print_exc()
            return "Что-то пошло не так... Давай начнем заново. Что обрабатываем?"

    def _generate_response(self, context, assumptions, original_text=""):
        """Генерирует ответ."""

        # Если пустой контекст
        if not context.has_minimum_data():
            return random.choice(self.greetings)

        # Информация
        info_parts = []
        if context.material:
            info_parts.append(f"**Материал:** {context.material}")
        if context.operation:
            info_parts.append(f"**Операция:** {context.operation}")
        if context.mode:
            info_parts.append(f"**Режим:** {context.mode}")

        info_text = "\n".join(info_parts) if info_parts else ""

        # С предположениями
        if assumptions:
            assumption_text = " ".join(assumptions)
            variants = [
                f"{assumption_text}\n\n{info_text}",
                f"Думаю так:\n{assumption_text}\n\n{info_text}",
                f"{assumption_text}\n\n{info_text}"
            ]
            base_response = random.choice(variants)
        else:
            base_response = info_text

        # Добавляем призыв к действию
        if context.material and context.operation and context.mode:
            # Если всё собрано - предлагаем рекомендации
            if hasattr(context, 'recommendations_given') and context.recommendations_given:
                call_to_action = random.choice([
                    "\n\n✅ Рекомендации уже давал. Что-то уточнить?",
                    "\n\n👌 Помню эту задачу. Нужны дополнительные пояснения?",
                    "\n\n💭 Уже обсуждали. Что-то изменилось?"
                ])
            else:
                call_to_action = random.choice([
                    "\n\n✅ Всё готово! Напиши 'совет' или 'рекомендации'.",
                    "\n\n👌 Запомнил. Хочешь получить параметры?",
                    "\n\n👍 Данные собраны. Можешь попросить рекомендации."
                ])
        elif context.material and context.operation:
            # Если нет режима
            call_to_action = random.choice([
                "\n\nУточни режим: черновая или чистовая?",
                "\n\nКакой режим обработки?",
                "\n\nЭто черновая или чистовая работа?"
            ])
        elif context.material:
            # Если только материал
            call_to_action = random.choice([
                f"\n\nЧто делаем с {context.material}?",
                f"\n\nКакая операция для {context.material}?",
                "\n\nТокарка или фрезеровка?"
            ])
        else:
            call_to_action = "\n\nЧто-то ещё?"

        response = base_response + call_to_action if base_response else call_to_action

        # Добавляем "человечность" (30% шанс)
        if random.random() < 0.3:
            human_touch = random.choice([
                "\n\n🤔 Что скажешь?",
                "\n\n💭 Как тебе?",
                "\n\n👨‍🏭 На твоём опыте...",
                "\n\n🔧 По-моему так..."
            ])
            response += human_touch

        return response

    def _handle_positive_response(self, context):
        """Обрабатывает положительный ответ (да, ок и т.д.)."""
        if context.material and context.operation and context.mode:
            # Если всё есть - спрашиваем что дальше
            responses = [
                "Отлично! Что дальше?\n▸ 'совет' - рекомендации\n▸ /reset - новая задача\n▸ 'сталь' - другой материал",
                "Хорошо. Что будем делать?\n▸ Нужны параметры?\n▸ Хочешь уточнить?\n▸ Или новая задача?",
                "Понял. Ещё что-то нужно?\n▸ Рекомендации?\n▸ Вопросы?\n▸ Или продолжаем?"
            ]
            return random.choice(responses)
        else:
            # Если данных мало
            return "Хорошо. Продолжим сбор информации?"

    def _get_recommendations(self, context):
        """Даёт рекомендации."""
        if not context.material or not context.operation:
            return "Сначала скажи, что обрабатываем и какую операцию делаем."

        print(f"DEBUG: Даю рекомендации для {context.material}, {context.operation}, {context.mode}")

        # Если рекомендации уже давались
        if hasattr(context, 'recommendations_given') and context.recommendations_given:
            responses = [
                "Я уже давал рекомендации по этой задаче. Хочешь что-то уточнить?",
                "По этой задаче мы уже обсуждали параметры. Что-то изменилось?",
                "Помню эту задачу. Нужны дополнительные пояснения?"
            ]
            return random.choice(responses)

        # Даем рекомендации
        recommendation = self.recommender.get_recommendation(context)

        # Помечаем, что рекомендации даны
        context.recommendations_given = True

        # Интеллектуальный вывод
        intro = random.choice([
            "🤔 **Думаю так:**",
            "👨‍🏭 **По моему опыту:**",
            "🔧 **Советую начать с:**",
            "💡 **Мои мысли:**"
        ])

        # Контекст
        context_info = []
        if context.material:
            context_info.append(f"• **Материал:** {context.material}")
        if context.operation:
            context_info.append(f"• **Операция:** {context.operation}")
        if context.mode:
            context_info.append(f"• **Режим:** {context.mode}")

        # Вопрос для продолжения
        follow_up = random.choice([
            "\n\n**Что дальше?**\n▸ Попробуем другие параметры\n▸ Начнём новую задачу (/reset)\n▸ Спроси что-нибудь",
            "\n\n**Как думаешь?**\n▸ Подойдёт?\n▸ Нужно изменить?\n▸ Свой опыт напиши",
            "\n\n**Понятно?**\n▸ Да - продолжаем\n▸ Нет - уточняй\n▸ Другой материал - скажи"
        ])

        full_response = f"{intro}\n\n" + "\n".join(context_info) + "\n\n" + recommendation + follow_up

        return full_response