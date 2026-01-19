def next_critical_question(session: dict) -> str:
    if not session.get("diameter"):
        return "Какой диаметр детали?"
    if not session.get("machine_type"):
        return "Ты работаешь на ЧПУ или универсальном станке?"
    return "Готово, все данные собраны."
