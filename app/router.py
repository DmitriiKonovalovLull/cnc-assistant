from dialog.flow import process_flow
from memory.session import get_session, update_session
from memory.history import save_history

def route_message(user_id: int, text: str) -> str:
    # Получаем текущую сессию
    session = get_session(user_id)

    # Обработка диалога
    # старое
    response = process_flow(user_id, text)

    # новое
    response = process_flow(user_id, text)

    # Сохраняем в историю
    save_history(user_id, session)

    return response
