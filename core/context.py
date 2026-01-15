"""
Улучшенный контекст с явным FSM и полной функциональностью.
"""

from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
import json
from pathlib import Path


class DialogState(Enum):
    """Явные состояния диалога FSM."""
    WAITING_START = auto()
    COLLECTING_CONTEXT = auto()
    CLARIFYING_MISSING = auto()
    ASKING_FOR_DETAILS = auto()
    RECOMMENDING_ROUGHING = auto()
    RECOMMENDING_FINISHING = auto()
    AWAITING_FEEDBACK = auto()
    PROCESSING_FEEDBACK = auto()
    COMPLETED = auto()


class OperationType(Enum):
    """Типы операций."""
    TURNING = "turning"
    MILLING = "milling"
    DRILLING = "drilling"
    BORING = "boring"
    GRINDING = "grinding"


class MaterialType(Enum):
    """Типы материалов."""
    STEEL = "steel"
    ALUMINUM = "aluminum"
    TITANIUM = "titanium"
    STAINLESS = "stainless_steel"
    CAST_IRON = "cast_iron"
    BRASS = "brass"


@dataclass
class CuttingContext:
    """
    Контекст обработки с явным FSM и инкапсуляцией.
    Только данные, без логики переходов.
    """

    # === ИДЕНТИФИКАЦИЯ ===
    user_id: str = "anonymous"
    session_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))

    # === ОСНОВНЫЕ ДАННЫЕ ===
    material: Optional[str] = None
    material_type: Optional[MaterialType] = None
    operation: Optional[str] = None
    operation_type: Optional[OperationType] = None
    tool: Optional[str] = None
    tool_material: Optional[str] = None
    diameter: Optional[float] = None

    # === ДОПОЛНИТЕЛЬНЫЕ ПАРАМЕТРЫ ===
    depth_of_cut: Optional[float] = None
    cutting_length: Optional[float] = None
    overhang: Optional[float] = None
    width: Optional[float] = None
    hardness: Optional[str] = None
    surface_quality: Optional[str] = None

    # === РЕЖИМЫ ОБРАБОТКИ ===
    modes: List[str] = field(default_factory=list)
    active_mode: Optional[str] = None

    # === УПРАВЛЕНИЕ ДИАЛОГОМ ===
    active_step: DialogState = DialogState.WAITING_START
    step_history: List[DialogState] = field(default_factory=list)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)

    # === УВЕРЕННОСТЬ ===
    confidence: Dict[str, float] = field(default_factory=lambda: {
        "material": 0.0,
        "operation": 0.0,
        "tool": 0.0,
        "diameter": 0.0,
        "depth_of_cut": 0.0
    })

    # === ФЛАГИ И МЕТАДАННЫЕ ===
    recommendations_given: List[str] = field(default_factory=list)
    assumptions_made: List[Dict[str, Any]] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    corrections_received: List[Dict[str, Any]] = field(default_factory=list)

    # === ВРЕМЕННЫЕ МЕТКИ ===
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    last_recommendation_at: Optional[datetime] = None

    # === ВНУТРЕННИЕ ФЛАГИ ===
    _is_dirty: bool = field(default=False, init=False)  # Флаг изменений

    def update_field(self,
                     field_name: str,
                     value: Any,
                     source: str = "user",
                     confidence: float = 1.0,
                     reason: Optional[str] = None) -> bool:
        """
        Безопасное обновление поля с отслеживанием источника.

        Returns:
            True если значение обновлено, False если проигнорировано
        """
        if not hasattr(self, field_name):
            print(f"Поле {field_name} не существует в контексте")
            return False

        # Проверяем, нужно ли обновлять
        current_conf = self.confidence.get(field_name, 0.0)
        current_value = getattr(self, field_name)

        # Приведение типов для числовых полей
        if field_name in ['diameter', 'depth_of_cut', 'cutting_length', 'overhang', 'width']:
            try:
                value = float(value) if value is not None else None
            except (ValueError, TypeError):
                print(f"Неверное значение для {field_name}: {value}")
                return False

        # Обновляем только если:
        # 1. Новое значение отличается ИЛИ
        # 2. Уверенность выше
        should_update = False

        if value != current_value:
            should_update = True
        elif confidence > current_conf:
            should_update = True

        if should_update:
            # Логируем изменение
            if source == "assumption" and reason:
                assumption = {
                    "field": field_name,
                    "value": value,
                    "reason": reason,
                    "confidence": confidence,
                    "timestamp": datetime.now().isoformat(),
                    "previous_value": current_value
                }
                self.assumptions_made.append(assumption)

            # Обновляем значение
            setattr(self, field_name, value)
            self.confidence[field_name] = min(confidence, 1.0)  # Ограничиваем 1.0

            # Обновляем timestamp
            self.last_updated = datetime.now()
            self._is_dirty = True

            # Автоматические преобразования
            self._update_derived_fields(field_name, value)

            return True
        return False

    def _update_derived_fields(self, field_name: str, value: Any):
        """Обновляет производные поля при изменении основного."""
        if field_name == "material" and value:
            # Автоматически определяем тип материала
            material_lower = value.lower()
            if "алюмин" in material_lower or "alum" in material_lower:
                self.material_type = MaterialType.ALUMINUM
            elif "титан" in material_lower or "titan" in material_lower:
                self.material_type = MaterialType.TITANIUM
            elif "нерж" in material_lower or "stainless" in material_lower:
                self.material_type = MaterialType.STAINLESS
            elif "чугун" in material_lower or "cast" in material_lower:
                self.material_type = MaterialType.CAST_IRON
            elif "сталь" in material_lower or "steel" in material_lower:
                self.material_type = MaterialType.STEEL
            elif "латун" in material_lower or "brass" in material_lower:
                self.material_type = MaterialType.BRASS

        elif field_name == "operation" and value:
            # Автоматически определяем тип операции
            op_lower = value.lower()
            if "токар" in op_lower or "turn" in op_lower:
                self.operation_type = OperationType.TURNING
            elif "фрез" in op_lower or "mill" in op_lower:
                self.operation_type = OperationType.MILLING
            elif "сверл" in op_lower or "drill" in op_lower:
                self.operation_type = OperationType.DRILLING
            elif "расточ" in op_lower or "boring" in op_lower:
                self.operation_type = OperationType.BORING
            elif "шлиф" in op_lower or "grind" in op_lower:
                self.operation_type = OperationType.GRINDING

    def add_conversation_turn(self, role: str, content: str):
        """Добавляет ход разговора в историю."""
        self.conversation_history.append({
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
            "step": self.active_step.name
        })
        self._is_dirty = True

    def add_correction(self, wrong_value: Dict[str, Any], correct_value: Dict[str, Any]):
        """Добавляет исправление от пользователя."""
        correction = {
            "timestamp": datetime.now().isoformat(),
            "context_snapshot": self.to_dict(),
            "wrong": wrong_value,
            "correct": correct_value
        }
        self.corrections_received.append(correction)
        self._is_dirty = True

    def get_missing_required_fields(self) -> List[str]:
        """Возвращает список обязательных полей, которые отсутствуют."""
        required = []
        if not self.material:
            required.append("material")
        if not self.operation:
            required.append("operation")
        return required

    def has_enough_data_for_recommendation(self) -> bool:
        """Проверяет, достаточно ли данных для рекомендации."""
        minimal_required = bool(self.material and self.operation)

        # Для некоторых операций нужен диаметр
        if self.operation_type in [OperationType.TURNING, OperationType.BORING]:
            return minimal_required and bool(self.diameter)

        return minimal_required

    def get_confidence_summary(self) -> Dict[str, float]:
        """Возвращает сводку по уверенности."""
        return {
            "overall": sum(self.confidence.values()) / max(len(self.confidence), 1),
            "details": self.confidence.copy()
        }

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация для логов."""
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,

            # Основные данные
            "material": self.material,
            "material_type": self.material_type.value if self.material_type else None,
            "operation": self.operation,
            "operation_type": self.operation_type.value if self.operation_type else None,
            "tool": self.tool,
            "diameter": self.diameter,

            # Дополнительные параметры
            "depth_of_cut": self.depth_of_cut,
            "cutting_length": self.cutting_length,
            "overhang": self.overhang,
            "width": self.width,

            # Режимы
            "modes": self.modes,
            "active_mode": self.active_mode,

            # FSM
            "active_step": self.active_step.name,
            "step_history": [step.name for step in self.step_history],

            # Уверенность
            "confidence": self.confidence,

            # Метаданные
            "recommendations_given": self.recommendations_given,
            "assumptions_made": self.assumptions_made,
            "corrections_received": len(self.corrections_received),

            # Временные метки
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "last_recommendation_at": self.last_recommendation_at.isoformat() if self.last_recommendation_at else None
        }

    def to_json(self, indent: int = 2) -> str:
        """Сериализация в JSON строку."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def reset_dialog_state(self) -> None:
        """Сбрасывает только состояние диалога, сохраняя данные."""
        self.active_step = DialogState.WAITING_START
        self.step_history.clear()
        self.recommendations_given.clear()
        self._is_dirty = True

    def complete_dialog(self) -> None:
        """Завершает диалог корректно."""
        self.active_step = DialogState.COMPLETED
        self.last_recommendation_at = datetime.now()
        self._is_dirty = True

    def mark_recommendation_given(self, mode: str):
        """Отмечает, что рекомендация дана."""
        if mode not in self.recommendations_given:
            self.recommendations_given.append(mode)
            self.last_recommendation_at = datetime.now()
            self._is_dirty = True

    def is_dirty(self) -> bool:
        """Проверяет, были ли изменения."""
        return self._is_dirty

    def mark_clean(self):
        """Отмечает контекст как чистый (сохраненный)."""
        self._is_dirty = False

    def get_recommendation_context(self) -> Dict[str, Any]:
        """Возвращает данные, необходимые для рекомендации."""
        return {
            "material": self.material,
            "material_type": self.material_type,
            "operation": self.operation,
            "operation_type": self.operation_type,
            "tool": self.tool,
            "diameter": self.diameter,
            "depth_of_cut": self.depth_of_cut,
            "active_mode": self.active_mode,
            "confidence": self.get_confidence_summary()
        }


# ======================
# МЕНЕДЖЕР КОНТЕКСТОВ (отдельный класс)
# ======================

class ContextManager:
    """Управляет всеми контекстами пользователей."""

    def __init__(self, storage_path: str = "data/contexts"):
        self._contexts: Dict[str, CuttingContext] = {}
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def get_context(self, user_id: str, create_new: bool = True) -> Optional[CuttingContext]:
        """Получает контекст пользователя."""
        if user_id in self._contexts:
            return self._contexts[user_id]

        if create_new:
            context = CuttingContext(user_id=user_id)
            self._contexts[user_id] = context
            return context

        return None

    def save_context(self, user_id: str, force: bool = False) -> bool:
        """Сохраняет контекст в файл."""
        if user_id not in self._contexts:
            return False

        context = self._contexts[user_id]

        # Сохраняем только если были изменения или принудительно
        if not force and not context.is_dirty():
            return False

        try:
            filename = self.storage_path / f"context_{user_id}_{context.session_id}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(context.to_json())

            context.mark_clean()
            return True
        except Exception as e:
            print(f"Ошибка сохранения контекста {user_id}: {e}")
            return False

    def save_all_contexts(self) -> Dict[str, bool]:
        """Сохраняет все контексты."""
        results = {}
        for user_id in self._contexts:
            results[user_id] = self.save_context(user_id, force=True)
        return results

    def load_context(self, user_id: str, session_id: Optional[str] = None) -> bool:
        """Загружает контекст из файла."""
        try:
            if session_id:
                filename = self.storage_path / f"context_{user_id}_{session_id}.json"
            else:
                # Ищем последний файл
                pattern = f"context_{user_id}_*.json"
                files = list(self.storage_path.glob(pattern))
                if not files:
                    return False
                filename = max(files, key=lambda x: x.stat().st_mtime)

            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Создаем контекст
            context = CuttingContext(user_id=user_id)

            # Восстанавливаем простые поля
            for field in ["material", "operation", "tool", "diameter",
                          "depth_of_cut", "cutting_length", "overhang", "width",
                          "modes", "active_mode", "recommendations_given"]:
                if field in data:
                    setattr(context, field, data[field])

            # Восстанавливаем Enum поля
            if data.get("material_type"):
                context.material_type = MaterialType(data["material_type"])
            if data.get("operation_type"):
                context.operation_type = OperationType(data["operation_type"])

            # Восстанавливаем FSM
            if data.get("active_step"):
                context.active_step = DialogState[data["active_step"]]

            self._contexts[user_id] = context
            context.mark_clean()
            return True

        except Exception as e:
            print(f"Ошибка загрузки контекста {user_id}: {e}")
            return False

    def reset_context(self, user_id: str) -> CuttingContext:
        """Полностью сбрасывает контекст пользователя."""
        context = CuttingContext(user_id=user_id)
        self._contexts[user_id] = context
        return context

    def delete_context(self, user_id: str) -> bool:
        """Удаляет контекст пользователя."""
        if user_id in self._contexts:
            del self._contexts[user_id]
            return True
        return False

    def get_user_ids(self) -> List[str]:
        """Возвращает список всех user_id."""
        return list(self._contexts.keys())

    def get_active_sessions(self) -> Dict[str, List[str]]:
        """Возвращает активные сессии по пользователям."""
        result = {}
        for user_id, context in self._contexts.items():
            if context.active_step != DialogState.COMPLETED:
                if user_id not in result:
                    result[user_id] = []
                result[user_id].append(context.session_id)
        return result


# ======================
# СИНГЛТОН ДЛЯ ПРОЕКТА
# ======================

# Единый менеджер контекстов для всего приложения
context_manager = ContextManager()


# Упрощенный интерфейс для быстрого доступа
def get_user_context(user_id: str, create_new: bool = True) -> Optional[CuttingContext]:
    """Быстрый доступ к контексту пользователя."""
    return context_manager.get_context(user_id, create_new)


def reset_user_context(user_id: str) -> CuttingContext:
    """Быстрый сброс контекста пользователя."""
    return context_manager.reset_context(user_id)


def save_user_context(user_id: str) -> bool:
    """Быстрое сохранение контекста."""
    return context_manager.save_context(user_id)


# ======================
# ТЕСТИРОВАНИЕ
# ======================

if __name__ == "__main__":
    # Пример использования
    ctx = get_user_context("test_user_123")

    print(f"Создан контекст: {ctx.session_id}")

    # Обновление данных
    ctx.update_field("material", "алюминий 6061", source="user", confidence=1.0)
    ctx.update_field("operation", "токарная обработка", source="user", confidence=1.0)
    ctx.update_field("diameter", 50.0, source="user", confidence=0.9)
    ctx.update_field("depth_of_cut", 2.0, source="user", confidence=0.8)

    # Добавляем ход разговора
    ctx.add_conversation_turn("user", "токарка алюминия 50 мм")
    ctx.add_conversation_turn("assistant", "Для алюминия рекомендую...")

    # Предположение
    ctx.update_field(
        "tool",
        "стандартная токарная пластина с PVD покрытием",
        source="assumption",
        confidence=0.7,
        reason="для точения алюминия обычно используют острые пластины с PVD покрытием"
    )

    # Отмечаем рекомендацию
    ctx.mark_recommendation_given("черновая обработка")

    print("\n=== Контекст ===")
    print(ctx.to_json())

    print("\n=== Недостающие поля ===")
    print(ctx.get_missing_required_fields())

    print("\n=== Достаточно данных? ===")
    print(ctx.has_enough_data_for_recommendation())

    print("\n=== Уверенность ===")
    print(ctx.get_confidence_summary())

    # Сохраняем
    save_user_context("test_user_123")

    # Загружаем
    context_manager.load_context("test_user_123")

    print("\n=== Активные сессии ===")
    print(context_manager.get_active_sessions())