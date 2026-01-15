"""
Исправленный контекст с правильной логикой завершения.
"""


class CuttingContext:
    """Контекст обработки."""

    def __init__(self):
        # Основные сущности
        self.material = None
        self.operation = None
        self.tool = None
        self.diameter = None

        # Режимы обработки
        self.modes = []
        self.active_mode = None

        # Управление диалогом
        self.active_step = "waiting_start"  # ← ИЗМЕНЕНО: начинаем с ожидания
        self.step_history = []

        # Уверенность
        self.confidence = {
            "material": 0.0,
            "operation": 0.0,
            "tool": 0.0,
            "modes": 0.0
        }

        # Флаги
        self.recommendations_given = []
        self.is_dialog_active = True  # ← ДОБАВЛЕНО: флаг активности диалога

    def update(self, field, value, source="user", confidence=1.0):
        """Обновляет поле контекста."""
        if hasattr(self, field):
            # Не перезаписываем если уверенность выше
            current_conf = self.confidence.get(field, 0.0)
            if confidence > current_conf:
                setattr(self, field, value)
                self.confidence[field] = confidence

                # Активируем диалог при любом обновлении
                self.is_dialog_active = True

                # Сбрасываем завершение если получаем новые данные
                if self.active_step == "feedback":
                    self.active_step = "processing"

    def has_minimum_data(self):
        """Проверяет, есть ли минимальные данные для рекомендаций."""
        return bool(self.material and self.operation)

    def is_confident_enough(self, field, threshold=0.7):
        """Достаточно ли уверены в данных."""
        return self.confidence.get(field, 0.0) >= threshold

    def get_next_step(self):
        """Определяет следующий шаг."""

        # Если диалог не активен - ждем старта
        if not self.is_dialog_active:
            return "waiting_start"

        # Если нет материала или операции
        if not self.material or not self.operation:
            return "clarify_missing"

        # Если есть режимы, но не назначен активный
        if self.modes and not self.active_mode:
            return "set_active_mode"

        # Если есть активный режим, но не давали рекомендаций
        if self.active_mode and self.active_mode not in self.recommendations_given:
            return f"recommend_{'roughing' if 'чернов' in self.active_mode else 'finishing'}"

        # Если есть другие режимы для обсуждения
        if self.modes:
            for mode in self.modes:
                if mode not in self.recommendations_given:
                    self.active_mode = mode
                    return f"recommend_{'roughing' if 'чернов' in mode else 'finishing'}"

        # Готово - но только если действительно что-то обсуждали
        if self.recommendations_given:
            return "feedback"
        else:
            return "waiting_start"  # Не завершаем если ничего не сделали

    def move_to_next_step(self):
        """Переходит к следующему шагу."""
        current_step = self.active_step
        next_step = self.get_next_step()

        if next_step != current_step:
            self.step_history.append(current_step)
            self.active_step = next_step

        return self.active_step

    def reset_for_new_dialog(self):
        """Сброс для нового диалога (но сохраняем некоторые настройки)."""
        # Сбрасываем только состояние диалога, но не языковые настройки
        self.active_step = "waiting_start"
        self.recommendations_given = []
        self.is_dialog_active = True
        self.step_history = []


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