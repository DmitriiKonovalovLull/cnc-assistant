"""
Умный обработчик для Дня 1 - Бот который уточняет, а не предполагает.
"""

import random
from core.context import get_context
from core.parser import SimpleParser
from core.recommendations import SmartRecommender


class MessageHandler:
    """Интеллектуальный обработчик."""

    def __init__(self):
        self.parser = SimpleParser()
        self.recommender = SmartRecommender()

        # Фразы для разных ситуаций
        self.phrases = {
            'greeting': [
                "Привет! Что обрабатываем?",
                "Здравствуйте! Какой материал?",
                "Добрый день! Что за задача?",
                "Приветствую! Что будем делать?"
            ],

            'ask_operation': [
                "Хорошо. Какая операция? (токарка/фрезеровка)",
                "Понял материал. Что делаем? Токарка или фрезеровка?",
                "Материал запомнил. Какая операция нужна?",
                "Так. Теперь скажи операцию: токарка или фрезеровка?"
            ],

            'ask_mode': [
                "Какой режим обработки? (черновой/чистовой)",
                "Черновая или чистовая обработка?",
                "Уточни режим: черновой или чистовой?",
                "Режим какой нужен: черновой или чистовой?"
            ],

            'ready': [
                "✅ Всё понял! Хочешь рекомендации?",
                "👍 Данные собраны. Дать совет по настройке?",
                "👌 Запомнил. Могу подсказать с параметрами.",
                "✅ Готово! Нужны рекомендации по обработке?"
            ],

            'confused': [
                "Не совсем понял... Можешь объяснить иначе?",
                "Хм, не уловил мысль. Расскажи подробнее?",
                "Запутался. Можешь повторить по-другому?",
                "Не понял. Можешь сказать проще?"
            ]
        }

    def handle_message(self, user_id, text):
        """Обрабатывает сообщение."""
        try:
            context = get_context(user_id)
            parsed = self.parser.parse(text)

            print(f"DEBUG: '{text}' -> {parsed}")

            # Если это команда рекомендаций
            if 'command' in parsed:
                return self._give_recommendations(context)

            # Обновляем контекст ЧАСТИЧНО
            updated = False

            if 'material' in parsed and parsed['material']:
                # Если материал меняется - сбрасываем остальное
                if context.material != parsed['material']:
                    context.material = parsed['material']
                    context.operation = None  # Сбрасываем операцию
                    context.mode = None  # Сбрасываем режим
                    context.diameter = None  # Сбрасываем диаметр
                    updated = True

            if 'operation' in parsed and parsed['operation']:
                context.operation = parsed['operation']
                updated = True

            if 'mode' in parsed and parsed['mode']:
                context.mode = parsed['mode']
                updated = True

            if 'diameter' in parsed and parsed['diameter']:
                context.diameter = parsed['diameter']
                updated = True

            # Генерируем ответ на основе текущего состояния
            return self._generate_smart_response(context, text)

        except Exception as e:
            print(f"Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return "Что-то пошло не так... Напиши /start для начала."

    def _generate_smart_response(self, context, user_text):
        """Генерирует умный ответ на основе контекста."""

        user_text_lower = user_text.lower()

        # 1. Если пользователь просит оба режима
        if ('чернов' in user_text_lower and 'чистов' in user_text_lower) or \
                ('черн' in user_text_lower and 'чист' in user_text_lower):
            return (
                "А, понимаю — нужны параметры и для черновой, и для чистовой обработки?\n\n"
                "Давай так:\n"
                "1. Сначала обсудим черновую\n"
                "2. Потом чистовая\n\n"
                "Для какого материала и операции?"
            )

        # 2. Если пользователь говорит о диаметре
        if 'диаметр' in user_text_lower or 'ø' in user_text_lower or 'мм' in user_text_lower:
            if context.diameter:
                return (
                    f"Диаметр {context.diameter} мм запомнил.\n\n"
                    f"Для такого диаметра нужны особые настройки. "
                    f"Уточни материал и операцию."
                )

        # 3. Поэтапный сбор информации
        if not context.material:
            return random.choice(self.phrases['greeting'])

        elif context.material and not context.operation:
            return random.choice(self.phrases['ask_operation'])

        elif context.material and context.operation and not context.mode:
            # Если есть диаметр - упоминаем его
            if context.diameter:
                return (
                    f"Материал: {context.material}\n"
                    f"Операция: {context.operation}\n"
                    f"Диаметр: {context.diameter} мм\n\n"
                    f"{random.choice(self.phrases['ask_mode'])}"
                )
            else:
                return random.choice(self.phrases['ask_mode'])

        elif context.material and context.operation and context.mode:
            # Собираем информацию о том, что у нас есть
            info = []
            if context.material:
                info.append(f"• Материал: {context.material}")
            if context.operation:
                info.append(f"• Операция: {context.operation}")
            if context.mode:
                info.append(f"• Режим: {context.mode}")
            if context.diameter:
                info.append(f"• Диаметр: {context.diameter} мм")

            info_text = "\n".join(info)

            # Разные варианты ответа
            variants = [
                f"{info_text}\n\n{random.choice(self.phrases['ready'])}",
                f"Итак:\n{info_text}\n\n{random.choice(self.phrases['ready'])}",
                f"Понял задачу:\n{info_text}\n\n{random.choice(self.phrases['ready'])}"
            ]

            # В 40% случаев добавляем "сомнение"
            if random.random() < 0.4:
                doubt = random.choice([
                    "\n\n🤔 Правильно понял?",
                    "\n\n💭 Как думаешь, всё верно?",
                    "\n\n👨‍🏭 По-моему так. Ты согласен?"
                ])
                return random.choice(variants) + doubt

            return random.choice(variants)

        else:
            return random.choice(self.phrases['confused'])

    def _give_recommendations(self, context):
        """Даёт рекомендации."""
        if not context.material or not context.operation:
            return (
                "Сначала нужно знать:\n"
                "1. Материал (например: алюминий, сталь 45)\n"
                "2. Операция (токарка или фрезеровка)\n\n"
                "Потом могу дать рекомендации."
            )

        # Если нет режима - спрашиваем
        if not context.mode:
            return (
                f"По {context.material} для {context.operation}:\n\n"
                "Нужно уточнить режим:\n"
                "• Черновая обработка — для быстрого съёма\n"
                "• Чистовая — для точности и качества\n\n"
                "Какой режим нужен?"
            )

        # Даём рекомендации
        recommendation = self.recommender.get_recommendation(context)

        # Форматируем с контекстом
        context_info = []
        if context.material:
            context_info.append(f"**Материал:** {context.material}")
        if context.operation:
            context_info.append(f"**Операция:** {context.operation}")
        if context.mode:
            context_info.append(f"**Режим:** {context.mode}")
        if context.diameter:
            context_info.append(f"**Диаметр:** {context.diameter} мм")

        # Выбираем вступление
        intro = random.choice([
            "🤔 **Вот что я думаю:**",
            "👨‍🏭 **По моему опыту:**",
            "🔧 **Рекомендую начать с:**",
            "💡 **Мой совет:**"
        ])

        # Выбираем завершение
        ending = random.choice([
            "\n\n**Что скажешь?**\n▸ Подойдёт?\n▸ Нужны уточнения?\n▸ Или другой режим?",
            "\n\n**Как думаешь?**\n▸ Попробуешь так?\n▸ Или изменить параметры?",
            "\n\n**Дальше?**\n▸ Уточни что-нибудь\n▸ Или /reset для новой задачи"
        ])

        return f"{intro}\n\n" + "\n".join(context_info) + "\n\n" + recommendation + ending