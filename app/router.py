from dialog.flow import process_flow

def route_message(user_id: int, text: str) -> str:
    """
    Основной маршрутизатор сообщений пользователя.
    Вызывает диалоговый процесс и возвращает ответ.
    История сохраняется внутри process_flow при необходимости.
    """
    # Обрабатываем текст через FSM / диалоговый процесс
    response = process_flow(user_id, text)

    # НЕ вызываем save_history здесь напрямую,
    # чтобы не ломать сигнатуру и не дублировать данные.
    # Все записи истории делаются внутри process_flow, когда есть
    # recommended_params и user_choice

    return response
