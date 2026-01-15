"""
Assumption Engine с правилами приоритета.
"""


class AssumptionEngine:
    """Двигатель предположений с учетом уверенности."""

    @staticmethod
    def apply_assumptions(context):
        """Применяет предположения, если уверенность низкая."""
        actions = []

        # ПРАВИЛО 1: Если есть материал, но нет операции
        if context.material and not context.operation:
            if context.confidence.get('material', 0) >= 0.5:
                assumption = AssumptionEngine._assume_operation(context.material)
                if assumption:
                    context.update("operation", assumption, source="assumption", confidence=0.4)
                    actions.append(f"Я предполагаю {assumption}.")

        # ПРАВИЛО 2: Если есть операция, но нет режимов
        if context.operation and not context.modes:
            if context.confidence.get('operation', 0) >= 0.5:
                context.modes = ['черновая']
                context.confidence['modes'] = 0.3
                actions.append("Предполагаю черновую обработку.")

        # ПРАВИЛО 3: Если есть режимы, но нет активного
        if context.modes and not context.active_mode:
            # Всегда начинаем с черновой
            context.active_mode = 'черновая'
            context.confidence['active_mode'] = 0.4
            actions.append("Начнём с черновой обработки.")

        return actions

    @staticmethod
    def _assume_operation(material):
        """Предполагает операцию на основе материала."""
        material_lower = material.lower()

        if 'сталь' in material_lower:
            return 'токарная'
        elif 'алюмин' in material_lower:
            return 'токарная'
        elif 'титан' in material_lower:
            return 'токарная'

        return None
