"""
Чистая логика диалога (FSM) для CNC Assistant.
Отвечает только за переходы состояний и валидацию ввода.
"""

import re
from typing import Dict, Any, Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# КЛАССЫ СОСТОЯНИЙ ДИАЛОГА
# ============================================================================

class UserState:
    """Состояния пользователя в диалоге."""

    class _State:
        def __init__(self, name):
            self.state = name

    waiting_material = _State("UserState:waiting_material")
    waiting_operation = _State("UserState:waiting_operation")
    waiting_machine_type = _State("UserState:waiting_machine_type")
    waiting_mode = _State("UserState:waiting_mode")
    waiting_tool_diameter = _State("UserState:waiting_tool_diameter")
    waiting_turning_start_diameter = _State("UserState:waiting_turning_start_diameter")
    waiting_turning_finish_diameter = _State("UserState:waiting_turning_finish_diameter")
    waiting_turning_tool_type = _State("UserState:waiting_turning_tool_type")
    waiting_turning_tool_material = _State("UserState:waiting_turning_tool_material")
    waiting_turning_tool_radius = _State("UserState:waiting_turning_tool_radius")
    waiting_turning_tool_overhang = _State("UserState:waiting_turning_tool_overhang")
    waiting_recommendation = _State("UserState:waiting_recommendation")
    waiting_user_choice = _State("UserState:waiting_user_choice")


# ============================================================================
# ВАЛИДАТОРЫ ВВОДА (ЧИСТАЯ ВАЛИДАЦИЯ БИЗНЕС-ЛОГИКИ)
# ============================================================================

class InputValidator:
    """Валидатор пользовательского ввода."""

    @staticmethod
    def validate_material(material: str) -> bool:
        """Проверить корректность материала."""
        valid_materials = ["сталь", "алюминий", "титан", "нержавейка", "чугун"]
        return material.lower() in valid_materials

    @staticmethod
    def validate_operation(operation: str) -> bool:
        """Проверить корректность операции."""
        valid_operations = ["токарка", "фрезерование", "сверление", "растачивание"]
        return operation.lower() in valid_operations

    @staticmethod
    def validate_machine_type(operation: str, machine_type: str) -> bool:
        """Проверить корректность типа станка для операции."""
        machine_map = {
            'токарка': ['чпу токарка', 'обычная токарка'],
            'фрезерование': ['чпу фрезер', 'обычная фрезер'],
            'сверление': ['чпу сверление', 'обычное сверление'],
            'растачивание': ['чпу сверление', 'обычное сверление']
        }
        valid_machines = machine_map.get(operation.lower(), [])
        return machine_type.lower() in [m.lower() for m in valid_machines]

    @staticmethod
    def validate_diameter(diameter: float, min_val: float = 0.1, max_val: float = 800) -> Tuple[bool, List[str]]:
        """Проверить корректность диаметра."""
        errors = []
        if not (min_val <= diameter <= max_val):
            errors.append(f"Диаметр должен быть от {min_val} до {max_val} мм")
        return len(errors) == 0, errors

    @staticmethod
    def validate_turning_diameters(start: float, finish: float) -> Tuple[bool, List[str]]:
        """Проверить логическую корректность диаметров для токарки."""
        errors = []

        # Базовые проверки
        start_valid, start_errors = InputValidator.validate_diameter(start)
        finish_valid, finish_errors = InputValidator.validate_diameter(finish, 0.1, start)

        errors.extend(start_errors)
        errors.extend(finish_errors)

        if finish >= start:
            errors.append("Конечный диаметр должен быть меньше начального")

        if start > 0 and finish > 0:
            ratio = finish / start
            if ratio < 0.1:
                errors.append("Слишком большое отношение диаметров (опасно!)")

        return len(errors) == 0, errors

    @staticmethod
    def validate_mode(mode: str) -> bool:
        """Проверить корректность режима обработки."""
        valid_modes = ["черновой", "получистовой", "чистовой"]
        return mode in valid_modes

    @staticmethod
    def validate_tool_type(machine_type: str, tool_type: str) -> bool:
        """Проверить корректность типа инструмента для станка."""
        is_cnc = "чпу" in machine_type.lower()

        if is_cnc:
            valid_tools = ["проходной (80°)", "чистовой (80°)", "канавочный",
                           "резьбовой (60°)", "отрезной", "расточной (90°)"]
        else:
            valid_tools = ["проходной (35°)", "чистовой (35°)", "канавочный",
                           "резьбовой (60°)", "отрезной", "расточной (35°)"]

        return tool_type in valid_tools

    @staticmethod
    def validate_tool_material(material: str) -> bool:
        """Проверить корректность материала инструмента."""
        valid_materials = ["твердый сплав", "быстрорежущая сталь", "керамика",
                           "кубический нитрид бора"]
        return material in valid_materials

    @staticmethod
    def validate_tool_radius(machine_type: str, radius: float) -> Tuple[bool, List[str]]:
        """Проверить корректность радиуса инструмента."""
        errors = []
        is_cnc = "чпу" in machine_type.lower()

        if is_cnc:
            if not (0.4 <= radius <= 1.0):
                errors.append("Для ЧПУ радиус должен быть от 0.4 до 1.0 мм")
        else:
            if not (1.2 <= radius <= 2.4):
                errors.append("Для обычной токарки радиус должен быть от 1.2 до 2.4 мм")

        return len(errors) == 0, errors

    @staticmethod
    def validate_tool_overhang(overhang: float) -> Tuple[bool, List[str]]:
        """Проверить корректность вылета инструмента."""
        errors = []
        if not (10 <= overhang <= 500):
            errors.append("Вылет инструмента должен быть от 10 до 500 мм")
        return len(errors) == 0, errors

    @staticmethod
    def validate_rpm(rpm: float) -> Tuple[bool, List[str]]:
        """Проверить корректность оборотов."""
        errors = []
        if not (10 <= rpm <= 30000):
            errors.append("Обороты должны быть от 10 до 30000 об/мин")
        return len(errors) == 0, errors


# ============================================================================
# ПАРСЕР ВВОДА (ЧИСТЫЙ ПАРСИНГ БЕЗ БИЗНЕС-ЛОГИКИ)
# ============================================================================

class InputParser:
    """Парсер пользовательского ввода."""

    @staticmethod
    def parse_number(text: str) -> Optional[float]:
        """Извлечь число из текста."""
        numbers = re.findall(r'\d+(?:[.,]\d+)?', text)
        if numbers:
            try:
                return float(numbers[0].replace(',', '.'))
            except ValueError:
                pass
        return None

    @staticmethod
    def parse_choice(text: str, choices: List[str]) -> Optional[str]:
        """Найти совпадение текста с вариантами выбора."""
        text_lower = text.lower()
        for choice in choices:
            if choice.lower() in text_lower or text_lower in choice.lower():
                return choice
        return None


# ============================================================================
# ЧИСТАЯ ЛОГИКА ПЕРЕХОДОВ СОСТОЯНИЙ (FSM)
# ============================================================================

class StateMachine:
    """Конечный автомат для управления диалогом."""

    def __init__(self):
        self.validator = InputValidator()
        self.parser = InputParser()

    async def process_input(
            self,
            user_input: str,
            current_state: Any,
            user_data: Dict[str, Any]
    ) -> Tuple[Optional[Any], Dict[str, Any]]:
        """
        Обработать ввод пользователя и вернуть следующее состояние.

        Args:
            user_input: Текст ввода пользователя
            current_state: Текущее состояние FSM
            user_data: Данные пользователя

        Returns:
            Кортеж (следующее_состояние, обновленные_данные)
        """

        # Преобразуем состояние в строку
        current_state_str = str(current_state)
        if hasattr(current_state, 'state'):
            current_state_str = current_state.state

        logger.debug(f"FSM: {current_state_str} -> '{user_input}'")

        # Обработка команд сброса
        if user_input.lower() in ['/start', 'начать', 'сначала']:
            return UserState.waiting_material, {}

        # Маршрутизация по состояниям
        handler_map = {
            UserState.waiting_material.state: self._handle_material,
            UserState.waiting_operation.state: self._handle_operation,
            UserState.waiting_machine_type.state: self._handle_machine_type,
            UserState.waiting_turning_start_diameter.state: self._handle_start_diameter,
            UserState.waiting_turning_finish_diameter.state: self._handle_finish_diameter,
            UserState.waiting_mode.state: self._handle_mode,
            UserState.waiting_turning_tool_type.state: self._handle_tool_type,
            UserState.waiting_turning_tool_material.state: self._handle_tool_material,
            UserState.waiting_turning_tool_radius.state: self._handle_tool_radius,
            UserState.waiting_turning_tool_overhang.state: self._handle_tool_overhang,
            UserState.waiting_recommendation.state: self._handle_recommendation,
            UserState.waiting_user_choice.state: self._handle_user_choice,
        }

        handler = handler_map.get(current_state_str)
        if handler:
            return await handler(user_input, user_data)
        else:
            logger.warning(f"No handler for state: {current_state_str}")
            return None, user_data

    # ========== ОБРАБОТЧИКИ СОСТОЯНИЙ ==========

    async def _handle_material(self, user_input: str, user_data: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        """Обработка выбора материала."""
        if self.validator.validate_material(user_input):
            return UserState.waiting_operation, {**user_data, 'material': user_input}
        return UserState.waiting_material, user_data

    async def _handle_operation(self, user_input: str, user_data: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        """Обработка выбора операции."""
        if self.validator.validate_operation(user_input):
            return UserState.waiting_machine_type, {**user_data, 'operation': user_input}
        return UserState.waiting_operation, user_data

    async def _handle_machine_type(self, user_input: str, user_data: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        """Обработка выбора типа станка."""
        operation = user_data.get('operation', '')

        if self.validator.validate_machine_type(operation, user_input):
            updated_data = {**user_data, 'machine_type': user_input}

            # Маршрутизация дальше
            if operation == 'токарка':
                return UserState.waiting_turning_start_diameter, updated_data
            else:
                return UserState.waiting_mode, updated_data

        return UserState.waiting_machine_type, user_data

    async def _handle_start_diameter(self, user_input: str, user_data: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        """Обработка начального диаметра."""
        diameter = self.parser.parse_number(user_input)
        if diameter is not None:
            is_valid, errors = self.validator.validate_diameter(diameter)
            if is_valid:
                return UserState.waiting_turning_finish_diameter, {**user_data, 'start_diameter': diameter}
            else:
                user_data['validation_errors'] = errors

        return UserState.waiting_turning_start_diameter, user_data

    async def _handle_finish_diameter(self, user_input: str, user_data: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        """Обработка конечного диаметра."""
        diameter = self.parser.parse_number(user_input)
        if diameter is not None:
            start_diameter = user_data.get('start_diameter', 0)

            is_valid, errors = self.validator.validate_turning_diameters(start_diameter, diameter)
            if is_valid:
                # Рассчитываем базовую разницу для дальнейшей логики
                diff = abs(start_diameter - diameter)
                updated_data = {
                    **user_data,
                    'finish_diameter': diameter,
                    'diameter_difference': diff
                }
                return UserState.waiting_mode, updated_data
            else:
                user_data['validation_errors'] = errors

        return UserState.waiting_turning_finish_diameter, user_data

    async def _handle_mode(self, user_input: str, user_data: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        """Обработка выбора режима."""
        if self.validator.validate_mode(user_input):
            updated_data = {**user_data, 'mode': user_input}

            # Маршрутизация дальше
            operation = user_data.get('operation', '')
            if operation == 'токарка':
                return UserState.waiting_turning_tool_type, updated_data
            else:
                # Для нетокарных операций - переход к диаметру инструмента
                return UserState.waiting_tool_diameter, updated_data

        return UserState.waiting_mode, user_data

    async def _handle_tool_type(self, user_input: str, user_data: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        """Обработка выбора типа инструмента."""
        machine_type = user_data.get('machine_type', '')

        if self.validator.validate_tool_type(machine_type, user_input):
            return UserState.waiting_turning_tool_material, {**user_data, 'tool_type': user_input}

        return UserState.waiting_turning_tool_type, user_data

    async def _handle_tool_material(self, user_input: str, user_data: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        """Обработка выбора материала инструмента."""
        if self.validator.validate_tool_material(user_input):
            return UserState.waiting_turning_tool_radius, {**user_data, 'tool_material': user_input}

        return UserState.waiting_turning_tool_material, user_data

    async def _handle_tool_radius(self, user_input: str, user_data: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        """Обработка выбора радиуса инструмента."""
        radius = self.parser.parse_number(user_input)
        if radius is not None:
            machine_type = user_data.get('machine_type', '')

            is_valid, errors = self.validator.validate_tool_radius(machine_type, radius)
            if is_valid:
                return UserState.waiting_turning_tool_overhang, {**user_data, 'tool_radius': radius}
            else:
                user_data['validation_errors'] = errors

        return UserState.waiting_turning_tool_radius, user_data

    async def _handle_tool_overhang(self, user_input: str, user_data: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        """Обработка вылета инструмента."""
        overhang = self.parser.parse_number(user_input)
        if overhang is not None:
            is_valid, errors = self.validator.validate_tool_overhang(overhang)
            if is_valid:
                # ВОТ ЗДЕСЬ: возвращаем состояние для расчета
                return "CALCULATE_RECOMMENDATIONS", {**user_data, 'tool_overhang': overhang}
                # ИЛИ: return UserState.waiting_recommendation, {**user_data, 'tool_overhang': overhang}
            else:
                user_data['validation_errors'] = errors

        return UserState.waiting_turning_tool_overhang, user_data

    async def _handle_recommendation(self, user_input: str, user_data: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        """Запрос на расчёт рекомендаций."""
        # Это состояние активируется автоматически после ввода всех параметров
        # Возвращаем специальный флаг для запуска расчётов
        return "CALCULATE_RECOMMENDATIONS", user_data

    async def _handle_user_choice(self, user_input: str, user_data: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        """Обработка выбора пользователя (обороты)."""
        rpm = self.parser.parse_number(user_input)
        if rpm is not None:
            is_valid, errors = self.validator.validate_rpm(rpm)
            if is_valid:
                # Добавляем RPM пользователя для анализа
                updated_data = {**user_data, 'user_rpm': rpm}

                # Если есть рекомендованные RPM, считаем отклонение
                recommendation = user_data.get('recommendation', {})
                if 'rpm' in recommendation:
                    recommended_rpm = recommendation['rpm']
                    if recommended_rpm > 0:
                        deviation = abs(rpm - recommended_rpm) / recommended_rpm
                        updated_data['deviation'] = deviation

                return "COMPLETED", updated_data
            else:
                user_data['validation_errors'] = errors

        return UserState.waiting_user_choice, user_data


# ============================================================================
# ФАБРИКА ОТВЕТОВ (ЧИСТОЕ ФОРМИРОВАНИЕ ТЕКСТА)
# ============================================================================

class ResponseFactory:
    """Фабрика текстовых ответов для состояний."""

    @staticmethod
    def get_response_for_state(
            state: Any,
            user_data: Dict[str, Any],
            validation_errors: List[str] = None
    ) -> str:
        """
        Сгенерировать текстовый ответ для состояния.

        Args:
            state: Текущее состояние
            user_data: Данные пользователя
            validation_errors: Ошибки валидации

        Returns:
            Текст ответа
        """

        state_str = str(state)
        if hasattr(state, 'state'):
            state_str = state.state

        # Базовые ответы
        responses = {
            UserState.waiting_material.state:
                "Выберите материал заготовки:",

            UserState.waiting_operation.state:
                "Выберите операцию обработки:",

            UserState.waiting_machine_type.state:
                f"Операция: {user_data.get('operation', '')}\nВыберите тип станка:",

            UserState.waiting_turning_start_diameter.state:
                "Введите начальный диаметр заготовки в мм (1-800 мм):",

            UserState.waiting_turning_finish_diameter.state:
                ResponseFactory._get_finish_diameter_response(user_data),

            UserState.waiting_mode.state:
                ResponseFactory._get_mode_response(user_data),

            UserState.waiting_turning_tool_type.state:
                f"Тип станка: {user_data.get('machine_type', '')}\nВыберите тип токарного инструмента:",

            UserState.waiting_turning_tool_material.state:
                "Выберите материал режущей пластины:",

            UserState.waiting_turning_tool_radius.state:
                ResponseFactory._get_radius_response(user_data),

            UserState.waiting_turning_tool_overhang.state:
                "Введите вылет инструмента от державки в мм (10-500 мм):",

            UserState.waiting_recommendation.state:
                "🔄 Рассчитываю оптимальные параметры...",

            UserState.waiting_user_choice.state:
                ResponseFactory._get_recommendation_response(user_data),

            "CALCULATE_RECOMMENDATIONS":
                "✅ Все параметры собраны. Запускаю расчёт...",

            "COMPLETED":
                "✅ Расчёт завершён! Для нового расчёта: /start",

            "ERROR":
                "❌ Произошла ошибка. Начните заново: /start"
        }

        response = responses.get(state_str, "Продолжаем диалог...")

        # Добавляем ошибки валидации, если есть
        if validation_errors:
            error_text = "\n\n⚠️ " + "\n⚠️ ".join(validation_errors[:3])
            response += error_text

        return response

    @staticmethod
    def _get_finish_diameter_response(user_data: Dict[str, Any]) -> str:
        """Сгенерировать ответ для конечного диаметра."""
        start = user_data.get('start_diameter', 0)
        return f"Начальный диаметр: {start} мм\nВведите конечный диаметр (меньше {start} мм):"

    @staticmethod
    def _get_mode_response(user_data: Dict[str, Any]) -> str:
        """Сгенерировать ответ для выбора режима."""
        operation = user_data.get('operation', '')
        machine_type = user_data.get('machine_type', '')

        if operation == 'токарка':
            diff = user_data.get('diameter_difference', 0)
            if diff > 10:
                return (f"Токарка на {machine_type}\n"
                        f"Разница диаметров: {diff:.1f} мм (большая)\n"
                        f"Рекомендуется черновой режим\n\n"
                        f"Выберите режим обработки:")
            elif diff < 2:
                return (f"Токарка на {machine_type}\n"
                        f"Разница диаметров: {diff:.1f} мм (малая)\n"
                        f"Можно использовать чистовой режим\n\n"
                        f"Выберите режим обработки:")
            else:
                return (f"Токарка на {machine_type}\n"
                        f"Разница диаметров: {diff:.1f} мм\n"
                        f"Выберите режим обработки:")
        else:
            return f"{operation} на {machine_type}\nВыберите режим обработки:"

    @staticmethod
    def _get_radius_response(user_data: Dict[str, Any]) -> str:
        """Сгенерировать ответ для выбора радиуса."""
        machine_type = user_data.get('machine_type', '')
        tool_type = user_data.get('tool_type', '')

        if "чпу" in machine_type.lower():
            return (f"Тип станка: {machine_type}\n"
                    f"Тип инструмента: {tool_type}\n\n"
                    f"Для ЧПУ: радиус 0.4-1.0 мм\n"
                    f"Выберите радиус пластины:")
        else:
            return (f"Тип станка: {machine_type}\n"
                    f"Тип инструмента: {tool_type}\n\n"
                    f"Для обычной токарки: радиус 1.2-2.4 мм\n"
                    f"Выберите радиус пластины:")

    @staticmethod
    def _get_recommendation_response(user_data: Dict[str, Any]) -> str:
        """Сгенерировать ответ с рекомендациями."""
        recommendation = user_data.get('recommendation', {})

        if not recommendation.get('is_valid', False):
            return "❌ Не удалось рассчитать рекомендации"

        # Базовый формат рекомендаций
        response = "🎯 <b>РЕКОМЕНДУЕМЫЕ ПАРАМЕТРЫ:</b>\n\n"

        # Основные параметры
        params = [
            ('vc', 'Скорость резания', 'м/мин', '.0f'),
            ('rpm', 'Обороты шпинделя', 'об/мин', '.0f'),
            ('feed', 'Подача', 'мм/об', '.3f'),
            ('depth_of_cut', 'Глубина резания', 'мм', '.2f'),
        ]

        for key, label, unit, fmt in params:
            value = recommendation.get(key)
            if value is not None:
                response += f"• <b>{label}:</b> {value:{fmt}} {unit}\n"

        # Дополнительные параметры
        extra_params = [
            ('feed_rate', 'Скорость подачи', 'мм/мин'),
            ('removal_rate', 'Скорость съёма', 'см³/мин'),
            ('power', 'Мощность резания', 'кВт'),
        ]

        for key, label, unit in extra_params:
            value = recommendation.get(key)
            if value is not None:
                if key == 'removal_rate':
                    response += f"• <b>{label}:</b> {value:.2f} {unit}\n"
                elif key == 'power':
                    response += f"• <b>{label}:</b> {value:.1f} {unit}\n"
                else:
                    response += f"• <b>{label}:</b> {value:.0f} {unit}\n"

        response += "\n<i>Введите обороты, которые ВЫ используете на станке:</i>"
        return response


# ============================================================================
# ОСНОВНОЙ ИНТЕРФЕЙС ДЛЯ ВНЕШНЕГО ИСПОЛЬЗОВАНИЯ
# ============================================================================

class DialogManager:
    """Менеджер диалога - основной интерфейс для внешнего кода."""

    def __init__(self):
        self.state_machine = StateMachine()
        self.response_factory = ResponseFactory()

    async def process_message(
            self,
            message_text: str,
            current_state: Any,
            user_data: Dict[str, Any]
    ) -> Tuple[Any, str, Dict[str, Any]]:
        """
        Обработать сообщение пользователя.

        Args:
            message_text: Текст сообщения
            current_state: Текущее состояние
            user_data: Данные пользователя

        Returns:
            Кортеж (следующее_состояние, ответ, обновленные_данные)
        """
        # Очищаем старые ошибки
        user_data.pop('validation_errors', None)

        # Обрабатываем ввод через FSM
        next_state, updated_data = await self.state_machine.process_input(
            message_text,
            current_state,
            user_data
        )

        # Получаем ошибки валидации, если есть
        validation_errors = updated_data.pop('validation_errors', None)

        # Генерируем ответ
        response = self.response_factory.get_response_for_state(
            next_state,
            updated_data,
            validation_errors
        )

        return next_state, response, updated_data

    def get_initial_state(self) -> Any:
        """Получить начальное состояние."""
        return UserState.waiting_material


# ============================================================================
# ТЕСТИРОВАНИЕ ЧИСТОЙ ЛОГИКИ
# ============================================================================

if __name__ == "__main__":
    async def test_pure_state_machine():
        """Тестирование чистой логики FSM."""
        print("🧪 Тестирование чистой логики диалога")
        print("=" * 60)

        dialog_manager = DialogManager()

        # Тестовый сценарий
        test_steps = [
            ("сталь", "Выберите материал заготовки:"),
            ("токарка", "Выберите операцию обработки:"),
            ("чпу токарка", "Операция: токарка\nВыберите тип станка:"),
            ("100", "Введите начальный диаметр заготовки в мм (1-800 мм):"),
            ("90", "Начальный диаметр: 100.0 мм\nВведите конечный диаметр (меньше 100.0 мм):"),
            ("черновой", "Токарка на чпу токарка\nРазница диаметров: 10.0 мм\nВыберите режим обработки:"),
            ("проходной (80°)", "Тип станка: чпу токарка\nВыберите тип токарного инструмента:"),
            ("твердый сплав", "Выберите материал режущей пластины:"),
            ("0.8",
             "Тип станка: чпу токарка\nТип инструмента: проходной (80°)\n\nДля ЧПУ: радиус 0.4-1.0 мм\nВыберите радиус пластины:"),
            ("50", "Введите вылет инструмента от державки в мм (10-500 мм):"),
        ]

        state = dialog_manager.get_initial_state()
        user_data = {}

        for user_input, expected_response_start in test_steps:
            print(f"\n📝 Ввод: {user_input}")

            next_state, response, user_data = await dialog_manager.process_message(
                user_input, state, user_data
            )

            # Проверяем, что ответ начинается с ожидаемого текста
            if response.startswith(expected_response_start[:20]):
                print(f"✅ OK: {response[:50]}...")
            else:
                print(f"❌ FAIL: ожидалось '{expected_response_start[:50]}...'")
                print(f"     получено '{response[:50]}...'")

            state = next_state

        print("\n" + "=" * 60)
        print(f"✅ Тестирование завершено. Собрано {len(user_data)} параметров")


    import asyncio

    asyncio.run(test_pure_state_machine())
