# core/memory/memory_manager.py
import json
import pickle
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set
from pathlib import Path
import hashlib
from dataclasses import dataclass, asdict, field
import numpy as np
from collections import defaultdict


@dataclass
class DialogMemory:
    """Память одного диалога."""
    dialog_id: str
    user_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    context_snapshot: Dict[str, Any] = field(default_factory=dict)
    messages: List[Dict[str, str]] = field(default_factory=list)
    corrections: List[Dict[str, Any]] = field(default_factory=list)
    final_outcome: Optional[str] = None
    learned_patterns: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dialog_id": self.dialog_id,
            "user_id": self.user_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "context": self.context_snapshot,
            "message_count": len(self.messages),
            "corrections": self.corrections,
            "final_outcome": self.final_outcome,
            "learned_patterns": self.learned_patterns
        }


@dataclass
class UserMemory:
    """Долговременная память пользователя."""
    user_id: str
    first_seen: datetime
    last_seen: datetime
    total_dialogs: int = 0
    preferred_materials: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    preferred_operations: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    typical_parameters: Dict[str, List[float]] = field(default_factory=dict)
    corrections_history: List[Dict[str, Any]] = field(default_factory=list)
    feedback_history: List[Dict[str, Any]] = field(default_factory=list)
    custom_rules: Dict[str, Any] = field(default_factory=dict)

    def update_preferences(self, material: str, operation: str, params: Dict[str, float]):
        """Обновляет предпочтения пользователя."""
        self.preferred_materials[material] += 1
        self.preferred_operations[operation] += 1

        for param, value in params.items():
            if param not in self.typical_parameters:
                self.typical_parameters[param] = []
            self.typical_parameters[param].append(value)
            # Храним только последние 10 значений
            if len(self.typical_parameters[param]) > 10:
                self.typical_parameters[param] = self.typical_parameters[param][-10:]

    def get_typical_value(self, param: str) -> Optional[float]:
        """Возвращает типичное значение параметра для пользователя."""
        if param in self.typical_parameters and self.typical_parameters[param]:
            return np.median(self.typical_parameters[param])
        return None

    def get_favorite_material(self) -> Optional[str]:
        """Возвращает самый часто используемый материал."""
        if self.preferred_materials:
            return max(self.preferred_materials.items(), key=lambda x: x[1])[0]
        return None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MemoryManager:
    """Управляет долговременной памятью ассистента."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.dialogs_file = self.data_dir / "logs" / "dialogs.jsonl"
        self.corrections_file = self.data_dir / "logs" / "corrections.jsonl"
        self.user_memory_dir = self.data_dir / "memory" / "users"
        self.patterns_file = self.data_dir / "memory" / "patterns.pkl"

        # Создаем директории
        self.dialogs_file.parent.mkdir(parents=True, exist_ok=True)
        self.user_memory_dir.mkdir(parents=True, exist_ok=True)

        # Кэши
        self._user_memories: Dict[str, UserMemory] = {}
        self._patterns: Optional[Dict[str, Any]] = None

        # Загружаем существующие данные
        self._load_patterns()

    def log_dialog(self, context, messages: List[Dict[str, str]],
                   corrections: List[Dict[str, Any]], outcome: str):
        """Логирует полный диалог."""
        dialog_memory = DialogMemory(
            dialog_id=self._generate_dialog_id(context.user_id),
            user_id=context.user_id,
            start_time=context.created_at,
            end_time=datetime.now(),
            context_snapshot=context.to_dict(),
            messages=messages.copy(),
            corrections=corrections.copy(),
            final_outcome=outcome
        )

        # Извлекаем паттерны для обучения
        patterns = self._extract_patterns(dialog_memory)
        dialog_memory.learned_patterns = patterns

        # Сохраняем в JSONL
        with open(self.dialogs_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(dialog_memory.to_dict(), ensure_ascii=False) + '\n')

        # Обновляем память пользователя
        self._update_user_memory(context.user_id, dialog_memory)

        # Обновляем глобальные паттерны
        self._update_patterns(patterns)

        return dialog_memory.dialog_id

    def log_correction(self, user_id: str, wrong: Dict[str, Any],
                       correct: Dict[str, Any], context_snapshot: Dict[str, Any]):
        """Логирует исправление от пользователя."""
        correction_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "wrong": wrong,
            "correct": correct,
            "context": context_snapshot,
            "type": self._classify_correction(wrong, correct)
        }

        with open(self.corrections_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(correction_entry, ensure_ascii=False) + '\n')

        # Добавляем в память пользователя
        user_memory = self.get_user_memory(user_id)
        user_memory.corrections_history.append(correction_entry)
        self._save_user_memory(user_memory)

        return correction_entry

    def get_user_memory(self, user_id: str) -> UserMemory:
        """Получает память пользователя."""
        if user_id not in self._user_memories:
            self._load_user_memory(user_id)
        return self._user_memories[user_id]

    def get_user_preferences(self, user_id: str, field: str) -> Optional[Any]:
        """Возвращает предпочтения пользователя по полю."""
        user_memory = self.get_user_memory(user_id)

        if field == "material":
            return user_memory.get_favorite_material()
        elif field == "operation":
            if user_memory.preferred_operations:
                return max(user_memory.preferred_operations.items(), key=lambda x: x[1])[0]
        elif field in ["diameter", "depth_of_cut", "feed", "speed"]:
            return user_memory.get_typical_value(field)

        return None

    def find_similar_contexts(self, current_context: Dict[str, Any],
                              limit: int = 5) -> List[Dict[str, Any]]:
        """Находит похожие контексты в истории."""
        similar = []

        # Читаем последние N диалогов
        try:
            with open(self.dialogs_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()[-100:]  # Последние 100 диалогов

                for line in lines:
                    dialog = json.loads(line.strip())

                    # Вычисляем схожесть
                    similarity = self._calculate_similarity(
                        current_context,
                        dialog["context"]
                    )

                    if similarity > 0.6:  # Порог схожести
                        similar.append({
                            "dialog": dialog,
                            "similarity": similarity,
                            "outcome": dialog.get("final_outcome")
                        })

        except FileNotFoundError:
            pass

        # Сортируем по схожести
        similar.sort(key=lambda x: x["similarity"], reverse=True)
        return similar[:limit]

    def learn_from_feedback(self, user_id: str, feedback: Dict[str, Any]):
        """Обучается на основе обратной связи."""
        user_memory = self.get_user_memory(user_id)
        user_memory.feedback_history.append({
            "timestamp": datetime.now().isoformat(),
            "feedback": feedback
        })

        # Извлекаем правила из фидбека
        if "corrected_parameters" in feedback:
            for param, value in feedback["corrected_parameters"].items():
                rule_key = f"{user_id}_{param}"
                self._patterns["user_specific_rules"][rule_key] = {
                    "value": value,
                    "confidence": 0.9,
                    "source": f"feedback_from_{user_id}",
                    "timestamp": datetime.now().isoformat()
                }

        self._save_user_memory(user_memory)
        self._save_patterns()

    def suggest_based_on_history(self, user_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Предлагает параметры на основе истории."""
        suggestions = {}

        # 1. Предпочтения пользователя
        user_memory = self.get_user_memory(user_id)

        # 2. Похожие контексты
        similar = self.find_similar_contexts(context, limit=3)

        # 3. Глобальные паттерны
        material = context.get("material")
        operation = context.get("operation")

        if material and operation:
            pattern_key = f"{material}_{operation}"
            if pattern_key in self._patterns.get("global_patterns", {}):
                suggestions.update(self._patterns["global_patterns"][pattern_key])

        # 4. Пользовательские правила
        for key, rule in self._patterns.get("user_specific_rules", {}).items():
            if key.startswith(user_id):
                param = key.split("_")[-1]
                suggestions[param] = {
                    "value": rule["value"],
                    "confidence": rule["confidence"],
                    "source": "user_history"
                }

        # 5. Агрегируем из похожих контекстов
        if similar:
            param_values = defaultdict(list)
            for sim in similar:
                dialog_context = sim["dialog"]["context"]
                for param in ["feed", "speed", "depth_of_cut"]:
                    if param in dialog_context:
                        param_values[param].append(dialog_context[param])

            for param, values in param_values.items():
                if values:
                    suggestions[param] = {
                        "value": np.median(values),
                        "confidence": min(0.8, len(values) / 10),
                        "source": "similar_cases"
                    }

        return suggestions

    # ==================== ПРИВАТНЫЕ МЕТОДЫ ====================

    def _load_user_memory(self, user_id: str):
        """Загружает память пользователя из файла."""
        user_file = self.user_memory_dir / f"{user_id}.json"

        if user_file.exists():
            with open(user_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

                # Конвертируем строки в datetime
                data["first_seen"] = datetime.fromisoformat(data["first_seen"])
                data["last_seen"] = datetime.fromisoformat(data["last_seen"])

                # Конвертируем defaultdict обратно
                data["preferred_materials"] = defaultdict(int, data["preferred_materials"])
                data["preferred_operations"] = defaultdict(int, data["preferred_operations"])

                self._user_memories[user_id] = UserMemory(**data)
        else:
            # Создаем новую память
            now = datetime.now()
            self._user_memories[user_id] = UserMemory(
                user_id=user_id,
                first_seen=now,
                last_seen=now
            )

    def _save_user_memory(self, user_memory: UserMemory):
        """Сохраняет память пользователя в файл."""
        user_file = self.user_memory_dir / f"{user_memory.user_id}.json"

        # Обновляем время последнего визита
        user_memory.last_seen = datetime.now()

        # Конвертируем в словарь
        data = user_memory.to_dict()
        data["first_seen"] = data["first_seen"].isoformat()
        data["last_seen"] = data["last_seen"].isoformat()

        # Конвертируем defaultdict в обычные dict
        data["preferred_materials"] = dict(data["preferred_materials"])
        data["preferred_operations"] = dict(data["preferred_operations"])

        with open(user_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_patterns(self):
        """Загружает глобальные паттерны."""
        if self.patterns_file.exists():
            with open(self.patterns_file, 'rb') as f:
                self._patterns = pickle.load(f)
        else:
            self._patterns = {
                "global_patterns": {},
                "user_specific_rules": {},
                "material_operations": defaultdict(dict),
                "correction_patterns": []
            }

    def _save_patterns(self):
        """Сохраняет глобальные паттерны."""
        with open(self.patterns_file, 'wb') as f:
            pickle.dump(self._patterns, f)

    def _update_user_memory(self, user_id: str, dialog: DialogMemory):
        """Обновляет память пользователя на основе диалога."""
        user_memory = self.get_user_memory(user_id)

        user_memory.total_dialogs += 1

        # Извлекаем параметры из контекста
        context = dialog.context_snapshot
        material = context.get("material")
        operation = context.get("operation")

        if material and operation:
            # Собираем параметры
            params = {}
            for param in ["diameter", "depth_of_cut", "feed", "speed"]:
                if param in context:
                    params[param] = context[param]

            user_memory.update_preferences(material, operation, params)

        self._save_user_memory(user_memory)

    def _extract_patterns(self, dialog: DialogMemory) -> List[Dict[str, Any]]:
        """Извлекает паттерны из диалога."""
        patterns = []
        context = dialog.context_snapshot

        # Паттерн: материал + операция -> параметры
        if context.get("material") and context.get("operation"):
            pattern_key = f"{context['material']}_{context['operation']}"

            pattern = {
                "type": "material_operation",
                "key": pattern_key,
                "parameters": {},
                "frequency": 1
            }

            for param in ["feed", "speed", "depth_of_cut"]:
                if param in context:
                    pattern["parameters"][param] = context[param]

            patterns.append(pattern)

        # Паттерны из исправлений
        for correction in dialog.corrections:
            pattern = {
                "type": "correction",
                "wrong": correction.get("wrong"),
                "correct": correction.get("correct"),
                "context": correction.get("context", {}),
                "timestamp": datetime.now().isoformat()
            }
            patterns.append(pattern)

        return patterns

    def _update_patterns(self, new_patterns: List[Dict[str, Any]]):
        """Обновляет глобальные паттерны."""
        for pattern in new_patterns:
            if pattern["type"] == "material_operation":
                key = pattern["key"]

                if key not in self._patterns["global_patterns"]:
                    self._patterns["global_patterns"][key] = {
                        "parameters": pattern["parameters"],
                        "frequency": 1,
                        "first_seen": datetime.now().isoformat(),
                        "last_seen": datetime.now().isoformat()
                    }
                else:
                    # Обновляем существующий паттерн
                    existing = self._patterns["global_patterns"][key]

                    # Усредняем параметры
                    for param, value in pattern["parameters"].items():
                        if param in existing["parameters"]:
                            # Взвешенное среднее
                            old_val = existing["parameters"][param]
                            old_freq = existing["frequency"]
                            existing["parameters"][param] = (old_val * old_freq + value) / (old_freq + 1)
                        else:
                            existing["parameters"][param] = value

                    existing["frequency"] += 1
                    existing["last_seen"] = datetime.now().isoformat()

            elif pattern["type"] == "correction":
                self._patterns["correction_patterns"].append(pattern)

    def _calculate_similarity(self, context1: Dict[str, Any], context2: Dict[str, Any]) -> float:
        """Вычисляет схожесть двух контекстов."""
        score = 0.0
        total_weights = 0.0

        # Веса полей
        weights = {
            "material": 0.4,
            "operation": 0.3,
            "diameter": 0.2,
            "tool": 0.1
        }

        for field, weight in weights.items():
            val1 = context1.get(field)
            val2 = context2.get(field)

            if val1 and val2:
                if val1 == val2:
                    score += weight
                total_weights += weight
            elif not val1 and not val2:
                total_weights += weight

        return score / total_weights if total_weights > 0 else 0.0

    def _classify_correction(self, wrong: Dict[str, Any], correct: Dict[str, Any]) -> str:
        """Классифицирует тип исправления."""
        if "feed" in wrong or "feed" in correct:
            return "feed_correction"
        elif "speed" in wrong or "speed" in correct:
            return "speed_correction"
        elif "depth" in wrong or "depth" in correct:
            return "depth_correction"
        elif "tool" in wrong or "tool" in correct:
            return "tool_correction"
        return "general_correction"

    def _generate_dialog_id(self, user_id: str) -> str:
        """Генерирует уникальный ID диалога."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        hash_str = hashlib.md5(f"{user_id}_{timestamp}".encode()).hexdigest()[:8]
        return f"{user_id}_{timestamp}_{hash_str}"


# ==================== ИНТЕГРАЦИЯ С АССИСТЕНТОМ ====================

class ContextWithMemory:
    """Расширенный контекст с доступом к памяти."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.context = None
        self.memory_manager = MemoryManager()
        self.user_memory = self.memory_manager.get_user_memory(user_id)

    def get_personalized_suggestions(self) -> Dict[str, Any]:
        """Получает персонализированные предложения."""
        if not self.context:
            return {}

        context_dict = self.context.to_dict()
        return self.memory_manager.suggest_based_on_history(
            self.user_id,
            context_dict
        )

    def apply_learned_patterns(self):
        """Применяет изученные паттерны к контексту."""
        suggestions = self.get_personalized_suggestions()

        for param, suggestion in suggestions.items():
            if suggestion["confidence"] > 0.7:  # Высокая уверенность
                if hasattr(self.context, param):
                    current_value = getattr(self.context, param)
                    if not current_value:  # Только если поле пустое
                        self.context.update_field(
                            param,
                            suggestion["value"],
                            source="learned_pattern",
                            confidence=suggestion["confidence"],
                            reason=f"На основе истории использования (уверенность: {suggestion['confidence']:.0%})"
                        )

    def log_interaction(self, messages: List[Dict[str, str]],
                        corrections: List[Dict[str, Any]], outcome: str):
        """Логирует взаимодействие."""
        return self.memory_manager.log_dialog(
            self.context,
            messages,
            corrections,
            outcome
        )


# Синглтон менеджера памяти
memory_manager = MemoryManager()
