"""
Единый объект состояния (Context Object) - САМОЕ ВАЖНОЕ за весь проект.
"""


class CuttingContext:
    """Единый объект состояния для резания."""

    def __init__(self):
        # Основные сущности
        self.material = None
        self.operation = None
        self.tool = None
        self.mode = None

        # Конкретные параметры
        self.diameter = None
        self.length = None
        self.tolerance = None

        # Уверенность
        self.confidence = {
            "material": 0.0,
            "operation": 0.0,
            "tool": 0.0,
            "mode": 0.0,
            "diameter": 0.0,
            "length": 0.0
        }

        # История сообщений
        self.messages = []

    def update(self, field, value, source="user", confidence=1.0):
        """Обновление поля контекста."""
        if hasattr(self, field):
            setattr(self, field, value)
            if field in self.confidence:
                self.confidence[field] = confidence

            # Логируем
            self.messages.append({
                "action": "update",
                "field": field,
                "value": value,
                "source": source,
                "confidence": confidence
            })

    def get_state(self):
        """Возвращает текущее состояние."""
        lines = []
        if self.material:
            lines.append(f"Материал: {self.material} ({self.confidence.get('material', 0):.1f})")
        if self.operation:
            lines.append(f"Операция: {self.operation} ({self.confidence.get('operation', 0):.1f})")
        if self.tool:
            lines.append(f"Инструмент: {self.tool} ({self.confidence.get('tool', 0):.1f})")
        if self.mode:
            lines.append(f"Режим: {self.mode} ({self.confidence.get('mode', 0):.1f})")
        if self.diameter:
            lines.append(f"Диаметр: {self.diameter} мм ({self.confidence.get('diameter', 0):.1f})")
        if self.length:
            lines.append(f"Длина: {self.length} мм ({self.confidence.get('length', 0):.1f})")

        return "\n".join(lines) if lines else "Контекст пуст"

    def has_minimum_data(self):
        """Проверяет, есть ли минимальные данные."""
        return bool(self.material or self.operation)


# Глобальный словарь контекстов
contexts = {}


def get_context(user_id):
    """Получить контекст для пользователя."""
    if user_id not in contexts:
        contexts[user_id] = CuttingContext()
    return contexts[user_id]


def reset_context(user_id):
    """Сбросить контекст."""
    contexts[user_id] = CuttingContext()
    return contexts[user_id]