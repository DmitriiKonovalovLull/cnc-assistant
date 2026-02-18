#!/usr/bin/env python3
"""
CLI интерфейс для CNC Assistant.
Работает по циклу: вопрос → парсинг ответа → обработка в FSM → следующий вопрос.
"""

import sys
import os
import re
from typing import Optional, Dict, Any, List, Union

# Добавляем корень проекта в путь для импортов
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from app.core.state_machine import StateMachine, SystemState
from app.bot.dialogs import DialogManager
from app.core.validator import Validator


class InputParser:
    """Утилиты для парсинга пользовательского ввода"""

    # Константы для числовых слов
    NUMBER_WORDS = {
        'половина': 0.5,
        'пол': 0.5,
        'четверть': 0.25,
        'треть': 0.333,
        'трети': 0.333,
    }

    # Словари для булевых значений
    POSITIVE_RESPONSES = {'да', 'yes', 'y', 'д', '+', 'true', '1', 'ок', 'ok', 'ага', 'угу'}
    NEGATIVE_RESPONSES = {'нет', 'no', 'n', 'н', '-', 'false', '0', 'not', 'неа', 'ноуп'}

    @staticmethod
    def parse_float(input_str: str) -> Optional[float]:
        """
        Парсит строку в число с плавающей точкой.
        Обрабатывает дроби, десятичные числа, целые числа.

        Args:
            input_str: Строка для парсинга

        Returns:
            Число float или None если не удалось распарсить
        """
        if not input_str:
            return None

        input_str = input_str.strip().replace(',', '.')

        # 1. Пробуем распарсить дробь вида "1/2", "3/4" и т.д.
        if '/' in input_str:
            try:
                parts = input_str.split('/')
                if len(parts) == 2:
                    numerator = float(parts[0].strip())
                    denominator = float(parts[1].strip())
                    if denominator != 0:
                        return numerator / denominator
            except (ValueError, ZeroDivisionError):
                pass

        # 2. Пробуем распарсить как обычное число
        try:
            # Убираем лишние символы (например, "мм", "м/мин" и т.д.)
            clean_str = re.sub(r'[^\d\.\-]', '', input_str)
            if clean_str:
                return float(clean_str)
        except ValueError:
            pass

        # 3. Пробуем распарсить числовые слова
        if input_str.lower() in InputParser.NUMBER_WORDS:
            return InputParser.NUMBER_WORDS[input_str.lower()]

        return None

    @staticmethod
    def parse_integer(input_str: str) -> Optional[int]:
        """
        Парсит строку в целое число.

        Args:
            input_str: Строка для парсинга

        Returns:
            Целое число или None если не удалось распарсить
        """
        float_value = InputParser.parse_float(input_str)
        if float_value is not None and float_value.is_integer():
            return int(float_value)
        return None

    @staticmethod
    def parse_choice(input_str: str, choices: List[str]) -> Optional[int]:
        """
        Парсит выбор из списка вариантов.

        Args:
            input_str: Ввод пользователя
            choices: Список доступных вариантов

        Returns:
            Индекс выбранного варианта (0-based) или None
        """
        if not input_str or not choices:
            return None

        input_str = input_str.strip()

        # 1. Если введен номер (1, 2, 3...)
        if input_str.isdigit():
            idx = int(input_str) - 1
            if 0 <= idx < len(choices):
                return idx

        # 2. Если введен текст - ищем совпадение
        input_lower = input_str.lower()
        for i, choice in enumerate(choices):
            if choice.lower().startswith(input_lower):
                return i

        return None

    @staticmethod
    def parse_boolean(input_str: str) -> Optional[bool]:
        """
        Парсит строку в булево значение.

        Args:
            input_str: Строка для парсинга

        Returns:
            True/False или None если не удалось распарсить
        """
        if not input_str:
            return None

        input_lower = input_str.strip().lower()

        if input_lower in InputParser.POSITIVE_RESPONSES:
            return True
        elif input_lower in InputParser.NEGATIVE_RESPONSES:
            return False

        return None


class CLIBot:
    """Основной класс CLI бота"""

    # Словарь соответствия типов вопросов методам парсинга
    PARSE_METHODS = {
        "choice": "parse_choice",
        "number": "parse_float",  # Для чисел с плавающей точкой
        "float": "parse_float",
        "integer": "parse_integer",
        "material": lambda x: x.upper(),
        "tool_material": lambda x: x,
        "yes_no": "parse_boolean",
        "boolean": "parse_boolean",
        "string": lambda x: x,
        "text": lambda x: x,
    }

    def __init__(self):
        self.state_machine = StateMachine()
        self.dialog_manager = DialogManager()
        self.validator = Validator()
        self.parser = InputParser()

        # Специальные команды
        self.special_commands = {
            'назад': ['/назад', 'back', 'b', 'назад'],
            'сброс': ['/сброс', 'reset', 'r', 'сброс'],
            'выход': ['/выход', 'exit', 'quit', 'q', 'выход'],
            'помощь': ['/помощь', 'help', 'h', 'помощь'],
            'статус': ['/статус', 'status', 's', 'статус'],
        }

        # Для удобства создаем обратный словарь
        self.command_map = {}
        for cmd_type, aliases in self.special_commands.items():
            for alias in aliases:
                self.command_map[alias.lower()] = cmd_type

    def _parse_user_input(self, user_input: str, question_type: str, choices: List[str] = None) -> Any:
        """
        Парсит ответ пользователя в зависимости от типа вопроса.

        Args:
            user_input: Строка ввода от пользователя
            question_type: Тип вопроса (определяет как парсить)
            choices: Список вариантов для вопросов типа choice

        Returns:
            Парсированное значение или словарь с командой
        """
        user_input = user_input.strip()
        if not user_input:
            return None

        user_input_lower = user_input.lower()

        # Проверка на специальные команды
        if user_input_lower in self.command_map:
            return {'command': self.command_map[user_input_lower]}

        # Получаем метод парсинга для данного типа вопроса
        parse_method = self.PARSE_METHODS.get(question_type)

        if parse_method is None:
            # По умолчанию возвращаем как строку
            return user_input

        # Вызываем соответствующий метод парсинга
        if parse_method == "parse_choice":
            return self.parser.parse_choice(user_input, choices)
        elif parse_method == "parse_float":
            return self.parser.parse_float(user_input)
        elif parse_method == "parse_integer":
            return self.parser.parse_integer(user_input)
        elif parse_method == "parse_boolean":
            return self.parser.parse_boolean(user_input)
        elif callable(parse_method):
            return parse_method(user_input)
        else:
            # Если метод указан как строка, но не найден
            return user_input

    def _display_choices(self, choices: List[str], show_numbers: bool = True):
        """
        Отображает варианты выбора.

        Args:
            choices: Список вариантов
            show_numbers: Показывать ли номера перед вариантами
        """
        if not choices:
            return

        print("\nВарианты:")
        for i, choice in enumerate(choices, 1 if show_numbers else 0):
            if show_numbers:
                print(f"  {i}. {choice}")
            else:
                print(f"  - {choice}")

        if show_numbers:
            print("  (или введите значение вручную)")

    def _display_help(self, context: Dict[str, Any] = None):
        """Показать справку по командам и текущий статус"""
        print("\n" + "=" * 50)
        print("СПРАВКА ПО КОМАНДАМ:")
        print("-" * 50)

        for cmd_type, aliases in self.special_commands.items():
            main_cmd = aliases[0]
            other_cmds = ", ".join(aliases[1:3])  # Показываем только 2-3 алиаса
            print(f"{main_cmd:15} - {self._get_command_description(cmd_type)}")
            if other_cmds:
                print(f"                 Алиасы: {other_cmds}")

        print("-" * 50)
        print("ФОРМАТЫ ВВОДА:")
        print("-" * 50)
        print("Числа: 100, 5, 0.5, 12.5")
        print("Дроби: 1/2, 3/4, 0.75")
        print("Слова: половина, четверть")
        print("Да/Нет: да, нет, y, n")

        # Показываем текущий статус, если есть контекст
        if context:
            print("-" * 50)
            print("ТЕКУЩИЙ ПРОГРЕСС:")
            if context.get('material'):
                print(f"Материал: {context['material']}")
            if context.get('tool_diameter'):
                print(f"Диаметр фрезы: {context['tool_diameter']}мм")
            if context.get('tool_type'):
                print(f"Тип фрезы: {context['tool_type']}")

        print("=" * 50 + "\n")

    def _get_command_description(self, cmd_type: str) -> str:
        """Получить описание команды"""
        descriptions = {
            'назад': 'Вернуться к предыдущему вопросу',
            'сброс': 'Начать заново',
            'помощь': 'Показать эту справку',
            'статус': 'Показать текущий прогресс',
            'выход': 'Завершить работу',
        }
        return descriptions.get(cmd_type, '')

    def _display_status(self):
        """Показать текущий статус сбора данных"""
        try:
            context = self.state_machine.get_context()
            progress = self.state_machine.get_progress()

            print("\n" + "=" * 50)
            print("ТЕКУЩИЙ СТАТУС:")
            print("-" * 50)
            print(f"Прогресс: {progress}")

            if context:
                filled_fields = []
                if context.get('material'):
                    filled_fields.append(f"Материал: {context['material']}")
                if context.get('tool_diameter'):
                    filled_fields.append(f"Фреза: {context['tool_diameter']}мм")
                if context.get('tool_type'):
                    filled_fields.append(f"Тип: {context['tool_type']}")
                if context.get('operation_type'):
                    filled_fields.append(f"Операция: {context['operation_type']}")

                if filled_fields:
                    print("Уже указано:")
                    for field in filled_fields:
                        print(f"  • {field}")
                else:
                    print("Данные еще не введены")

            print("=" * 50 + "\n")
        except Exception as e:
            print(f"Не удалось получить статус: {e}")

    def _show_examples_for_type(self, question_type: str):
        """Показать примеры ввода для определенного типа вопроса"""
        examples = {
            "number": "Пример: 0.5, 1/2, 10, 12.5",
            "float": "Пример: 0.5, 1/2, 10.5, 3.14",
            "integer": "Пример: 1, 5, 10, 100",
            "yes_no": "Пример: да/нет, y/n",
            "boolean": "Пример: да/нет, true/false",
            "material": "Пример: АЛЮМИНИЙ, СТАЛЬ45, Д16Т",
            "choice": "Введите номер или текст варианта",
        }

        if question_type in examples:
            print(f"Подсказка: {examples[question_type]}")

    def run(self):
        """Основной цикл работы CLI бота"""
        print("=" * 60)
        print("ДОБРО ПОЖАЛОВАТЬ В CNC ASSISTANT")
        print("=" * 60)
        print("Я помогу подобрать режимы резания для фрезерования.")
        print("Для справки введите /помощь\n")

        while True:
            try:
                # 1. Получаем текущий вопрос от FSM
                current_state = self.state_machine.get_current_state()

                if current_state == SystemState.CALCULATED:
                    # Все данные собраны, можно показывать результат
                    self._show_results()
                    if not self._ask_to_continue():
                        break
                    continue

                # 2. Получаем вопрос и его тип
                context = self.state_machine.get_context()
                question_data = self.dialog_manager.get_question(current_state, context)

                if not question_data:
                    print("Ошибка: не найден вопрос для состояния", current_state)
                    break

                question_text = question_data["question"]
                question_type = question_data.get("type", "text")
                choices = question_data.get("choices", [])
                help_text = question_data.get("help", "")

                # Проверяем, что тип вопроса поддерживается
                if question_type not in self.PARSE_METHODS:
                    print(f"Предупреждение: тип вопроса '{question_type}' не поддерживается, используем текстовый ввод")

                # 3. Показываем вопрос пользователю
                print("\n" + "=" * 50)
                print(f"Вопрос {self.state_machine.get_progress()}:")
                print("-" * 50)
                print(question_text)

                # Если есть подсказка - показываем её
                if help_text:
                    print(f"\n[ℹ] {help_text}")

                # Если есть варианты выбора - показываем их
                if choices:
                    self._display_choices(choices)

                # 4. Читаем ввод пользователя
                user_input = input("\nВаш ответ: ").strip()

                if not user_input:
                    print("Ввод не может быть пустым. Пожалуйста, введите значение.")
                    continue

                # 5. Парсим ввод
                parsed_input = self._parse_user_input(user_input, question_type, choices)

                # 6. Обрабатываем специальные команды
                if isinstance(parsed_input, dict) and 'command' in parsed_input:
                    self._handle_command(parsed_input['command'], context)
                    continue

                # 7. Валидируем ввод
                validation_result = self.validator.validate_input(
                    current_state, parsed_input, context
                )

                if not validation_result["valid"]:
                    print(f"Ошибка: {validation_result.get('message', 'Некорректный ввод')}")
                    if validation_result.get("suggestion"):
                        print(f"Подсказка: {validation_result['suggestion']}")

                    # Показываем примеры для данного типа ввода
                    self._show_examples_for_type(question_type)
                    continue

                # 8. Передаем валидные данные в FSM
                success = self.state_machine.process_input(
                    current_state,
                    validation_result["value"],
                    context
                )

                if not success:
                    print("Ошибка обработки ввода. Попробуйте еще раз.")

            except KeyboardInterrupt:
                print("\n\nПрервано пользователем.")
                if self._ask_to_exit():
                    break
            except Exception as e:
                print(f"\nПроизошла ошибка: {e}")
                import traceback
                traceback.print_exc()
                print("Попробуйте еще раз или введите /сброс для начала заново.")

    def _handle_command(self, command: str, context: Dict[str, Any]):
        """Обработка специальных команд"""
        if command == 'exit':
            print("\nДо свидания!")
            sys.exit(0)
        elif command == 'help':
            self._display_help(context)
        elif command == 'status':
            self._display_status()
        elif command == 'back':
            if self.state_machine.can_go_back():
                self.state_machine.go_back()
                print("Вернулись к предыдущему вопросу.")
            else:
                print("Нельзя вернуться назад (начало диалога).")
        elif command == 'reset':
            self.state_machine.reset()
            print("Начинаем заново.")
        else:
            print(f"Неизвестная команда: {command}")

    def _show_results(self):
        """Показать результаты расчета"""
        print("\n" + "=" * 60)
        print("РЕЗУЛЬТАТЫ РАСЧЕТА")
        print("=" * 60)

        try:
            params = self.state_machine.get_parameters()

            # Безопасный доступ к атрибутам
            print(f"\nМатериал: {getattr(params.material, 'name', 'не указан')} "
                  f"({getattr(params.material, 'code', 'N/A')})")
            print(f"Инструмент: {getattr(params.tool, 'diameter', 'не указан')}мм, "
                  f"{getattr(params.tool, 'type', 'не указан')}")
            print(f"Материал инструмента: {getattr(params.tool, 'material', 'не указан')}")

            print("\nРЕКОМЕНДУЕМЫЕ РЕЖИМЫ:")
            print("-" * 40)

            if hasattr(params.operation, 'mode') and params.operation.mode:
                mode = params.operation.mode
                print(f"Скорость резания (Vc): {getattr(mode, 'cutting_speed', 'N/A')} м/мин")
                print(f"Подача на зуб (fz): {getattr(mode, 'feed_per_tooth', 'N/A')} мм/зуб")
                print(f"Обороты (n): {getattr(mode, 'spindle_speed', 'N/A')} об/мин")
                print(f"Подача (vf): {getattr(mode, 'feed_rate', 'N/A')} мм/мин")

            if hasattr(params.operation, 'passes') and params.operation.passes:
                print(f"\nСТРАТЕГИЯ ПРОХОДОВ:")
                for i, pass_info in enumerate(params.operation.passes, 1):
                    pass_type = getattr(pass_info, 'type', 'проход')
                    depth = getattr(pass_info, 'depth', 'N/A')
                    print(f"{i}. {pass_type}: ap={depth}мм")

            print("\nДОПОЛНИТЕЛЬНО:")
            print(f"Опыт оператора: {getattr(params.operator, 'experience_level', 'не указан')}")
            print(f"Сложность: {getattr(params.operation, 'complexity', 'не указан')}")

            # Сравнение с пользовательскими значениями, если они были введены
            try:
                comparison = self.state_machine.get_comparison()
                if comparison:
                    print(f"\nСРАВНЕНИЕ:")
                    print(f"Совпадение: {getattr(comparison, 'match_percentage', 0):.1f}%")
                    if hasattr(comparison, 'differences') and comparison.differences:
                        print("Различия:")
                        for diff in comparison.differences:
                            print(f"  - {diff}")
            except:
                pass  # Игнорируем ошибки сравнения

        except AttributeError as e:
            print(f"Ошибка при выводе результатов: {e}")
            print("Пожалуйста, проверьте структуру данных.")

    def _ask_to_continue(self) -> bool:
        """Спросить, хочет ли пользователь начать новый расчет"""
        while True:
            response = input("\nХотите начать новый расчет? (да/нет): ").strip().lower()
            if self.parser.parse_boolean(response) is True:
                self.state_machine.reset()
                print("\n" + "=" * 50)
                print("НАЧИНАЕМ НОВЫЙ РАСЧЕТ")
                print("=" * 50)
                return True
            elif self.parser.parse_boolean(response) is False:
                return False
            else:
                print("Пожалуйста, ответьте 'да' или 'нет'")

    def _ask_to_exit(self) -> bool:
        """Спросить, хочет ли пользователь выйти"""
        while True:
            response = input("\nВы точно хотите выйти? (да/нет): ").strip().lower()
            parsed = self.parser.parse_boolean(response)
            if parsed is True:
                return True
            elif parsed is False:
                print("Продолжаем работу...")
                return False
            else:
                print("Пожалуйста, ответьте 'да' или 'нет'")


def main():
    """Точка входа в CLI приложение"""
    try:
        bot = CLIBot()
        bot.run()
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()