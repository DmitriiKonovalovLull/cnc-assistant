from typing import Optional, Dict, Any
import re
from memory.session import get_session, update_session
from logic.recommend import recommend_rpm

# === Константы состояний ===
STATE_IDLE = "IDLE"
STATE_ASK_NAME = "ASK_NAME"
STATE_WAIT_DIAMETER = "WAIT_DIAMETER"
STATE_WAIT_MACHINE = "WAIT_MACHINE"
STATE_WAIT_MAX_RPM = "WAIT_MAX_RPM"
STATE_READY = "READY"

# === Ключевые слова ===
GREETING_KEYWORDS = ["привет", "здравствуй", "добрый день", "hello", "hi", "хэй", "здорово"]
SHOW_OLD_KEYWORDS = ["покажи", "старые", "история", "что было", "сохраненные"]
CALC_KEYWORDS = ["режим", "rpm", "об/мин", "посчитай", "расчитай", "дай режимы", "рекомендация"]
RESET_KEYWORDS = ["сброс", "очистить", "заново", "новый", "reset"]
HELP_KEYWORDS = ["помощь", "help", "что ты умеешь", "команды"]

# === Материалы ===
MATERIAL_MAPPING = {
    "алюминий": ("aluminum", "Алюминий"),
    "сталь": ("steel", "Сталь"),
    "титан": ("titanium", "Титан"),
    "нержавейка": ("stainless_steel", "Нержавеющая сталь"),
    "чугун": ("cast_iron", "Чугун"),
    "латунь": ("brass", "Латунь"),
    "медь": ("copper", "Медь"),
}

# === Вспомогательные функции ===
def extract_diameter(text: str) -> Optional[float]:
    normalized = re.sub(r'[,;]', '.', text)
    pattern = r'[ØDd=:]*\s*(\d+(?:\.\d+)?)\s*(?:мм|mm)?'
    match = re.search(pattern, normalized)
    if match:
        try:
            diameter = float(match.group(1))
            if 0.1 <= diameter <= 1000:
                return diameter
        except ValueError:
            pass
    return None

def detect_material(text: str) -> Optional[tuple]:
    text_lower = text.lower()
    for keyword, (material_id, material_name) in MATERIAL_MAPPING.items():
        if keyword in text_lower or keyword[:3] in text_lower:
            return material_id, material_name
    return None

def create_welcome_message(username: str, session: Dict[str, Any]) -> str:
    material = session.get("material_name", "не указан")
    diameter = session.get("diameter")
    machine = session.get("machine_type")
    rpm_mode = session.get("rpm_mode")
    if diameter:
        machine_display = "ЧПУ" if machine == "cnc" else "универсальный"
        mode_display = "по Vc" if rpm_mode == "vc" else "фиксированные"
        return (f"С возвращением, {username}! 📊\n"
                f"Текущие параметры:\n"
                f"• Материал: {material}\n"
                f"• Диаметр: {diameter} мм\n"
                f"• Станок: {machine_display}\n"
                f"• Режим: {mode_display}\n\n"
                "Можешь изменить материал или диаметр, либо написать 'режим', чтобы получить рекомендации.")
    return f"Привет, {username}! 👋 Давай настроим параметры для расчёта режимов резания."

def create_parameters_summary(session: Dict[str, Any]) -> str:
    material_name = session.get("material_name", "не указан")
    diameter = session.get("diameter")
    machine = session.get("machine_type")
    rpm_mode = session.get("rpm_mode")
    max_rpm_turning = session.get("max_rpm_turning", "не указан")
    max_rpm_milling = session.get("max_rpm_milling", "не указан")
    if not diameter or not material_name:
        return "❌ Не все параметры заданы. Укажи материал и диаметр."
    machine_display = "ЧПУ" if machine == "cnc" else "универсальный"
    mode_display = "по Vc" if rpm_mode == "vc" else "фиксированные"
    rpm_recommendation = recommend_rpm(session.get("material"), machine, diameter)
    return (f"📋 Твои последние параметры:\n"
            f"• Материал: {material_name}\n"
            f"• Диаметр: {diameter} мм\n"
            f"• Станок: {machine_display}\n"
            f"• Режим расчёта: {mode_display}\n"
            f"• Макс. обороты токарного: {max_rpm_turning}\n"
            f"• Макс. обороты фрезерного: {max_rpm_milling}\n\n"
            f"💡 Рекомендация:\n{rpm_recommendation}\n"
            "Можешь изменить материал или диаметр для нового расчёта.")

# === Основной обработчик ===
def process_flow(user_id: int, text: str) -> str:
    session = get_session(user_id)
    state = session.get("state", STATE_IDLE)
    username = session.get("username")
    text_lower = text.lower().strip()

    # === Помощь ===
    if any(word in text_lower for word in HELP_KEYWORDS):
        return ("📋 Команды:\n"
                "• Привет - начать диалог\n"
                "• Материал - выбрать материал\n"
                "• Диаметр - указать размер детали\n"
                "• Покажи / история - показать параметры\n"
                "• Режим - получить рекомендации\n"
                "• Сброс - начать заново\n"
                "• Помощь - это сообщение")

    # === Сброс ===
    if any(word in text_lower for word in RESET_KEYWORDS):
        update_session(user_id, state=STATE_IDLE, clear=True)
        return "🔄 Сессия сброшена. Начнём заново! Как тебя зовут?"

    # === Приветствие ===
    if any(word in text_lower for word in GREETING_KEYWORDS):
        if not username:
            update_session(user_id, state=STATE_ASK_NAME)
            return "👋 Привет! Рад познакомиться! Как к тебе обращаться? 😊"
        return create_welcome_message(username, session)

    # === Ввод имени ===
    if state == STATE_ASK_NAME:
        name = text.strip()
        if len(name) < 2 or len(name) > 50:
            return "Пожалуйста, введи имя от 2 до 50 символов."
        update_session(user_id, username=name, state=STATE_IDLE)
        return f"Отлично, {name}! 👨‍🔧 Какой материал обрабатываем? (алюминий, сталь, титан...)"

    # === Показ старых параметров ===
    if any(kw in text_lower for kw in SHOW_OLD_KEYWORDS):
        return create_parameters_summary(session)

    # === IDLE — материал ===
    if state == STATE_IDLE:
        material_info = detect_material(text_lower)
        if material_info:
            material_id, material_name = material_info
            update_session(user_id, material=material_id, material_name=material_name, operation="turning",
                           state=STATE_WAIT_DIAMETER)
            return f"🛠 Отлично, {material_name}! Теперь скажи, какой диаметр заготовки в мм?"
        else:
            return "🤔 Не понял материал. Укажи: алюминий, сталь, титан, нержавейка, чугун, латунь или медь."

    # === WAIT_DIAMETER — диаметр ===
    if state == STATE_WAIT_DIAMETER:
        diameter = extract_diameter(text)
        if diameter:
            update_session(user_id, diameter=diameter, state=STATE_WAIT_MACHINE)
            return "📏 Диаметр принят! Какой станок используешь? ЧПУ (авто) или универсальный (ручной)?"
        return "📏 Не понял диаметр. Укажи число, например: 50, 50.5, Ø32"

    # === WAIT_MACHINE — станок ===
    if state == STATE_WAIT_MACHINE:
        if any(word in text_lower for word in ["универс", "ручн", "manual"]):
            update_session(user_id, machine_type="manual", rpm_mode="fixed", state=STATE_WAIT_MAX_RPM)
            return "✅ Универсальный станок выбран. Укажи максимальные обороты токарного шпинделя."
        if any(word in text_lower for word in ["чпу", "cnc", "автомат"]):
            update_session(user_id, machine_type="cnc", rpm_mode="vc", state=STATE_WAIT_MAX_RPM)
            return "✅ ЧПУ выбран. Укажи максимальные обороты фрезерного шпинделя."
        return "🏭 Укажи тип станка: ЧПУ или универсальный"

    # === WAIT_MAX_RPM — максимальные обороты ===
    if state == STATE_WAIT_MAX_RPM:
        try:
            rpm_value = int(re.search(r'\d+', text).group())
            machine = session.get("machine_type")
            if machine == "manual":
                update_session(user_id, max_rpm_turning=rpm_value, state=STATE_READY)
                return f"⚡ Макс. обороты токарного шпинделя установлены: {rpm_value} об/мин.\nТеперь напиши 'режим', и я дам рекомендации."
            else:
                update_session(user_id, max_rpm_milling=rpm_value, state=STATE_READY)
                return f"⚡ Макс. обороты фрезерного шпинделя установлены: {rpm_value} об/мин.\nТеперь напиши 'режим', и я дам рекомендации."
        except:
            return "⚠️ Не понял число. Укажи цифрами максимальные обороты шпинделя."

    # === READY — рекомендации / обновление ===
    if state == STATE_READY:
        if any(k in text_lower for k in CALC_KEYWORDS):
            if not session.get("material") or not session.get("diameter"):
                return "❌ Не хватает параметров. Укажи материал и диаметр заново."
            rpm_recommendation = recommend_rpm(session.get("material"), session.get("machine_type"),
                                               session.get("diameter"))
            return f"🎯 Вот твои рекомендации по резанию:\n{rpm_recommendation}\n💡 Можно изменить материал или диаметр для нового расчёта."
        material_info = detect_material(text_lower)
        if material_info:
            material_id, material_name = material_info
            update_session(user_id, material=material_id, material_name=material_name, state=STATE_WAIT_DIAMETER)
            return f"🔄 Изменён материал на '{material_name}'. Введи новый диаметр."
        diameter = extract_diameter(text_lower)
        if diameter:
            update_session(user_id, diameter=diameter, state=STATE_READY)
            return f"🔄 Диаметр изменён на {diameter} мм. Напиши 'режим' для получения рекомендаций."

    # === Ответ по умолчанию ===
    return "🤖 Не понял запрос. Напиши 'помощь' для списка команд."
