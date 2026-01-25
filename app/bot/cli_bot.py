"""
CLI версия для отладки и тестирования.
Интегрирована с новой системой recommendation.py v4.0.
"""

import asyncio
import re
from typing import Dict

# Импорты из нашего обновленного recommendation.py
from app.services.recommendation import (
    calculate_cutting_modes_turning_for_bot,
    calculate_cutting_modes_milling_for_bot,
    calculate_cutting_modes_drilling_for_bot
)
from app.services.data_collector import save_interaction_with_memory


async def start_cli_bot():
    """Запуск бота в командной строке."""
    print("=" * 60)
    print("CNC Assistant CLI v3.0")
    print("Сбор данных для обучения ИИ")
    print("Поддержка ЧПУ/обычная токарка, диаметры до 800 мм")
    print("=" * 60)

    user_data = {}
    current_state = "waiting_material"

    while True:
        try:
            # Показываем подсказку в зависимости от состояния
            prompt = get_state_prompt(current_state, user_data)
            if prompt:
                print(prompt)

            # Ввод пользователя
            user_input = input("\n> ").strip()

            if user_input.lower() in ['exit', 'quit', 'выход']:
                print("Выход...")
                break

            if user_input.lower() in ['reset', 'сброс', 'новая']:
                print("Начинаем новый расчет...")
                user_data = {}
                current_state = "waiting_material"
                continue

            # Обработка состояния
            next_state, updated_data = await get_next_state_cli(
                current_state,
                user_input,
                user_data
            )

            user_data = updated_data

            if next_state == "ERROR":
                print("❌ Произошла ошибка. Начните заново.")
                user_data = {}
                current_state = "waiting_material"
                continue
            elif next_state == "COMPLETED":
                # Завершение диалога с RPM
                await handle_user_choice_state(user_data)
                print("\n" + "=" * 50)
                print("Хотите начать новый расчет? (да/нет)")
                answer = input("> ").strip().lower()
                if answer in ['да', 'yes', 'y', 'д']:
                    print("\n" + "-" * 50)
                    print("Начинаем новый расчет!")
                    print("-" * 50)
                    user_data = {}
                    current_state = "waiting_material"
                else:
                    print("Спасибо за использование! До свидания.")
                    break
                continue
            elif next_state:
                current_state = next_state

                # Специальная логика для отображения рекомендаций
                if current_state == "waiting_recommendation":
                    await handle_recommendation_state(user_data)
                    current_state = "waiting_user_choice"
                    continue

            else:
                print("Не понимаю. Попробуйте снова или используйте команды:")
                print("'exit' - выход, 'reset' - начать заново")

        except KeyboardInterrupt:
            print("\n\nВыход...")
            break
        except ValueError as e:
            print(f"Ошибка ввода данных: {e}")
            print("Пожалуйста, введите корректное значение.")
        except Exception as e:
            print(f"Неожиданная ошибка: {e}")
            print("Попробуйте снова: 'reset'")
            user_data = {}
            current_state = "waiting_material"


def get_state_prompt(state: str, user_data: Dict) -> str:
    """Возвращает подсказку для текущего состояния."""
    prompts = {
        "waiting_material": (
            "\nВыберите материал:\n"
            "сталь, алюминий, титан, нержавейка, чугун"
        ),
        "waiting_operation": (
            f"\nМатериал: {user_data.get('material')}\n"
            "Выберите операцию:\n"
            "токарка, фрезерование, сверление, растачивание"
        ),
        "waiting_machine_type": (
            f"\nМатериал: {user_data.get('material')}\n"
            f"Операция: {user_data.get('operation')}\n"
            "Выберите тип станка:\n"
            "ЧПУ токарка, Обычная токарка, "
            "ЧПУ фрезер, Обычная фрезер, "
            "ЧПУ сверление, Обычное сверление"
        ),
        "waiting_mode": (
            f"\nМатериал: {user_data.get('material')}\n"
            f"Операция: {user_data.get('operation')}\n"
            f"Тип станка: {user_data.get('machine_type')}\n"
            "Выберите режим обработки:\n"
            "черновой, получистовой, чистовой"
        ),
        "waiting_tool_diameter": (
            f"\nМатериал: {user_data.get('material')}\n"
            f"Операция: {user_data.get('operation')}\n"
            f"Тип станка: {user_data.get('machine_type')}\n"
            f"Режим: {user_data.get('mode')}\n"
            "\nВведите диаметр инструмента в мм:"
        ),
        "waiting_turning_start_diameter": (
            f"\nМатериал: {user_data.get('material')}\n"
            f"Операция: {user_data.get('operation')}\n"
            f"Тип станка: {user_data.get('machine_type')}\n"
            "\nВведите начальный диаметр заготовки в мм (до 800 мм):"
        ),
        "waiting_turning_finish_diameter": (
            f"\nМатериал: {user_data.get('material')}\n"
            f"Операция: {user_data.get('operation')}\n"
            f"Тип станка: {user_data.get('machine_type')}\n"
            f"Начальный диаметр: {user_data.get('start_diameter')} мм\n"
            "\nВведите конечный диаметр детали в мм:"
        ),
        "waiting_turning_tool_type": (
            "\nВыберите тип токарного инструмента:\n"
            "проходной (95°), чистовой (95°), канавочный,\n"
            "резьбовой (60°), отрезной, расточной (90°)"
        ),
        "waiting_turning_tool_material": (
            "\nВыберите материал режущей пластины:\n"
            "твердый сплав, быстрорежущая сталь, керамика, кубический нитрид бора"
        ),
        "waiting_turning_tool_overhang": (
            "\nВведите вылет инструмента от державки в мм (10-500):"
        ),
        "waiting_user_choice": (
            "\nКакие обороты ВЫ ставите на станке? (введите число):"
        ),
    }
    return prompts.get(state, "")


async def get_next_state_cli(current_state: str, user_input: str, user_data: Dict) -> Tuple[str, Dict]:
    """Определяет следующее состояние для CLI версии."""

    # Обработка выбора материала
    if current_state == "waiting_material":
        if user_input in ["сталь", "алюминий", "титан", "нержавейка", "чугун"]:
            return "waiting_operation", {**user_data, 'material': user_input}
        else:
            return "waiting_material", user_data

    # Обработка выбора операции
    elif current_state == "waiting_operation":
        if user_input in ["токарка", "фрезерование", "сверление", "растачивание"]:
            return "waiting_machine_type", {**user_data, 'operation': user_input}
        else:
            return "waiting_operation", user_data

    # Обработка выбора типа станка
    elif current_state == "waiting_machine_type":
        operation = user_data.get('operation', '')

        valid_machine_types = []
        if "токар" in operation.lower():
            valid_machine_types = ["чпу токарка", "обычная токарка"]
        elif "фрезер" in operation.lower():
            valid_machine_types = ["чпу фрезер", "обычная фрезер"]
        else:
            valid_machine_types = ["чпу сверление", "обычное сверление"]

        if user_input.lower() in [x.lower() for x in valid_machine_types]:
            if user_input.lower() == "токарка":
                return "waiting_turning_start_diameter", {**user_data, 'machine_type': user_input}
            else:
                return "waiting_mode", {**user_data, 'machine_type': user_input}
        else:
            return "waiting_machine_type", user_data

    # Обработка выбора режима
    elif current_state == "waiting_mode":
        if user_input in ["черновой", "получистовой", "чистовой"]:
            updated_data = {**user_data, 'mode': user_input}

            if user_data.get('operation') in ["фрезерование", "сверление", "растачивание"]:
                return "waiting_tool_diameter", updated_data
            else:
                return "waiting_turning_start_diameter", updated_data
        else:
            return "waiting_mode", user_data

    # Обработка ввода диаметра инструмента
    elif current_state == "waiting_tool_diameter":
        try:
            numbers = re.findall(r'\d+(?:\.\d+)?', user_input)
            if numbers:
                diameter = float(numbers[0].replace(',', '.'))
                operation = user_data.get('operation', '')

                if operation == "фрезерование" and 0.1 <= diameter <= 300:
                    return "waiting_recommendation", {**user_data, 'tool_diameter': diameter}
                elif operation in ["сверление", "растачивание"] and 0.1 <= diameter <= 100:
                    return "waiting_recommendation", {**user_data, 'tool_diameter': diameter}
                else:
                    return "waiting_tool_diameter", user_data
            else:
                return "waiting_tool_diameter", user_data
        except (ValueError, IndexError):
            return "waiting_tool_diameter", user_data

    # ========== ТОКАРНЫЕ ПАРАМЕТРЫ ==========

    # Начальный диаметр для токарки
    elif current_state == "waiting_turning_start_diameter":
        try:
            numbers = re.findall(r'\d+(?:\.\d+)?', user_input)
            if numbers:
                diameter = float(numbers[0].replace(',', '.'))
                if 1 <= diameter <= 800:
                    return "waiting_turning_finish_diameter", {**user_data, 'start_diameter': diameter}
                else:
                    return "waiting_turning_start_diameter", user_data
            else:
                return "waiting_turning_start_diameter", user_data
        except (ValueError, IndexError):
            return "waiting_turning_start_diameter", user_data

    # Конечный диаметр для токарки
    elif current_state == "waiting_turning_finish_diameter":
        try:
            numbers = re.findall(r'\d+(?:\.\d+)?', user_input)
            if numbers:
                diameter = float(numbers[0].replace(',', '.'))
                start_diameter = user_data.get('start_diameter', 0)
                if 0.1 <= diameter < start_diameter:
                    return "waiting_turning_tool_type", {**user_data, 'finish_diameter': diameter}
                else:
                    return "waiting_turning_finish_diameter", user_data
            else:
                return "waiting_turning_finish_diameter", user_data
        except (ValueError, IndexError):
            return "waiting_turning_finish_diameter", user_data

    # Тип токарного инструмента
    elif current_state == "waiting_turning_tool_type":
        if user_input in ["проходной (95°)", "чистовой (95°)", "канавочный",
                          "резьбовой (60°)", "отрезной", "расточной (90°)"]:
            return "waiting_turning_tool_material", {**user_data, 'tool_type': user_input}
        else:
            return "waiting_turning_tool_type", user_data

    # Материал токарного инструмента
    elif current_state == "waiting_turning_tool_material":
        if user_input in ["твердый сплав", "быстрорежущая сталь", "керамика",
                          "кубический нитрид бора"]:
            updated_data = {**user_data, 'tool_material': user_input}
            return "waiting_turning_tool_overhang", updated_data
        else:
            return "waiting_turning_tool_material", user_data

    # Вылет токарного инструмента
    elif current_state == "waiting_turning_tool_overhang":
        try:
            numbers = re.findall(r'\d+(?:\.\d+)?', user_input)
            if numbers:
                overhang = float(numbers[0].replace(',', '.'))
                if 10 <= overhang <= 500:
                    updated_data = {**user_data, 'tool_overhang': overhang}
                    return "waiting_mode", updated_data
                else:
                    return "waiting_turning_tool_overhang", user_data
            else:
                return "waiting_turning_tool_overhang", user_data
        except (ValueError, IndexError):
            return "waiting_turning_tool_overhang", user_data

    # Расчет рекомендаций
    elif current_state == "waiting_recommendation":
        try:
            operation = user_data.get('operation')
            machine_type = user_data.get('machine_type', '')

            # Маппинг machine_type
            if "чпу" in machine_type.lower():
                if "токар" in machine_type.lower():
                    machine_type_key = "чпу_токарка"
                elif "фрезер" in machine_type.lower():
                    machine_type_key = "чпу_фрезер"
                else:
                    machine_type_key = "чпу_сверление"
            else:
                if "токар" in machine_type.lower():
                    machine_type_key = "обычная_токарка"
                elif "фрезер" in machine_type.lower():
                    machine_type_key = "обычная_фрезер"
                else:
                    machine_type_key = "обычное_сверление"

            if operation == 'токарка':
                recommendations = calculate_cutting_modes_turning_for_bot(
                    material=user_data.get('material'),
                    machine_type=machine_type_key,
                    mode=user_data.get('mode'),
                    start_diameter=user_data.get('start_diameter', 0),
                    finish_diameter=user_data.get('finish_diameter', 0),
                    tool_type=user_data.get('tool_type', 'проходной (95°)'),
                    tool_material=user_data.get('tool_material', 'твердый сплав'),
                    tool_overhang=user_data.get('tool_overhang', 50.0)
                )
            elif operation == 'фрезерование':
                recommendations = calculate_cutting_modes_milling_for_bot(
                    material=user_data.get('material'),
                    machine_type=machine_type_key,
                    mode=user_data.get('mode'),
                    tool_diameter=user_data.get('tool_diameter', 0)
                )
            elif operation in ['сверление', 'растачивание']:
                recommendations = calculate_cutting_modes_drilling_for_bot(
                    material=user_data.get('material'),
                    machine_type=machine_type_key,
                    mode=user_data.get('mode'),
                    tool_diameter=user_data.get('tool_diameter', 0)
                )
            else:
                recommendations = {}

            if not recommendations or not recommendations.get('is_valid', False):
                print(f"Не удалось рассчитать рекомендации для {operation}")
                return "ERROR", user_data

            return "waiting_user_choice", {**user_data, 'recommendation': recommendations}

        except Exception as e:
            print(f"Ошибка расчета рекомендаций: {e}")
            return "ERROR", user_data

    # Обработка ввода оборотов пользователем
    elif current_state == "waiting_user_choice":
        numbers = re.findall(r'\d+(?:\.\d+)?', user_input)
        if numbers:
            try:
                user_rpm = float(numbers[0].replace(',', '.'))
                if 10 <= user_rpm <= 30000:
                    updated_data = {**user_data, 'user_rpm': user_rpm}

                    # Рассчитываем отклонение
                    recommended_rpm = user_data.get('recommendation', {}).get('rpm', 0)
                    if recommended_rpm > 0:
                        deviation = abs(user_rpm - recommended_rpm) / recommended_rpm
                        updated_data['deviation'] = deviation

                    return "COMPLETED", updated_data
            except (ValueError, IndexError):
                pass
        return "waiting_user_choice", user_data

    else:
        return None, user_data


async def handle_recommendation_state(user_data: Dict):
    """Обработка состояния рекомендаций."""
    try:
        operation = user_data.get('operation')
        recommendations = user_data.get('recommendation', {})

        if not recommendations:
            print("Не удалось получить рекомендации")
            return

        print("\n" + "=" * 60)
        print("РЕКОМЕНДАЦИИ:")
        print("=" * 60)

        if operation == 'токарка':
            print(f"Материал: {user_data.get('material')}")
            print(f"Тип станка: {user_data.get('machine_type')}")
            print(f"Режим: {user_data.get('mode')}")
            print(f"Диаметры: {user_data.get('start_diameter')} → {user_data.get('finish_diameter')} мм")
            print(f"Тип инструмента: {user_data.get('tool_type')}")
            print(f"Материал пластины: {user_data.get('tool_material')}")
            print(f"Вылет: {user_data.get('tool_overhang')} мм")
            print("-" * 40)
            print(f"Средний диаметр: {recommendations.get('avg_diameter', 0)} мм")
            print(f"Глубина резания: {recommendations.get('depth_of_cut', 0)} мм")
            print(f"Скорость резания (Vc): {recommendations.get('vc', 0)} м/мин")
            print(f"Обороты (n): {recommendations.get('rpm', 0)} об/мин")
            print(f"Подача (f): {recommendations.get('feed', 0)} мм/об")
            print(f"Скорость подачи: {recommendations.get('feed_rate', 0)} мм/мин")
            if recommendations.get('power'):
                print(f"Мощность: {recommendations.get('power')} кВт")
            print(f"Скорость съема: {recommendations.get('removal_rate', 0)} см³/мин")

        elif operation == 'фрезерование':
            print(f"Материал: {user_data.get('material')}")
            print(f"Тип станка: {user_data.get('machine_type')}")
            print(f"Режим: {user_data.get('mode')}")
            print(f"Диаметр фрезы: {user_data.get('tool_diameter')} мм")
            print("-" * 40)
            print(f"Скорость резания (Vc): {recommendations.get('vc', 0)} м/мин")
            print(f"Обороты (n): {recommendations.get('rpm', 0)} об/мин")
            print(f"Подача на зуб (fz): {recommendations.get('feed_per_tooth', 0)} мм/зуб")
            print(f"Подача (F): {recommendations.get('feed', 0)} мм/мин")
            print(f"Глубина резания (ap): {recommendations.get('ap', 0)} мм")
            print(f"Количество зубьев: {recommendations.get('teeth_count', 4)}")
            print(f"Скорость съема: {recommendations.get('removal_rate', 0)} см³/мин")

        elif operation in ['сверление', 'растачивание']:
            print(f"Материал: {user_data.get('material')}")
            print(f"Тип станка: {user_data.get('machine_type')}")
            print(f"Режим: {user_data.get('mode')}")
            print(f"Диаметр инструмента: {user_data.get('tool_diameter')} мм")
            print("-" * 40)
            print(f"Скорость резания (Vc): {recommendations.get('vc', 0)} м/мин")
            print(f"Обороты (n): {recommendations.get('rpm', 0)} об/мин")
            print(f"Подача (f): {recommendations.get('feed', 0)} мм/об")
            print(f"Скорость подачи: {recommendations.get('feed_rate', 0)} мм/мин")

        warnings = recommendations.get('warnings', [])
        if warnings:
            print("\n⚠️  ВНИМАНИЕ:")
            for warning in warnings[:3]:
                print(f"  • {warning}")

        print("=" * 60)

    except Exception as e:
        print(f"Ошибка при отображении рекомендаций: {e}")


def calculate_deviation_score(user_rpm: float, recommended_rpm: float) -> float:
    """Рассчитывает отклонение пользовательского выбора от рекомендации."""
    if recommended_rpm == 0:
        return 0
    return abs(user_rpm - recommended_rpm) / recommended_rpm


async def handle_user_choice_state(user_data: Dict):
    """Обработка выбора пользователя и сохранение результатов."""
    try:
        user_rpm = user_data.get('user_rpm')
        if not user_rpm:
            print("Ошибка: не найдены обороты пользователя")
            return

        recommendations = user_data.get('recommendation', {})
        recommended_rpm = recommendations.get('rpm', 0)

        if recommended_rpm == 0:
            print("Ошибка: не найдены рекомендуемые обороты")
            return

        deviation = calculate_deviation_score(user_rpm, recommended_rpm)

        # Сохраняем в базу
        interaction_data = {
            'user_id': 'cli_user',
            'material': user_data.get('material'),
            'operation': user_data.get('operation'),
            'machine_type': user_data.get('machine_type'),
            'mode': user_data.get('mode'),
            'recommended_rpm': float(recommended_rpm),
            'recommended_vc': float(recommendations.get('vc', 0)),
            'user_rpm': float(user_rpm),
            'deviation_score': deviation,
            'context': {
                'source': 'cli',
                'bot_version': '3.0',
                'timestamp': asyncio.get_event_loop().time()
            }
        }

        # Добавляем специфичные параметры
        if user_data.get('operation') == 'токарка':
            interaction_data.update({
                'start_diameter': float(user_data.get('start_diameter', 0)),
                'finish_diameter': float(user_data.get('finish_diameter', 0)),
                'tool_type': user_data.get('tool_type', ''),
                'tool_material': user_data.get('tool_material', ''),
                'tool_overhang': float(user_data.get('tool_overhang', 0)),
                'feed': float(recommendations.get('feed', 0))
            })
        elif user_data.get('operation') in ['фрезерование', 'сверление', 'растачивание']:
            interaction_data.update({
                'tool_diameter': float(user_data.get('tool_diameter', 0)),
                'feed': float(recommendations.get('feed', 0))
            })

        success = save_interaction_with_memory(interaction_data)

        if success:
            deviation_percent = deviation * 100
            if deviation_percent < 10:
                reaction = "✅ Отличное совпадение!"
            elif deviation_percent < 25:
                reaction = "⚠️  Небольшое отклонение"
            else:
                reaction = "🔄 Значительное отклонение"

            print(f"\n{reaction}")
            print(f"🎯 Рекомендация ИИ: {int(recommended_rpm)} об/мин")
            print(f"👨‍🔧 Ваш выбор: {int(user_rpm)} об/мин")
            print(f"📊 Отклонение: {deviation_percent:.1f}%")
            print("✓ Данные сохранены для обучения ИИ!")
        else:
            print("⚠️  Не удалось сохранить данные в базу")

    except ValueError:
        print("Ошибка: некорректные данные")
    except KeyError as e:
        print(f"Ошибка: отсутствует параметр {e}")
    except Exception as e:
        print(f"Ошибка при сохранении данных: {e}")


if __name__ == "__main__":
    asyncio.run(start_cli_bot())