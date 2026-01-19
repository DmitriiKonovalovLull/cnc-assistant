from core.intent_detector import detect_intent
from core.extractor import extract_material, extract_diameter, speed_table
from memory.user_profile import get_or_create_user, save_history

def handle(user_input: str, context: dict, step: str, user_id: int):
    # сохраняем историю пользователя
    save_history(user_id, user_input)
    user = get_or_create_user(user_id)

    intent = detect_intent(user_input)
    response = ""

    # --- FSM шаги ---
    if step == "INIT":
        if intent == "start":
            response = (
                "Привет! Я CNC-ассистент.\n"
                "Я запоминаю материалы и диаметр заготовки.\n"
                "Начнем с материала. Напиши, какой материал будешь резать."
            )
            step = "ASK_MATERIAL"
        else:
            response = "Сначала напиши /start или старт, чтобы я запустился."
            step = "INIT"

    elif step == "ASK_MATERIAL":
        material = extract_material(user_input)
        if material:
            context["material"] = material
            response = f"Запомнил материал: {material}. Теперь напиши диаметр заготовки (мм)."
            step = "ASK_DIAMETER"
        else:
            response = "Не понял материал. Напиши: алюминий, сталь или титан."
            step = "ASK_MATERIAL"

    elif step == "ASK_DIAMETER":
        diameter = extract_diameter(user_input)
        if diameter:
            context["diameter"] = diameter
            response = f"Принят диаметр: {diameter} мм. Рассчитываю RPM..."
            step = "CALCULATE"
        else:
            response = "Не понял диаметр. Введи число, например: 50 или 50.5."
            step = "ASK_DIAMETER"

    elif step == "CALCULATE":
        material = context.get("material")
        diameter = context.get("diameter")
        if material and diameter:
            vc = speed_table[material]      # скорость резания м/мин
            rpm = (vc * 1000) / (3.1416 * diameter)
            response = f"Для {material} с диаметром {diameter} мм рекомендую RPM ≈ {round(rpm)}"
        else:
            response = "Ошибка: нет данных для расчёта. Начнём с начала."
            step = "INIT"

    else:
        response = "Не понимаю этот шаг. Возвращаюсь к началу."
        step = "INIT"

    return response, context, step
