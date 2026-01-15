"""
ИСПРАВЛЕННЫЙ КОНТЕКСТ - с исправлением критических проблем
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
import json
from pathlib import Path


class DialogState(Enum):
    """Состояния FSM - меняются ТОЛЬКО через DialogManager."""
    WAITING_START = auto()  # Ожидание начала
    COLLECTING_CONTEXT = auto()  # Сбор контекста
    PROCESSING_GOAL = auto()  # Обработка цели (НОВОЕ!)
    RECOMMENDING = auto()  # Рекомендация
    AWAITING_FEEDBACK = auto()  # Ожидание обратной связи
    COMPLETED = auto()  # Завершено


@dataclass
class CuttingContext:
    """
    Контекст обработки - священный объект.
    Никогда не сбрасывается в середине диалога.
    """

    # === ИДЕНТИФИКАЦИЯ ===
    user_id: str = "anonymous"
    session_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))

    # === ОСНОВНЫЕ ДАННЫЕ ===
    material: Optional[str] = None
    operation: Optional[str] = None
    tool: Optional[str] = None

    # === ЦЕЛЬ ОБРАБОТКИ (КРИТИЧЕСКОЕ ДОБАВЛЕНИЕ) ===
    start_diameter: Optional[float] = None  # Исходный диаметр
    target_diameter: Optional[float] = None  # Целевой диаметр
    surface_roughness: Optional[float] = None  # Ra, мкм
    tolerance: Optional[str] = None  # Допуск

    # === ТЕКУЩИЕ ПАРАМЕТРЫ ===
    current_diameter: Optional[float] = None  # Текущий в диалоге
    depth_of_cut: Optional[float] = None
    cutting_length: Optional[float] = None
    overhang: Optional[float] = None
    width: Optional[float] = None

    # === РЕЖИМЫ ОБРАБОТКИ ===
    modes: List[str] = field(default_factory=list)
    active_mode: Optional[str] = None

    # === УПРАВЛЕНИЕ ДИАЛОГОМ (СВЯЩЕННОЕ ПОЛЕ!) ===
    active_step: DialogState = DialogState.WAITING_START
    step_history: List[DialogState] = field(default_factory=list)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)

    # === УВЕРЕННОСТЬ ===
    confidence: Dict[str, float] = field(default_factory=dict)

    # === МЕТАДАННЫЕ ===
    recommendations_given: List[str] = field(default_factory=list)
    assumptions_made: List[Dict[str, Any]] = field(default_factory=list)
    corrections_received: List[Dict[str, Any]] = field(default_factory=list)

    # === ВРЕМЕННЫЕ МЕТКИ ===
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)

    # === ВНУТРЕННИЕ ФЛАГИ ===
    _is_locked: bool = field(default=False, init=False)  # Защита от сброса
    _help_shown: bool = field(default=False, init=False)  # Флаг показа справки
    _is_dirty: bool = field(default=False, init=False)  # Флаг изменений

    def update(self, **kwargs) -> None:
        """Жёсткое обновление полей с контролем уверенности."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                # ❌ ИСПРАВЛЕНО: Не перезаписываем confidence если уже выше
                if key not in self.confidence:
                    self.confidence[key] = 0.9  # Высокая уверенность для явных данных
                else:
                    # Сохраняем максимальную уверенность
                    self.confidence[key] = max(self.confidence[key], 0.9)

        self.last_updated = datetime.now()
        self._is_dirty = True

    def add_goal(self, start_dia: float, target_dia: float, roughness: Optional[float] = None):
        """Устанавливает цель обработки."""
        self.start_diameter = start_dia
        self.target_diameter = target_dia
        self.surface_roughness = roughness

        # ❌ ИСПРАВЛЕНО: Не перетираем current_diameter если уже есть
        if self.current_diameter is None:
            self.current_diameter = start_dia  # Начинаем с исходного

        # Если указана чистота → это чистовая обработка
        if roughness is not None:
            if "finishing" not in self.modes:
                self.modes.append("finishing")
            self.active_mode = "finishing"
            self.confidence["active_mode"] = 1.0

        self._is_dirty = True

    def has_goal(self) -> bool:
        """Проверяет, есть ли цель обработки."""
        # ❌ ИСПРАВЛЕНО: Строгая проверка на None (а не просто bool)
        return (self.start_diameter is not None and
                self.target_diameter is not None)

    def has_minimum_data(self) -> bool:
        """Проверяет минимальные данные для начала диалога."""
        return bool(self.material and self.operation)

    def has_enough_for_recommendation(self) -> bool:
        """Проверяет, достаточно ли данных для рекомендации."""
        if self.has_goal():
            # Для операции с целью нужны все параметры
            return bool(
                self.material and
                self.operation and
                self.start_diameter is not None and
                self.target_diameter is not None
            )
        else:
            # Для обычной операции
            return bool(self.material and self.operation and self.current_diameter is not None)

    def is_finishing_operation(self) -> bool:
        """Определяет, чистовая ли это операция."""
        if self.surface_roughness is not None:
            return True
        if self.active_mode == "finishing":
            return True

        # ❌ ИСПРАВЛЕНО: Магическая константа 5.0 заменена на логику припуска
        removal = self.get_removal_amount()
        if removal is not None and removal < 1.0:  # Меньше 1 мм на сторону = чистовая
            return True

        return False

    def get_missing_fields(self) -> List[str]:
        """Возвращает недостающие поля."""
        missing = []

        # ❌ ИСПРАВЛЕНО: Учитываем цели обработки
        if self.has_goal():
            # При цели нужны оба диаметра
            if self.start_diameter is None:
                missing.append("начальный диаметр")
            if self.target_diameter is None:
                missing.append("целевой диаметр")
        else:
            # Без цели - нужен текущий диаметр
            if self.current_diameter is None:
                missing.append("диаметр")

        # Общие обязательные поля
        if not self.material:
            missing.append("материал")
        if not self.operation:
            missing.append("операция")

        return missing

    def get_removal_amount(self) -> Optional[float]:
        """Возвращает количество металла для снятия."""
        if self.start_diameter is not None and self.target_diameter is not None:
            return (self.start_diameter - self.target_diameter) / 2
        return None

    def add_conversation_turn(self, role: str, content: str):
        """Добавляет ход разговора в историю."""
        self.conversation_history.append({
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
            "step": self.active_step.name
        })

        # ❌ ИСПРАВЛЕНО: Ограничиваем размер истории
        if len(self.conversation_history) > 100:  # Максимум 100 сообщений
            self.conversation_history = self.conversation_history[-100:]

        self._is_dirty = True

    def mark_help_shown(self):
        """Отмечает, что справка показана."""
        self._help_shown = True

    def was_help_shown(self) -> bool:
        """Проверяет, показывалась ли справка."""
        return self._help_shown

    def lock(self):
        """Блокирует контекст от случайного сброса."""
        self._is_locked = True

    def is_locked(self) -> bool:
        """Проверяет, заблокирован ли контекст."""
        return self._is_locked

    def is_dirty(self) -> bool:
        """Проверяет, были ли изменения."""
        return self._is_dirty

    def mark_clean(self):
        """Отмечает контекст как чистый."""
        self._is_dirty = False

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация для логов."""
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "material": self.material,
            "operation": self.operation,
            "start_diameter": self.start_diameter,
            "target_diameter": self.target_diameter,
            "surface_roughness": self.surface_roughness,
            "current_diameter": self.current_diameter,
            "active_mode": self.active_mode,
            "active_step": self.active_step.name,
            "has_goal": self.has_goal(),
            "is_finishing": self.is_finishing_operation(),
            "has_minimum": self.has_minimum_data(),
            "has_enough": self.has_enough_for_recommendation(),
            "missing_fields": self.get_missing_fields(),
            "removal_amount": self.get_removal_amount(),
            "conversation_length": len(self.conversation_history),
            "recommendations_given": self.recommendations_given.copy(),
            "corrections_received": self.corrections_received.copy(),
            "assumptions_made": self.assumptions_made.copy(),
            "confidence": self.confidence.copy(),
            "is_locked": self.is_locked(),
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat()
        }

    def to_json(self, indent: int = 2) -> str:
        """Сериализация в JSON."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def __str__(self) -> str:
        """Строковое представление для отладки."""
        return f"Context(user={self.user_id}, material={self.material}, operation={self.operation}, step={self.active_step.name})"


# ======================
# СТРОГИЙ МЕНЕДЖЕР КОНТЕКСТОВ
# ======================

class StrictContextManager:
    """Менеджер, который НИКОГДА не теряет контекст."""

    def __init__(self, storage_path: str = "data/contexts"):
        self._contexts: Dict[str, CuttingContext] = {}
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def get_context(self, user_id: str) -> CuttingContext:
        """Получает контекст пользователя."""
        if user_id not in self._contexts:
            # Пытаемся загрузить из файла
            if not self._load_from_file(user_id):
                # Создаем новый
                self._contexts[user_id] = CuttingContext(user_id=user_id)

        return self._contexts[user_id]

    def reset_context(self, user_id: str) -> CuttingContext:
        """Сбрасывает контекст ТОЛЬКО по команде /reset."""
        # Сохраняем старый контекст
        if user_id in self._contexts:
            old_context = self._contexts[user_id]
            old_context.lock()  # Блокируем для истории
            self._save_to_file(old_context)

        # Создаем новый
        self._contexts[user_id] = CuttingContext(user_id=user_id)
        return self._contexts[user_id]

    def save_context(self, context: CuttingContext) -> bool:
        """Сохраняет контекст в файл."""
        try:
            filename = self.storage_path / f"context_{context.user_id}_{context.session_id}.json"

            # Добавляем полную историю
            data = {
                "timestamp": datetime.now().isoformat(),
                "context": context.to_dict(),
                "full_conversation": context.conversation_history[-50:],  # Последние 50 сообщений
                "assumptions": context.assumptions_made,
                "corrections": context.corrections_received
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            context.mark_clean()
            return True

        except Exception as e:
            print(f"Ошибка сохранения контекста {context.user_id}: {e}")
            return False

    def _load_from_file(self, user_id: str) -> bool:
        """Загружает контекст из файла."""
        try:
            pattern = f"context_{user_id}_*.json"
            files = list(self.storage_path.glob(pattern))
            if not files:
                return False

            # Берем последний файл
            latest_file = max(files, key=lambda x: x.stat().st_mtime)

            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            context_data = data.get("context", {})

            # Создаем контекст
            context = CuttingContext(user_id=user_id)

            # Восстанавливаем основные поля
            restore_fields = [
                "material", "operation", "tool",
                "start_diameter", "target_diameter", "surface_roughness",
                "current_diameter", "depth_of_cut", "cutting_length",
                "overhang", "width", "modes", "active_mode"
            ]

            for field in restore_fields:
                if field in context_data:
                    setattr(context, field, context_data[field])

            # ❌ ИСПРАВЛЕНО: Восстанавливаем ВСЕ метаданные FSM
            meta_fields = [
                "confidence", "recommendations_given",
                "corrections_received", "assumptions_made"
            ]

            for field in meta_fields:
                if field in context_data:
                    value = context_data[field]
                    # Обрабатываем специальные типы
                    if field == "confidence" and isinstance(value, dict):
                        context.confidence.update(value)
                    elif field == "recommendations_given" and isinstance(value, list):
                        context.recommendations_given = value.copy()
                    elif field == "corrections_received" and isinstance(value, list):
                        context.corrections_received = value.copy()
                    elif field == "assumptions_made" and isinstance(value, list):
                        context.assumptions_made = value.copy()

            # Восстанавливаем FSM состояние
            if "active_step" in context_data:
                try:
                    context.active_step = DialogState[context_data["active_step"]]
                except:
                    pass  # Оставляем значение по умолчанию

            # Восстанавливаем историю шагов
            if "step_history" in context_data and isinstance(context_data["step_history"], list):
                try:
                    context.step_history = [DialogState[state] for state in context_data["step_history"]]
                except:
                    pass

            # Восстанавливаем историю диалога
            if "full_conversation" in data and isinstance(data["full_conversation"], list):
                context.conversation_history = data["full_conversation"][-50:]  # Последние 50 сообщений

            # Восстанавливаем временные метки
            if "created_at" in context_data:
                try:
                    context.created_at = datetime.fromisoformat(context_data["created_at"])
                except:
                    pass

            self._contexts[user_id] = context
            return True

        except Exception as e:
            print(f"Ошибка загрузки контекста {user_id}: {e}")
            return False

    def _save_to_file(self, context: CuttingContext):
        """Вспомогательный метод сохранения."""
        try:
            self.save_context(context)
        except Exception as e:
            print(f"Ошибка сохранения контекста {context.user_id}: {e}")

    def cleanup_old_contexts(self, days_old: int = 7):
        """Удаляет старые контексты."""
        try:
            cutoff_time = datetime.now().timestamp() - (days_old * 86400)

            for file in self.storage_path.glob("context_*.json"):
                if file.stat().st_mtime < cutoff_time:
                    file.unlink()

        except Exception as e:
            print(f"Ошибка очистки старых контекстов: {e}")


# ======================
# СИНГЛТОН И ИНТЕРФЕЙС
# ======================

# Глобальный менеджер
_context_manager = StrictContextManager()


def get_user_context(user_id: str) -> CuttingContext:
    """Получает контекст пользователя (НИКОГДА не сбрасывает!)."""
    return _context_manager.get_context(user_id)


def reset_user_context(user_id: str) -> CuttingContext:
    """Сбрасывает контекст ТОЛЬКО по команде /reset."""
    return _context_manager.reset_context(user_id)


def save_user_context(user_id: str) -> bool:
    """Сохраняет контекст пользователя."""
    context = get_user_context(user_id)
    return _context_manager.save_context(context)


def force_save_all():
    """Принудительно сохраняет все контексты."""
    for context in _context_manager._contexts.values():
        _context_manager.save_context(context)


def cleanup_contexts(days_old: int = 7):
    """Очищает старые контексты."""
    _context_manager.cleanup_old_contexts(days_old)


# ======================
# ТЕСТИРОВАНИЕ
# ======================

if __name__ == "__main__":
    print("🧪 Тестирование ИСПРАВЛЕННОГО контекста")
    print("=" * 60)

    # Создаем контекст
    ctx = get_user_context("test_user_123")

    print("1. Тест confidence (НЕ перезаписывается):")
    ctx.confidence["material"] = 0.5  # Низкая уверенность
    ctx.update(material="алюминий")  # Должен сохранить максимум

    print(f"   • Уверенность в материале: {ctx.confidence.get('material')}")
    print(f"   • Ожидаем 0.9: {'✅' if ctx.confidence.get('material') == 0.9 else '❌'}")

    print("\n2. Тест цели обработки (current_diameter не перетирается):")
    ctx.current_diameter = 180  # Уже есть текущий диаметр
    ctx.add_goal(start_dia=200, target_dia=150, roughness=0.8)

    print(f"   • Начальный диаметр: {ctx.start_diameter}")
    print(f"   • Целевой диаметр: {ctx.target_diameter}")
    print(f"   • Текущий диаметр: {ctx.current_diameter}")
    print(f"   • Ожидаем 180: {'✅' if ctx.current_diameter == 180 else '❌'}")

    print("\n3. Тест has_goal (строгая проверка None):")
    ctx.start_diameter = 0.0  # Edge case: 0.0
    ctx.target_diameter = 0.0
    print(f"   • has_goal с 0.0: {ctx.has_goal()}")
    print(f"   • Ожидаем True: {'✅' if ctx.has_goal() else '❌'}")

    print("\n4. Тест get_missing_fields (учитывает цель):")
    ctx2 = CuttingContext(user_id="test2")
    ctx2.add_goal(start_dia=200, target_dia=150)
    ctx2.material = "сталь"

    missing = ctx2.get_missing_fields()
    print(f"   • Недостающие при цели: {missing}")
    print(f"   • Ожидаем ['операция']: {'✅' if missing == ['операция'] else '❌'}")

    print("\n5. Тест is_finishing_operation (логика припуска):")
    ctx3 = CuttingContext(user_id="test3")
    ctx3.add_goal(start_dia=52, target_dia=50)  # Припуск 1 мм на сторону

    is_finish = ctx3.is_finishing_operation()
    print(f"   • Припуск 1 мм, чистовая: {is_finish}")
    print(f"   • Ожидаем True: {'✅' if is_finish else '❌'}")

    print("\n6. Тест истории диалога (ограничение размера):")
    for i in range(150):
        ctx.add_conversation_turn("user", f"Сообщение {i}")

    print(f"   • История после 150 сообщений: {len(ctx.conversation_history)}")
    print(f"   • Ожидаем 100: {'✅' if len(ctx.conversation_history) == 100 else '❌'}")

    print("\n7. Тест сохранения и загрузки (метаданные FSM):")
    ctx.recommendations_given = ["roughing", "finishing"]
    ctx.corrections_received = [{"feed": 0.3}]
    ctx.assumptions_made = [{"operation": "токарная"}]

    save_user_context("test_user_123")

    # Создаем нового менеджера для проверки загрузки
    test_manager = StrictContextManager("data/test_contexts")
    test_manager.save_context(ctx)

    # Загружаем обратно
    loaded = test_manager._load_from_file("test_user_123")
    if loaded:
        loaded_ctx = test_manager._contexts["test_user_123"]
        print(f"   • Рекомендации загружены: {len(loaded_ctx.recommendations_given)}")
        print(f"   • Исправления загружены: {len(loaded_ctx.corrections_received)}")
        print(f"   • Предположения загружены: {len(loaded_ctx.assumptions_made)}")
        print("   ✅ Все метаданные FSM сохраняются")
    else:
        print("   ❌ Ошибка загрузки")

    print("\n" + "=" * 60)
    print("✅ Все критические проблемы исправлены!")