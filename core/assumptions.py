"""
Assumption Engine ("магия ИИ").
Задача: не спрашивать сразу, а предполагать.
Делает бота умнее без сложной логики.
"""


class AssumptionEngine:
    """Двигатель предположений."""

    @staticmethod
    def apply_assumptions(context):
        assumptions = []

        # Не делаем предположений при пустом контексте
        if not context.has_minimum_data():
            return assumptions

        # === ПРАВИЛО: Маленький диаметр → выше обороты ===
        if context.diameter:
            try:
                dia = float(context.diameter.replace(',', '.'))
                if dia < 20:
                    assumptions.append(f"Диаметр {dia} мм маленький — нужны высокие обороты.")
                elif dia > 100:
                    assumptions.append(f"Диаметр {dia} мм большой — осторожно с вибрациями.")
            except:
                pass

        # === ПРАВИЛО: Алюминий + маленький диаметр → острый инструмент ===
        if (context.material and 'алюмин' in context.material.lower() and
                context.diameter):
            try:
                dia = float(context.diameter.replace(',', '.'))
                if dia < 15:
                    assumptions.append("Для маленького диаметра алюминия нужен очень острый инструмент.")
            except:
                pass

        # Остальные правила...

        # === ПРАВИЛО 1: Если есть материал, но нет операции ===
        if context.material and not context.operation:
            material_lower = context.material.lower()

            if 'сталь' in material_lower:
                context.update("operation", "токарная",
                               source="assumption", confidence=0.4)
                assumptions.append("Я предполагаю токарную обработку. Если не так — скажи 'фрезеровка'.")

            elif 'алюмин' in material_lower:
                context.update("operation", "токарная",
                               source="assumption", confidence=0.5)
                assumptions.append("Для алюминия часто используют токарку. Это верно?")

        # === ПРАВИЛО 2: Если есть операция, но нет режима ===
        elif context.operation and not context.mode:
            # Только если уже есть материал
            if context.material:
                context.update("mode", "черновая",
                               source="assumption", confidence=0.3)
                assumptions.append("Предполагаю черновую обработку. Уточни режим если нужно.")

        # === ПРАВИЛО 3: Если есть сталь и токарка, но нет инструмента ===
        elif (context.material and 'сталь' in context.material.lower() and
              context.operation and 'токар' in context.operation and
              not context.tool):
            context.update("tool", "резец с пластиной",
                           source="assumption", confidence=0.5)
            assumptions.append("Для стали обычно используют резец с твердосплавной пластиной.")

        # === ПРАВИЛО 4: Если есть алюминий и токарка, но нет инструмента ===
        elif (context.material and 'алюмин' in context.material.lower() and
              context.operation and 'токар' in context.operation and
              not context.tool):
            context.update("tool", "острый резец",
                           source="assumption", confidence=0.6)
            assumptions.append("Для алюминия рекомендую острые резцы.")

        return assumptions