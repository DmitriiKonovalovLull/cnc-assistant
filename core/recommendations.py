"""
Интеллектуальные рекомендации с учетом конкретики.
"""

import random


class SmartRecommender:
    """Умный генератор рекомендаций."""

    @staticmethod
    def get_recommendation(context):
        """Генерирует рекомендации с учетом всех деталей."""

        if not context.material or not context.operation:
            return "Нужно знать материал и операцию."

        material = context.material.lower()
        operation = context.operation.lower()
        mode = context.mode.lower() if context.mode else ""
        diameter = context.diameter

        # === ОСОБЫЙ СЛУЧАЙ: маленький диаметр ===
        if diameter:
            try:
                dia = float(diameter.replace(',', '.'))
                if dia < 5:
                    return SmartRecommender._small_diameter_advice(dia, material, operation, mode)
                elif dia < 20:
                    return SmartRecommender._medium_diameter_advice(dia, material, operation, mode)
                elif dia > 50:
                    return SmartRecommender._large_diameter_advice(dia, material, operation, mode)
            except:
                pass

        # === АЛЮМИНИЙ ===
        if 'алюмин' in material:
            if 'токар' in operation:
                if 'чернов' in mode:
                    return SmartRecommender._aluminum_turning_rough(diameter)
                elif 'чистов' in mode:
                    return SmartRecommender._aluminum_turning_finish(diameter)
                else:
                    return SmartRecommender._aluminum_turning_general(diameter)

            elif 'фрез' in operation:
                return SmartRecommender._aluminum_milling(diameter)

        # === СТАЛЬ ===
        elif 'сталь' in material:
            if 'токар' in operation:
                if 'чернов' in mode:
                    return SmartRecommender._steel_turning_rough(diameter)
                elif 'чистов' in mode:
                    return SmartRecommender._steel_turning_finish(diameter)
                else:
                    return SmartRecommender._steel_turning_general(diameter)

            elif 'фрез' in operation:
                return SmartRecommender._steel_milling(diameter)

        # Общие рекомендации
        return SmartRecommender._general_advice(material, operation, mode, diameter)

    # === МЕТОДЫ ДЛЯ РАЗНЫХ СЛУЧАЕВ ===

    @staticmethod
    def _small_diameter_advice(dia, material, operation, mode):
        """Советы для маленьких диаметров (<5 мм)."""
        return (
            f"⚠️ **Внимание: диаметр всего {dia} мм!**\n\n"
            "**Особые рекомендации:**\n"
            "• Очень высокие обороты\n"
            "• Минимальная подача\n"
            "• Идеально острый инструмент\n"
            "• Минимальный вылет\n\n"
            "💡 **Совет:** Для таких диаметров лучше опытным путём."
        )

    @staticmethod
    def _aluminum_turning_rough(diameter=None):
        """Черновая токарка алюминия."""
        base = (
            "🏭 **Для черновой токарки алюминия:**\n\n"
            "**Базовые параметры:**\n"
            "• Обороты: 1000-2000 об/мин\n"
            "• Подача: 0.3-0.5 мм/об\n"
            "• Глубина: 3-5 мм\n\n"
            "💡 **Советы:**\n"
            "• Острый резец с большим углом\n"
            "• Воздух вместо СОЖ\n"
            "• Не бойся скорости"
        )

        if diameter:
            try:
                dia = float(diameter.replace(',', '.'))
                if dia < 20:
                    base += (
                        f"\n\n💎 **Для Ø{dia} мм:**\n"
                        "• Обороты: 1500-2500 об/мин\n"
                        "• Подача: 0.2-0.4 мм/об\n"
                        "• Следи за вибрациями!"
                    )
            except:
                pass

        return base

    @staticmethod
    def _aluminum_turning_finish(diameter=None):
        """Чистовая токарка алюминия."""
        return (
            "✨ **Для чистовой токарки алюминия:**\n\n"
            "**Параметры для блеска:**\n"
            "• Обороты: 1500-3000 об/мин\n"
            "• Подача: 0.1-0.2 мм/об\n"
            "• Глубина: 0.5-1 мм\n\n"
            "💎 **Для зеркала:**\n"
            "• ОЧЕНЬ острый инструмент\n"
            "• Радиус 0.4-0.8 мм\n"
            "• Воздух для чистоты\n"
            "• Минимальная подача на финише"
        )

    @staticmethod
    def _aluminum_turning_general(diameter=None):
        """Общие советы по алюминию."""
        advice = [
            "Алюминий любит скорость и острый инструмент.",
            "Можно работать почти без охлаждения.",
            "Не бойся больших подач.",
            "Следи, чтобы стружка не наматывалась."
        ]

        response = (
            "🔧 **По алюминию для токарки:**\n\n"
            "**Общие принципы:**\n"
            f"• {random.choice(advice)}\n"
            f"• {random.choice(advice)}\n\n"
            "**Уточни для конкретики:**\n"
            "• Черновая — больше съём\n"
            "• Чистовая — блеск и точность"
        )

        return response

    @staticmethod
    def _steel_turning_rough(diameter=None):
        """Черновая токарка стали."""
        return (
            "⚙️ **Для черновой токарки стали:**\n\n"
            "**Стартовые параметры:**\n"
            "• Скорость: 100-160 м/мин\n"
            "• Подача: 0.2-0.35 мм/об\n"
            "• Глубина: 2-3 мм\n\n"
            "⚠️ **Важно:**\n"
            "• Используй СОЖ\n"
            "• Стружка должна ломаться\n"
            "• Снизь подачу при вибрациях\n"
            "• Для стали 45 — пластины с покрытием"
        )

    @staticmethod
    def _general_advice(material, operation, mode, diameter):
        """Общие умные советы."""

        tips = [
            "Начни со средних значений и корректируй по стружке.",
            "Станок не должен сильно вибрировать.",
            "Инструмент должен служить долго.",
            "Хорошая обработка = хорошая стружка.",
            "Не торопись — лучше медленно и качественно."
        ]

        response = (
            f"🤔 **По {material} для {operation}:**\n\n"
            "**Мой подход:**\n"
            f"1. {random.choice(tips)}\n"
            f"2. {random.choice(tips)}\n\n"
        )

        if mode:
            response += f"**Режим:** {mode}\n"

        if diameter:
            response += f"**Диаметр:** {diameter} мм\n\n"

        response += (
            "💡 **Совет:**\n"
            "Сделай пробный проход и посмотри на результат."
        )

        return response