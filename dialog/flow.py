from typing import Optional, Dict, Any
import re
from memory.session import get_session, update_session
from memory.history import save_history
from logic.recommend import recommend_rpm
from logic.evaluate import evaluate_rpm_decision
from dialog.validators import rpm_is_reasonable
from memory.profiles import update_profile

# === Состояния ===
STATE_IDLE = "IDLE"
STATE_ASK_NAME = "ASK_NAME"
STATE_WAIT_MATERIAL = "WAIT_MATERIAL"
STATE_WAIT_OPERATION = "WAIT_OPERATION"
STATE_WAIT_CUT_TYPE = "WAIT_CUT_TYPE"  # Новое состояние для типа обработки
STATE_WAIT_DIAMETER = "WAIT_DIAMETER"
STATE_WAIT_MACHINE = "WAIT_MACHINE"
STATE_WAIT_MAX_RPM = "WAIT_MAX_RPM"
STATE_READY = "READY"

# === Ключевые слова ===
GREETING_KEYWORDS = ["привет", "здравствуй", "добрый день", "hello", "hi", "хэй", "здорово"]
SHOW_OLD_KEYWORDS = ["покажи", "старые", "история", "что было", "сохраненные", "помнишь", "режимы"]
CALC_KEYWORDS = ["режим", "rpm", "об/мин", "посчитай", "расчитай", "дай режимы", "рекомендация"]
RESET_KEYWORDS = ["сброс", "очистить", "заново", "новый", "reset"]
HELP_KEYWORDS = ["помощь", "help", "что ты умеешь", "команды"]
ROUGH_CUT_KEYWORDS = ["чернов", "груб", "rough", "предвар"]
FINE_CUT_KEYWORDS = ["чистов", "тонк", "finish", "окончат"]

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

def detect_operation(text: str) -> Optional[str]:
    ops = {"токарная": "turning", "фрезерная": "milling", "сверление": "drilling"}
    for k, v in ops.items():
        if k in text.lower():
            return v
    return None

def detect_cut_type(text: str) -> Optional[str]:
    text_lower = text.lower()
    if any(word in text_lower for word in ROUGH_CUT_KEYWORDS):
        return "rough"
    if any(word in text_lower for word in FINE_CUT_KEYWORDS):
        return "clean"
    return None

def create_welcome_message(username: str, session: Dict[str, Any]) -> str:
    material = session.get("material_name", "не указан")
    operation = session.get("operation", "не указана")
    cut_type = session.get("cut_type", "не указан")
    diameter = session.get("diameter")
    machine = session.get("machine_type")

    if diameter:
        machine_display = "ЧПУ" if machine == "cnc" else "универсальный"
        cut_type_display = "черновая" if cut_type == "rough" else "чистовая" if cut_type == "clean" else "не указана"
        return (f"С возвращением, {username}! 📊\n"
                f"Текущие параметры:\n"
                f"• Материал: {material}\n"
                f"• Операция: {operation}\n"
                f"• Тип обработки: {cut_type_display}\n"
                f"• Диаметр: {diameter} мм\n"
                f"• Станок: {machine_display}\n\n"
                "Можешь изменить любой параметр или написать 'режим' для рекомендаций.")
    return f"Привет, {username}! 👋 Давай настроим параметры для расчёта режимов резания."

def create_parameters_summary(session: Dict[str, Any]) -> str:
    """Показывает полную сводку параметров"""
    material_name = session.get("material_name", "не указан")
    operation = session.get("operation", "не указана")
    cut_type = session.get("cut_type", "не указан")
    diameter = session.get("diameter", "не указан")
    machine = session.get("machine_type", "не указан")
    max_rpm = session.get("max_rpm_milling") or session.get("max_rpm_turning", "не указаны")
    rpm_data = session.get("recommended_params", {})

    cut_type_display = "черновая" if cut_type == "rough" else "чистовая" if cut_type == "clean" else "не указана"
    machine_display = "ЧПУ" if machine == "cnc" else "универсальный" if machine == "manual" else "не указан"

    msg = (f"📋 Твои параметры:\n"
           f"• Материал: {material_name}\n"
           f"• Операция: {operation}\n"
           f"• Тип обработки: {cut_type_display}\n"
           f"• Диаметр: {diameter} мм\n"
           f"• Станок: {machine_display}\n"
           f"• Макс. обороты: {max_rpm} об/мин\n"
           f"• Рекомендованные RPM: {rpm_data.get('rpm', 'не указано')}\n"
           f"• Скорость резания Vc: {rpm_data.get('vc', 'не указано')}\n")
    if rpm_data.get('feed_per_tooth'):
        msg += f"• Подача на зуб: {rpm_data['feed_per_tooth']} мм/зуб\n"
    if rpm_data.get('depth_of_cut'):
        msg += f"• Глубина реза: {rpm_data['depth_of_cut']} мм\n"
    if rpm_data.get('tool_type'):
        msg += f"• Инструмент: {rpm_data['tool_type']}\n"
    if rpm_data.get('notes'):
        msg += f"• Замечания: {rpm_data['notes']}\n"
    msg += "\n✏️ Напиши 'режим' для обновления рекомендаций."
    return msg

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
                "• Операция - токарная, фрезерная, сверление\n"
                "• Тип обработки - черновая или чистовая\n"
                "• Диаметр - указать размер\n"
                "• Станок - ЧПУ или универсальный\n"
                "• Режим - получить рекомендации\n"
                "• Покажи - показать параметры\n"
                "• Сброс - начать заново\n"
                "• Помощь - это сообщение")

    # === Сброс ===
    if any(word in text_lower for word in RESET_KEYWORDS):
        update_session(user_id, state=STATE_IDLE, clear=True)
        return "🔄 Сессия сброшена. Начнём заново! Как тебя зовут?"

    # === Вспоминание прошлых режимов ===
    if session.get("recommended_params"):
        if any(k in text_lower for k in SHOW_OLD_KEYWORDS):
            return create_parameters_summary(session)

    # === Приветствие ===
    if any(word in text_lower for word in GREETING_KEYWORDS):
        if not username:
            update_session(user_id, state=STATE_ASK_NAME)
            return "👋 Привет! Рад познакомиться! Как к тебе обращаться? 😊"
        return create_welcome_message(username, session)

    # === Ввод имени ===
    if state == STATE_ASK_NAME:
        name = text.strip()
        update_session(user_id, username=name, state=STATE_WAIT_MATERIAL)
        return f"Отлично, {name}! 👨‍🔧 Какой материал обрабатываем? (алюминий, сталь, титан...)"

    # === Выбор материала ===
    if state in [STATE_WAIT_MATERIAL, STATE_IDLE]:
        material_info = detect_material(text_lower)
        if material_info:
            material_id, material_name = material_info
            update_session(user_id, material=material_id, material_name=material_name, state=STATE_WAIT_OPERATION)
            return f"🛠 Отлично, {material_name}! Какую операцию будем выполнять? (токарная, фрезерная, сверление)"
        if state == STATE_WAIT_MATERIAL:
            return "🤔 Не понял материал. Укажи: алюминий, сталь, титан, нержавейка, чугун, латунь или медь."

    # === Выбор операции ===
    if state == STATE_WAIT_OPERATION:
        operation = detect_operation(text_lower)
        if operation:
            update_session(user_id, operation=operation, state=STATE_WAIT_CUT_TYPE)
            return f"🔹 Операция: {operation}. Какой тип обработки? (черновая или чистовая)"
        return "🤔 Укажи операцию: токарная, фрезерная или сверление."

    # === Выбор типа обработки ===
    if state == STATE_WAIT_CUT_TYPE:
        cut_type = detect_cut_type(text_lower)
        if cut_type:
            cut_type_display = "черновая" if cut_type == "rough" else "чистовая"
            update_session(user_id, cut_type=cut_type, state=STATE_WAIT_DIAMETER)
            return f"🔧 Тип обработки: {cut_type_display}. Укажи диаметр заготовки (мм)."

        diameter = extract_diameter(text_lower)
        if diameter:
            update_session(user_id, cut_type="rough", diameter=diameter, state=STATE_WAIT_MACHINE)
            return f"📏 Диаметр принят: {diameter} мм (тип обработки установлен 'черновая'). Какой станок используешь? ЧПУ или универсальный?"

        return "🔧 Укажи тип обработки: черновая или чистовая. Или введи диаметр для черновой обработки."

    # === Диаметр ===
    if state == STATE_WAIT_DIAMETER:
        diameter = extract_diameter(text)
        if diameter:
            update_session(user_id, diameter=diameter, state=STATE_WAIT_MACHINE)
            return "📏 Диаметр принят! Какой станок используешь? ЧПУ или универсальный?"
        return "📏 Не понял диаметр. Укажи число, например: 50, 50.5, Ø32"

    # === Станок ===
    if state == STATE_WAIT_MACHINE:
        if "чпу" in text_lower or "cnc" in text_lower:
            update_session(user_id, machine_type="cnc", rpm_mode="vc", state=STATE_WAIT_MAX_RPM)
            return "✅ ЧПУ выбран. Укажи максимальные обороты шпинделя."
        if "универс" in text_lower or "ручн" in text_lower or "manual" in text_lower:
            update_session(user_id, machine_type="manual", rpm_mode="fixed", state=STATE_WAIT_MAX_RPM)
            return "✅ Универсальный выбран. Укажи максимальные обороты шпинделя."
        return "🏭 Укажи тип станка: ЧПУ или универсальный"

    # === Макс. обороты ===
    if state == STATE_WAIT_MAX_RPM:
        match = re.search(r'\d+', text)
        if match:
            rpm_value = int(match.group())
            machine = session.get("machine_type")
            if machine == "cnc":
                update_session(user_id, max_rpm_milling=rpm_value, state=STATE_READY)
            else:
                update_session(user_id, max_rpm_turning=rpm_value, state=STATE_READY)
            return f"⚡ Максимальные обороты установлены: {rpm_value} об/мин.\nТеперь напиши 'режим', чтобы получить рекомендации."
        return "⚠️ Не понял число. Укажи цифрами максимальные обороты шпинделя."

    # === READY — рекомендации / пользовательский RPM ===
    if state == STATE_READY:
        # 1. Рекомендации
        if any(k in text_lower for k in CALC_KEYWORDS):
            material = session.get("material")
            machine_type = session.get("machine_type")
            diameter = session.get("diameter")
            operation = session.get("operation")
            cut_type = session.get("cut_type", "rough")

            if not material or not diameter or not operation:
                return "❌ Не хватает параметров. Укажи материал, операцию и диаметр заново."

            rpm_data = recommend_rpm(material, machine_type, diameter, operation, cut_type)
            update_session(user_id, recommended_params=rpm_data, cut_type=cut_type)

            cut_type_display = "черновой" if cut_type == "rough" else "чистовой"
            machine_display = "ЧПУ" if machine_type == "cnc" else "универсального станка"

            msg = (f"🎯 Рекомендация для {cut_type_display} резания на {machine_display}:\n\n"
                   f"• Обороты: {rpm_data.get('rpm')} об/мин\n"
                   f"• Скорость резания: {rpm_data.get('vc')} м/мин\n")

            if rpm_data.get('feed_per_tooth'):
                msg += f"• Подача на зуб: {rpm_data['feed_per_tooth']} мм/зуб\n"
            if rpm_data.get('depth_of_cut'):
                msg += f"• Глубина реза: {rpm_data['depth_of_cut']} мм\n"
            if rpm_data.get('tool_type'):
                msg += f"• Инструмент: {rpm_data['tool_type']}\n"
            if rpm_data.get('notes'):
                msg += f"• Замечания: {rpm_data['notes']}\n"

            msg += ("\n📝 Если используешь другие обороты — просто напиши число.\n"
                    "🔄 Можешь изменить тип обработки: 'черновая' или 'чистовая'")
            return msg

        # 2. Изменение типа обработки
        if "чистовая" in text_lower or "чистов" in text_lower:
            update_session(user_id, cut_type="clean")
            return "✅ Тип обработки изменён на 'чистовая'. Напиши 'режим' для обновлённой рекомендации."

        if "черновая" in text_lower or "чернов" in text_lower:
            update_session(user_id, cut_type="rough")
            return "✅ Тип обработки изменён на 'черновая'. Напиши 'режим' для обновлённой рекомендации."

        # 3. Пользовательский ввод RPM
        user_match = re.search(r'\b(\d{2,5})\b', text)
        if user_match and session.get("recommended_params"):
            user_rpm = int(user_match.group(1))
            rec_rpm = session.get("recommended_params", {}).get("rpm")
            if rec_rpm:
                machine_limit = session.get("max_rpm_milling") if session.get("machine_type") == "cnc" else session.get("max_rpm_turning")
                analysis = evaluate_rpm_decision(user_rpm, rec_rpm, machine_limit)
                valid = rpm_is_reasonable(session.get("material"), session.get("diameter"), user_rpm)

                save_history(user_id, {
                    "material": session.get("material"),
                    "operation": session.get("operation"),
                    "cut_type": session.get("cut_type"),
                    "diameter": session.get("diameter"),
                    "machine_type": session.get("machine_type"),
                    "recommended_params": session.get("recommended_params"),
                    "user_choice": {"rpm": user_rpm},
                    "valid": valid
                })

                update_profile(user_id=user_id, delta=analysis["delta"], physics_valid=analysis["physics_valid"])

                cut_type_display = "черновой" if session.get("cut_type") == "rough" else "чистовой"
                if analysis["delta"] > 0.5:
                    return (f"Для {cut_type_display} обработки обычно используют обороты ниже.\n"
                            f"Ты работаешь на {user_rpm} об/мин — это выше среднего.\nЕсли так стабильно работает — ок 👍")
                elif analysis["delta"] < -0.5:
                    return (f"Ты используешь обороты ниже рекомендованных для {cut_type_display} обработки.\n"
                            f"Часто так делают для стабильности и увеличения ресурса инструмента.")
                else:
                    return f"Понял, {user_rpm} об/мин. Это близко к рекомендованным значениям для {cut_type_display} обработки."

        # 4. Изменение материала
        material_info = detect_material(text_lower)
        if material_info:
            material_id, material_name = material_info
            update_session(user_id, material=material_id, material_name=material_name, state=STATE_WAIT_CUT_TYPE)
            return f"🔄 Изменён материал на '{material_name}'. Укажи тип обработки (черновая/чистовая) или диаметр."

        # 5. Изменение диаметра
        diameter = extract_diameter(text_lower)
        if diameter:
            update_session(user_id, diameter=diameter, state=STATE_READY)
            return f"🔄 Диаметр изменён на {diameter} мм. Напиши 'режим' для получения рекомендаций."

        # 6. Изменение операции
        operation = detect_operation(text_lower)
        if operation:
            update_session(user_id, operation=operation, state=STATE_WAIT_CUT_TYPE)
            return f"🔄 Операция изменена на '{operation}'. Укажи тип обработки (черновая/чистовая)."

    return "🤖 Не понял запрос. Напиши 'помощь' для списка команд или 'покажи' для просмотра текущих параметров."
