"""
CLI версия для отладки и тестирования.
"""
import asyncio
from typing import Dict, Any

from app.core.state_machine import UserState, get_next_state
from app.services.recommendation import calculate_cutting_modes
from app.services.experience import calculate_deviation_score
from app.storage.memory import save_interaction


async def start_cli_bot():
    """Запуск бота в командной строке."""
    print("=" * 50)
    print("CNC Assistant CLI")
    print("Сбор данных для обучения ИИ")
    print("=" * 50)

    user_data = {}
    current_state = UserState.waiting_material

    print("\nВыбери материал:")
    print("сталь, алюминий, титан, нержавейка, чугун, латунь")

    while True:
        try:
            # Ввод пользователя
            user_input = input("\n> ").strip().lower()

            if user_input in ['exit', 'quit', 'выход']:
                print("Выход...")
                break

            # Обработка состояния
            next_state, updated_data = await get_next_state(
                current_state.value if current_state else None,
                user_input,
                user_data
            )

            user_data = updated_data

            if next_state:
                current_state = next_state

                # Логика для каждого состояния
                if current_state == UserState.waiting_operation:
                    print(f"\nМатериал: {user_data.get('material')}")
                    print("Выбери операцию:")
                    print("токарка, фрезерование, сверление, растачивание")

                elif current_state == UserState.waiting_mode:
                    print(f"\nМатериал: {user_data.get('material')}")
                    print(f"Операция: {user_data.get('operation')}")
                    print("Выбери режим обработки:")
                    print("черновой, получистовой, чистовой")

                elif current_state == UserState.waiting_diameter:
                    print(f"\nМатериал: {user_data.get('material')}")
                    print(f"Операция: {user_data.get('operation')}")
                    print(f"Режим: {user_data.get('mode')}")
                    print("\nВведи диаметр обработки в мм:")

                elif current_state == UserState.waiting_recommendation:
                    diameter = float(user_data.get('diameter', 0))

                    recommendations = calculate_cutting_modes(
                        material=user_data.get('material'),
                        operation=user_data.get('operation'),
                        mode=user_data.get('mode'),
                        diameter=diameter
                    )

                    user_data['recommendation'] = recommendations

                    print("\n" + "=" * 50)
                    print("РЕКОМЕНДАЦИИ:")
                    print(f"Материал: {user_data.get('material')}")
                    print(f"Операция: {user_data.get('operation')}")
                    print(f"Режим: {user_data.get('mode')}")
                    print(f"Диаметр: {diameter} мм")
                    print("-" * 30)
                    print(f"Скорость резания (Vc): {recommendations.get('vc')} м/мин")
                    print(f"Обороты (n): {recommendations.get('rpm')} об/мин")
                    print(f"Подача (f): {recommendations.get('feed')} мм/об")
                    print("=" * 50)
                    print("\nКакие обороты ВЫ ставите на станке?")

                elif current_state == UserState.waiting_user_choice:
                    try:
                        user_rpm = float(user_input)
                        recommended_rpm = user_data['recommendation']['rpm']

                        deviation = calculate_deviation_score(
                            user_rpm=user_rpm,
                            recommended_rpm=recommended_rpm
                        )

                        # Сохраняем в базу
                        interaction_data = {
                            'user_id': 'cli_user',
                            'material': user_data.get('material'),
                            'operation': user_data.get('operation'),
                            'mode': user_data.get('mode'),
                            'diameter': user_data.get('diameter'),
                            'recommended_rpm': recommended_rpm,
                            'recommended_vc': user_data['recommendation']['vc'],
                            'user_rpm': user_rpm,
                            'deviation_score': deviation,
                            'context': {'source': 'cli'}
                        }

                        save_interaction(interaction_data)

                        print(f"\n✓ Данные сохранены!")
                        print(f"Отклонение от рекомендации: {deviation:.1%}")
                        print("\nНачать заново? (да/нет)")

                        answer = input("> ").strip().lower()
                        if answer in ['да', 'yes', 'y']:
                            user_data = {}
                            current_state = UserState.waiting_material
                            print("\nВыбери материал:")
                            print("сталь, алюминий, титан, нержавейка, чугун, латунь")
                        else:
                            break

                    except ValueError:
                        print("Пожалуйста, введи число (обороты):")

            else:
                print("Не понимаю. Попробуй снова.")

        except KeyboardInterrupt:
            print("\n\nВыход...")
            break
        except Exception as e:
            print(f"Ошибка: {e}")
            print("Попробуй снова /start")
            user_data = {}
            current_state = UserState.waiting_material