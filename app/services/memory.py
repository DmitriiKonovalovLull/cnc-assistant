"""
Сервис работы с памятью (контекст пользователя).
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta


class UserMemory:
    """Память пользователя для хранения контекста."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.conversation_history = []
        self.previous_decisions = []
        self.preferences = {}
        self.machine_type = None
        self.tool_preferences = {}

    def add_interaction(self, interaction: Dict[str, Any]):
        """Добавить взаимодействие в историю."""
        interaction["timestamp"] = datetime.now().isoformat()
        self.conversation_history.append(interaction)

        # Если это решение по режимам, сохраняем отдельно
        if "user_rpm" in interaction:
            self.previous_decisions.append(interaction)

            # Ограничиваем историю последними 100 решениями
            if len(self.previous_decisions) > 100:
                self.previous_decisions = self.previous_decisions[-100:]

    def get_recent_decisions(self, count: int = 10) -> List[Dict[str, Any]]:
        """Получить последние решения."""
        return self.previous_decisions[-count:] if self.previous_decisions else []

    def get_material_preferences(self) -> Dict[str, Any]:
        """Получить предпочтения по материалам."""
        material_stats = {}

        for decision in self.previous_decisions:
            material = decision.get("material")
            if material:
                if material not in material_stats:
                    material_stats[material] = {
                        "count": 0,
                        "avg_deviation": 0,
                        "deviations": []
                    }

                material_stats[material]["count"] += 1
                if "deviation_score" in decision:
                    material_stats[material]["deviations"].append(
                        decision["deviation_score"]
                    )

        # Рассчитываем средние
        for material, stats in material_stats.items():
            if stats["deviations"]:
                stats["avg_deviation"] = sum(stats["deviations"]) / len(stats["deviations"])

        return material_stats

    def infer_machine_type(self) -> Optional[str]:
        """Попытаться определить тип станка по решениям пользователя."""
        if not self.previous_decisions:
            return None

        # Анализируем типичные обороты
        rpm_values = [d.get("user_rpm", 0) for d in self.previous_decisions if d.get("user_rpm")]
        if not rpm_values:
            return None

        avg_rpm = sum(rpm_values) / len(rpm_values)

        # Эвристики
        if avg_rpm > 4000:
            return "high_speed_cnc"
        elif avg_rpm > 2000:
            return "cnc_lathe"
        elif avg_rpm > 500:
            return "universal"
        else:
            return "old_universal"

    def get_consistency_score(self) -> Optional[float]:
        """Оценка согласованности решений."""
        from app.services.experience import calculate_consistency_score

        if len(self.previous_decisions) < 3:
            return None

        return calculate_consistency_score(self.previous_decisions)


# Глобальное хранилище памяти пользователей
_user_memories = {}


def get_user_memory(user_id: str) -> UserMemory:
    """Получить или создать память пользователя."""
    if user_id not in _user_memories:
        _user_memories[user_id] = UserMemory(user_id)
    return _user_memories[user_id]


def save_user_preference(
        user_id: str,
        preference_type: str,
        value: Any
):
    """Сохранить предпочтение пользователя."""
    memory = get_user_memory(user_id)

    if preference_type == "machine_type":
        memory.machine_type = value
    elif preference_type == "tool_material":
        memory.tool_preferences["material"] = value
    elif preference_type == "strategy":
        memory.preferences["strategy"] = value


def get_user_context(user_id: str) -> Dict[str, Any]:
    """Получить полный контекст пользователя для рекомендаций."""
    memory = get_user_memory(user_id)

    # Определяем тип станка
    machine_type = memory.machine_type or memory.infer_machine_type() or "universal"

    # Анализируем предпочтения по материалам
    material_stats = memory.get_material_preferences()

    # Определяем типичную стратегию
    strategy = "adaptive"
    if memory.previous_decisions:
        deviations = [abs(d.get("deviation_score", 0)) for d in memory.previous_decisions]
        avg_deviation = sum(deviations) / len(deviations)

        if avg_deviation < 0.1:
            strategy = "precise"
        elif avg_deviation > 0.3:
            strategy = "conservative" if deviations[0] < 0 else "aggressive"

    context = {
        "user_id": user_id,
        "machine_type": machine_type,
        "strategy": strategy,
        "material_stats": material_stats,
        "decision_count": len(memory.previous_decisions),
        "consistency_score": memory.get_consistency_score(),
        "preferences": memory.preferences,
        "tool_preferences": memory.tool_preferences,
    }

    return context