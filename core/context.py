"""
Единый объект состояния для бота.
"""


class CuttingContext:
    """Контекст обработки."""

    def __init__(self):
        # Основные сущности
        self.material = None
        self.operation = None
        self.tool = None
        self.mode = None
        self.diameter = None

        # Флаги состояния
        self.recommendations_given = False

        # Уверенность
        self.confidence = {
            "material": 0.0,
            "operation": 0.0,
            "tool": 0.0,
            "mode": 0.0
        }

        # История
        self.messages = []

    def update(self, field, value, source="user", confidence=1.0):
        """Обновляет поле контекста."""
        if hasattr(self, field):
            setattr(self, field, value)
            if field in self.confidence:
                self.confidence[field] = confidence

            self.messages.append({
                "field": field,
                "value": value,
                "source": source,
                "confidence": confidence
            })

    def has_minimum_data(self):
        """Проверяет, есть ли минимальные данные."""
        return bool(self.material or self.operation)

    def get_state(self):
        """Для отладки."""
        lines = []
        if self.material:
            lines.append(f"Материал: {self.material}")
        if self.operation:
            lines.append(f"Операция: {self.operation}")
        if self.mode:
            lines.append(f"Режим: {self.mode}")
        return " | ".join(lines)


# Глобальное хранилище
contexts = {}


def get_context(user_id):
    """Получает контекст пользователя."""
    if user_id not in contexts:
        contexts[user_id] = CuttingContext()
    return contexts[user_id]


def reset_context(user_id):
    """Сбрасывает контекст."""
    contexts[user_id] = CuttingContext()
    return contexts[user_id]