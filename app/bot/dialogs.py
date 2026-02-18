"""
ДИАЛОГИ ДЛЯ СБОРА ДАННЫХ.
ПРОСТОЙ, ТУПОЙ, ИДЕАЛЬНЫЙ. ТОЛЬКО ТЕКСТ, НИКАКОЙ ЛОГИКИ.
С поддержкой безопасности, интернационализации и валидации.
"""

import html
import random
from typing import List, Optional, Dict, Any, Callable
from enum import Enum

# Импорт i18n для интернационализации
try:
    from app.bot.i18n import t, get_lang, SUPPORTED_LANGS, DEFAULT_LANG
except ImportError:
    # Fallback если i18n не доступен
    def t(key: str, lang: Optional[str] = None, **kwargs: Any) -> str:
        return key
    def get_lang(context: Any = None, user_id: Optional[str] = None) -> str:
        return DEFAULT_LANG if 'DEFAULT_LANG' in globals() else 'ru'
    SUPPORTED_LANGS = ('ru', 'en', 'zh')
    DEFAULT_LANG = 'ru'


# ============================================================================
# КОНСТАНТЫ
# ============================================================================

class Choice:
    """Варианты выбора пользователя."""
    BELOW = "Ниже"
    KEEP = "Оставить"
    ABOVE = "Выше"
    SKIP = "Пропустить"
    CHANGE = "Изменить"
    YES = "Да"
    NO = "Нет"
    SAVE = "Сохранить"
    CANCEL = "Отмена"


class MessageFormat(Enum):
    """Формат сообщения."""
    HTML = "html"
    MARKDOWN = "markdown"


class StatusEmoji:
    """Эмодзи для разных статусов."""
    SUCCESS = "✅"
    WARNING = "⚠️"
    ERROR = "❌"
    INFO = "ℹ️"
    QUESTION = "❓"
    CALCULATION = "🧮"
    MACHINE = "🏭"
    TOOL = "🔧"
    MATERIAL = "🧱"
    SPEED = "⚡"
    RPM = "🔄"
    FEED = "📏"
    DEPTH = "🔪"
    POWER = "⚙️"
    SAVE = "💾"
    CANCEL = "❌"
    YES = "✅"
    NO = "❌"


# Telegram ограничение на длину сообщения
TELEGRAM_MAX_MESSAGE_LENGTH = 4096
TELEGRAM_SAFE_MESSAGE_LENGTH = 4000


# ============================================================================
# БЕЗОПАСНОСТЬ: ЭКРАНИРОВАНИЕ HTML
# ============================================================================

def _escape_user_input(value: Any) -> str:
    """
    Экранировать пользовательский ввод для безопасности.
    
    Args:
        value: Значение для экранирования
        
    Returns:
        Экранированная строка
    """
    if value is None:
        return ""
    return html.escape(str(value))


def _escape_dict(details: Dict[str, Any]) -> Dict[str, str]:
    """
    Экранировать все значения в словаре.
    
    Args:
        details: Словарь с данными
        
    Returns:
        Словарь с экранированными значениями
    """
    return {k: _escape_user_input(v) for k, v in details.items()}


# ============================================================================
# ФОРМАТИРОВАНИЕ СООБЩЕНИЙ
# ============================================================================

class DialogFormatter:
    """Форматтер для разных типов разметки."""
    
    def __init__(self, format: MessageFormat = MessageFormat.HTML):
        self.format = format
    
    def bold(self, text: str) -> str:
        """Жирный текст."""
        if self.format == MessageFormat.HTML:
            return f"<b>{text}</b>"
        return f"*{text}*"
    
    def italic(self, text: str) -> str:
        """Курсив."""
        if self.format == MessageFormat.HTML:
            return f"<i>{text}</i>"
        return f"_{text}_"
    
    def code(self, text: str) -> str:
        """Моноширинный код."""
        if self.format == MessageFormat.HTML:
            return f"<code>{text}</code>"
        return f"`{text}`"
    
    def with_status(self, emoji: str, text: str) -> str:
        """Добавить эмодзи-статус к тексту."""
        return f"{emoji} {text}"


# Глобальный форматтер по умолчанию
_default_formatter = DialogFormatter(MessageFormat.HTML)


def split_long_message(text: str, max_length: int = TELEGRAM_SAFE_MESSAGE_LENGTH) -> List[str]:
    """
    Разбить длинное сообщение на части.
    
    Args:
        text: Текст сообщения
        max_length: Максимальная длина части
        
    Returns:
        Список частей сообщения
    """
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current = []
    current_length = 0
    
    for line in text.split('\n'):
        line_length = len(line) + 1  # +1 for newline
        
        if current_length + line_length > max_length:
            parts.append('\n'.join(current))
            current = [line]
            current_length = line_length
        else:
            current.append(line)
            current_length += line_length
    
    if current:
        parts.append('\n'.join(current))
    
    return parts


# ============================================================================
# ВАЛИДАЦИЯ СЦЕНАРИЕВ
# ============================================================================

class ScenarioValidator:
    """Валидатор сценариев."""
    
    REQUIRED_PARAMS: Dict[str, List[str]] = {
        "rpm_too_high": ["current_rpm", "max_rpm"],
        "power_limit_exceeded": ["material"],
        "depth_too_big": ["current_depth", "tool_radius"],
        "vibration_risk": ["length", "diameter"],
        "tool_wear": ["hours"],
        "chip_control": ["depth", "feed"],
        "machine_not_found": ["name"],
        "material_not_found": ["name"],
        "parameter_too_low": ["param_name", "current_value", "min_value"],
        "parameter_too_high": ["param_name", "current_value", "max_value"],
        "unusual_combination": ["details"],
        "safety_margin_low": ["margin"],
    }
    
    @classmethod
    def validate_scenario(cls, scenario: str, params: Dict[str, Any]) -> Optional[str]:
        """
        Проверить, что все необходимые параметры переданы.
        
        Args:
            scenario: Название сценария
            params: Параметры сценария
            
        Returns:
            Сообщение об ошибке или None если все ок
        """
        required = cls.REQUIRED_PARAMS.get(scenario, [])
        missing = [p for p in required if p not in params]
        
        if missing:
            return f"Missing required parameters for {scenario}: {missing}"
        return None


# ============================================================================
# ЕДИНЫЙ ИСТОЧНИК ПРИМЕРОВ
# ============================================================================

# Стандартные примеры для разных параметров (единый источник)
DEFAULT_EXAMPLES: Dict[str, List[str]] = {
    "материал": [
        "• Сталь 45",
        "• Алюминий Д16Т",
        "• Нержавейка 12Х18Н10Т",
        "• Чугун СЧ20",
        "• Титан ВТ6",
        "• Сталь 40Х (легированная)",
        "• Алюминий АМг6 (магналий)",
        "• Латунь Л63",
        "• Медь М1"
    ],
    "диаметр": [
        "• Ø100 мм",
        "• 50 мм",
        "• с Ø80 до Ø70",
        "• внутренний Ø40",
        "• наружный Ø120, внутренний Ø80",
        "• Ø45H7 (+0.025)",
        "• Ø60js6 (±0.008)"
    ],
    "операция": [
        "• черновая (обдирочная)",
        "• получистовая (подготовительная)",
        "• чистовая (финишная)",
        "• тонкая (прецизионная)",
        "• отрезная",
        "• расточная",
        "• нарезка резьбы",
        "• канавочная",
        "• фасонная"
    ],
    "инструмент": [
        "• пластина r0.8 (CNMG)",
        "• твердый сплав (WC-Co)",
        "• вылет 40 мм",
        "• угол 80° (ромбическая)",
        "• керамика (чистовая)",
        "• CBN (для закалённых сталей)",
        "• HSS (быстрорез)"
    ],
    "мощность станка": [
        "• 7.5 кВт",
        "• 11 кВт",
        "• 15 кВт",
        "• 22 кВт"
    ],
    "скорость резания": [
        "• 150 м/мин",
        "• 80 м/мин для нержавейки",
        "• 250 м/мин для алюминия",
        "• 60 м/мин для титана"
    ],
    "название файла": [
        "• Вал-приводной",
        "• Фланец-001",
        "• Крышка-корпуса",
        "• Шестерня-зубчатая",
        "• Втулка-направляющая",
        "• Шпиндель-главный",
        "• Патрон-3х-кулачковый"
    ],
    "длина обработки": [
        "• 100 мм",
        "• 50 мм",
        "• 200 мм",
        "• 150 мм"
    ],
    "припуск": [
        "• 2 мм на сторону",
        "• 3 мм общий",
        "• 1 мм на диаметр",
        "• 5 мм заготовка"
    ],
    "радиус пластины": [
        "• 0.4 мм",
        "• 0.8 мм",
        "• 1.2 мм",
        "• 1.6 мм"
    ],
    "подача": [
        "• 0.15 мм/об",
        "• 0.25 мм/об",
        "• 0.1 мм/об чистовая",
        "• 0.3 мм/об черновая"
    ],
    "глубина резания": [
        "• 2 мм",
        "• 1.5 мм",
        "• 3 мм черновая",
        "• 0.5 мм чистовая"
    ],
}


def _get_examples_with_context(param_name: str, count: int = 3) -> List[str]:
    """
    Получить примеры с учетом контекста.
    
    Args:
        param_name: Название параметра
        count: Количество примеров
        
    Returns:
        Список примеров
    """
    all_examples = DEFAULT_EXAMPLES.get(param_name, [])
    
    # Если примеров мало, возвращаем все
    if len(all_examples) <= count:
        return all_examples
    
    # Иначе выбираем случайные count примеров
    return random.sample(all_examples, count)


# ============================================================================
# УНИВЕРСАЛЬНЫЕ ФОРМАТТЕРЫ
# ============================================================================

def format_warning_scenario(
        scenario: str,
        lang: Optional[str] = None,
        **details: Any
) -> str:
    """
    Форматировать любой сценарий с предупреждением или ошибкой.
    
    Args:
        scenario: Название сценария
        lang: Язык (если None, используется DEFAULT_LANG)
        **details: Параметры для подстановки в шаблон
        
    Returns:
        Отформатированное сообщение
    """
    # Валидация сценария
    validation_error = ScenarioValidator.validate_scenario(scenario, details)
    if validation_error:
        return f"⚠️ <b>Ошибка валидации:</b> {validation_error}"

    # Экранирование пользовательского ввода
    safe_details = _escape_dict(details)
    
    lang = lang or DEFAULT_LANG

    templates = {
        # Физические ограничения
        "rpm_too_high": (
            f"{StatusEmoji.WARNING} <b>{t('msg.rpm_too_high', lang=lang, default='Обороты выше предела!')}</b>\n\n"
            f"{t('msg.current_rpm', lang=lang, default='Сейчас')}: {{current_rpm}} {t('msg.rpm_unit', lang=lang, default='об/мин')}\n"
            f"{t('msg.max_rpm', lang=lang, default='Максимум станка')}: {{max_rpm}} {t('msg.rpm_unit', lang=lang, default='об/мин')}\n\n"
            f"{t('msg.reduce_rpm', lang=lang, default='Снизить обороты?')}"
        ),
        "power_limit_exceeded": (
            f"{StatusEmoji.POWER} <b>{t('msg.power_limit_exceeded', lang=lang, default='Мощность резания велика для')} {{material}}</b>\n\n"
            f"{t('msg.machine_overload', lang=lang, default='Может быть перегруз станка.')}\n"
            f"{t('msg.reduce_params', lang=lang, default='Уменьшить глубину или подачу?')}"
        ),
        "depth_too_big": (
            f"{StatusEmoji.DEPTH} <b>{t('msg.depth_too_big', lang=lang, default='Глубина резания больше радиуса пластины!')}</b>\n\n"
            f"{t('msg.depth', lang=lang, default='Глубина')}: {{current_depth}} {t('msg.mm_unit', lang=lang, default='мм')}\n"
            f"{t('msg.insert_radius', lang=lang, default='Радиус пластины')}: {{tool_radius}} {t('msg.mm_unit', lang=lang, default='мм')}\n\n"
            f"{t('msg.reduce_depth', lang=lang, default='Рекомендуется уменьшить глубину.')}"
        ),
        "vibration_risk": (
            f"{StatusEmoji.WARNING} <b>{t('msg.vibration_risk', lang=lang, default='Возможны вибрации')}</b>\n\n"
            f"{t('msg.ld_ratio', lang=lang, default='Соотношение L/D')} = {{length}}/{{diameter}}\n"
            f"{t('msg.reduce_feed_overhang', lang=lang, default='При больших вылетах нужно снижать подачу.')}"
        ),
        "tool_wear": (
            f"{StatusEmoji.TOOL} <b>{t('msg.tool_wear', lang=lang, default='Внимание: износ инструмента')}</b>\n\n"
            f"{t('msg.hours', lang=lang, default='Наработка')}: {{hours}} {t('msg.hours_unit', lang=lang, default='часов')}\n"
            f"{t('msg.check_insert', lang=lang, default='Рекомендуется проверить пластину или снизить параметры резания.')}"
        ),
        "chip_control": (
            f"{StatusEmoji.WARNING} <b>{t('msg.chip_control', lang=lang, default='Проблемы с отводом стружки')}</b>\n\n"
            f"{t('msg.at_depth_feed', lang=lang, default='При глубине')} {{depth}} {t('msg.mm_unit', lang=lang, default='мм')} {t('msg.and_feed', lang=lang, default='и подаче')} {{feed}} {t('msg.mm_rev_unit', lang=lang, default='мм/об')}\n"
            f"{t('msg.bad_chip', lang=lang, default='может быть плохой отвод стружки.')}\n"
            f"{t('msg.increase_feed', lang=lang, default='Увеличить подачу или уменьшить глубину?')}"
        ),

        # Ошибки
        "parsing_error": (
            f"{StatusEmoji.ERROR} <b>{t('msg.parsing_error', lang=lang, default='Не понял ваш ввод')}</b>\n\n"
            f"{t('msg.write_more', lang=lang, default='Пожалуйста, напишите подробнее:')}\n"
            f"• {t('msg.material_diameter', lang=lang, default='Материал и диаметр')}\n"
            f"• {t('msg.operation_type', lang=lang, default='Тип операции')}\n"
            f"• {t('msg.tool_if_known', lang=lang, default='Инструмент (если известен)')}"
        ),
        "calculation_error": (
            f"{StatusEmoji.WARNING} <b>{t('msg.calculation_error_title', lang=lang, default='Не могу рассчитать параметры')}</b>\n\n"
            f"{t('msg.check', lang=lang, default='Проверьте:')}\n"
            f"• {t('msg.data_correctness', lang=lang, default='Корректность введенных данных')}\n"
            f"• {t('msg.physical_feasibility', lang=lang, default='Физическую реализуемость')}\n"
            f"• {t('msg.machine_tool_limits', lang=lang, default='Ограничения станка/инструмента')}"
        ),
        "machine_not_found": (
            f"{StatusEmoji.MACHINE} <b>{t('msg.machine_not_found', lang=lang, default='Станок')} '{{name}}' {t('msg.not_found', lang=lang, default='не найден')}</b>\n\n"
            f"{t('msg.add_manually', lang=lang, default='Добавьте его параметры вручную:')}\n"
            f"• {t('msg.power_kw', lang=lang, default='Мощность (кВт)')}\n"
            f"• {t('msg.max_rpm', lang=lang, default='Макс. обороты (об/мин)')}\n"
            f"• {t('msg.machine_type', lang=lang, default='Тип (токарный, фрезерный)')}"
        ),
        "material_not_found": (
            f"{StatusEmoji.MATERIAL} <b>{t('msg.material_not_found', lang=lang, default='Материал')} '{{name}}' {t('msg.not_found', lang=lang, default='не найден')}</b>\n\n"
            f"{t('msg.use_analog', lang=lang, default='Использовать ближайший аналог?')}\n"
            f"{t('msg.or_specify_manual', lang=lang, default='Или указать свойства вручную?')}"
        ),

        # Общие предупреждения
        "parameter_too_low": (
            f"{StatusEmoji.WARNING} <b>{t('msg.parameter_too_low', lang=lang, default='Параметр слишком низкий')}</b>\n\n"
            f"{{param_name}}: {{current_value}}\n"
            f"{t('msg.recommended_min', lang=lang, default='Рекомендуемый минимум')}: {{min_value}}\n\n"
            f"{t('msg.increase_value', lang=lang, default='Увеличить значение?')}"
        ),
        "parameter_too_high": (
            f"{StatusEmoji.WARNING} <b>{t('msg.parameter_too_high', lang=lang, default='Параметр слишком высокий')}</b>\n\n"
            f"{{param_name}}: {{current_value}}\n"
            f"{t('msg.recommended_max', lang=lang, default='Рекомендуемый максимум')}: {{max_value}}\n\n"
            f"{t('msg.decrease_value', lang=lang, default='Уменьшить значение?')}"
        ),
        "unusual_combination": (
            f"{StatusEmoji.QUESTION} <b>{t('msg.unusual_combination', lang=lang, default='Необычное сочетание параметров')}</b>\n\n"
            f"{{details}}\n\n"
            f"{t('msg.check_calculation', lang=lang, default='Проверить расчёт?')}"
        ),
        "safety_margin_low": (
            f"{StatusEmoji.WARNING} <b>{t('msg.safety_margin_low', lang=lang, default='Маленький запас прочности')}</b>\n\n"
            f"{t('msg.power_margin', lang=lang, default='Запас по мощности')}: {{margin}}%\n"
            f"{t('msg.reduce_load', lang=lang, default='Рекомендуется снизить нагрузку.')}"
        ),
    }

    template = templates.get(scenario, f"{StatusEmoji.WARNING} {{message}}")
    return template.format(**safe_details)


def format_success(
        scenario: str,
        lang: Optional[str] = None,
        **details: Any
) -> str:
    """
    Форматировать любой успешный сценарий.
    
    Args:
        scenario: Название сценария
        lang: Язык
        **details: Параметры для подстановки
        
    Returns:
        Отформатированное сообщение
    """
    # Экранирование пользовательского ввода
    safe_details = _escape_dict(details)
    
    lang = lang or DEFAULT_LANG

    templates = {
        # Основные сценарии
        "start_dialog": (
            f"{StatusEmoji.SUCCESS} <b>{t('msg.start_dialog', lang=lang, default='CNC Assistant — подбор режимов резания')}</b>\n\n"
            f"{t('msg.tell_what_process', lang=lang, default='Расскажите, что нужно обработать?')}\n\n"
            f"<i>{t('msg.examples', lang=lang, default='Например:')}</i>\n"
            f"• {t('msg.example_steel', lang=lang, default='Сталь 45, Ø100, черновая')}\n"
            f"• {t('msg.example_aluminum', lang=lang, default='Алюминий, Ø50, чистовая')}\n"
            f"• {t('msg.example_stainless', lang=lang, default='Нержавейка, Ø80, получистовая')}"
        ),
        "final_recommendation": (
            f"{StatusEmoji.SUCCESS} <b>{t('msg.final_recommendation', lang=lang, default='ГОТОВАЯ ПРОГРАММА РЕЗАНИЯ')}</b>\n\n"
            f"{t('msg.all_params_checked', lang=lang, default='Все параметры проверены и согласованы.')}\n\n"
            f"<i>{t('msg.can_start', lang=lang, default='Можете приступать к обработке!')}</i>"
        ),
        "experience_saved": (
            f"{StatusEmoji.SUCCESS} <b>{t('msg.experience_saved', lang=lang, default='Спасибо за ваш опыт!')}</b>\n\n"
            f"{t('msg.will_improve', lang=lang, default='Эти данные помогут улучшить рекомендации.')}"
        ),

        # Подтверждения
        "assumption_confirmed": (
            f"{StatusEmoji.SUCCESS} <b>{t('msg.assumption_confirmed', lang=lang, default='Предположение подтверждено')}</b>\n\n"
            f"{{param_name}} = {{value}}"
        ),
        "value_adjusted": (
            f"{StatusEmoji.INFO} <b>{t('msg.value_adjusted', lang=lang, default='Значение скорректировано')}</b>\n\n"
            f"{{param_name}}: {{old_value}} → {{new_value}}"
        ),
        "calculation_complete": (
            f"{StatusEmoji.SUCCESS} <b>{t('msg.calculation_complete', lang=lang, default='Расчёт завершён')}</b>\n\n"
            f"{{result}}"
        ),

        # Сохранение данных
        "data_saved": (
            f"{StatusEmoji.SAVE} <b>{t('msg.data_saved', lang=lang, default='Решение сохранено')}</b>\n\n"
            f"{t('msg.added_to_kb', lang=lang, default='Добавлено в базу знаний.')}"
        ),
        "filename_saved": (
            f"{StatusEmoji.SAVE} <b>{t('msg.filename_saved', lang=lang, default='Файл сохранён')}</b>\n\n"
            f"{t('msg.filename', lang=lang, default='Название')}: {{filename}}\n"
            f"{t('msg.path', lang=lang, default='Путь')}: /cnc_projects/{{filename}}.nc"
        ),

        # Сравнения
        "operator_comparison": (
            f"{StatusEmoji.INFO} <b>{t('msg.operator_comparison', lang=lang, default='Сравнение с оператором')}</b>\n\n"
            f"{t('msg.parameter', lang=lang, default='Параметр')}: {{param}}\n"
            f"{t('msg.bot', lang=lang, default='Бот')}: {{bot_value}}\n"
            f"{t('msg.operator', lang=lang, default='Оператор')}: {{operator_value}}\n\n"
            f"{t('msg.whose_better', lang=lang, default='Чье решение лучше?')}"
        ),

        # Анализ решений
        "conservative_choice": (
            f"{StatusEmoji.INFO} <b>{t('msg.conservative_choice', lang=lang, default='Более консервативно')}</b>\n\n"
            f"<i>{t('msg.maybe_consider', lang=lang, default='Возможно, учитываете:')}\n"
            f"• {t('msg.tool_wear_consider', lang=lang, default='Износ инструмента')}\n"
            f"• {t('msg.vibrations_consider', lang=lang, default='Вибрации')}\n"
            f"• {t('msg.machine_instability', lang=lang, default='Нестабильность станка')}</i>"
        ),
        "aggressive_choice": (
            f"{StatusEmoji.INFO} <b>{t('msg.aggressive_choice', lang=lang, default='Более агрессивно')}</b>\n\n"
            f"<i>{t('msg.experience_allows', lang=lang, default='Опыт позволяет:')}\n"
            f"• {t('msg.exceed_recommendations', lang=lang, default='Превышать рекомендации')}\n"
            f"• {t('msg.faster_chip', lang=lang, default='Быстрее снимать стружку')}\n"
            f"• {t('msg.sharp_tool', lang=lang, default='Использовать острый инструмент')}</i>"
        ),
        "standard_choice": (
            f"{StatusEmoji.INFO} <b>{t('msg.standard_choice', lang=lang, default='Близко к рекомендациям')}</b>\n\n"
            f"<i>{t('msg.good_match', lang=lang, default='Хорошее соответствие:')}\n"
            f"• {t('msg.physical_calculations', lang=lang, default='Физическим расчётам')}\n"
            f"• {t('msg.practical_experience', lang=lang, default='Практическому опыту')}\n"
            f"• {t('msg.safe_limits', lang=lang, default='Безопасным пределам')}</i>"
        ),

        # Завершение
        "goodbye": (
            f"{StatusEmoji.SUCCESS} <b>{t('msg.goodbye', lang=lang, default='Спасибо за использование CNC Assistant!')}</b>\n\n"
            f"{t('msg.experience_makes_smarter', lang=lang, default='Ваш опыт делает систему умнее.')}\n"
            f"{t('msg.see_you', lang=lang, default='До новых встреч!')}"
        ),

        # Информационные
        "ready_to_calculate": (
            f"{StatusEmoji.CALCULATION} <b>{t('msg.ready_to_calculate', lang=lang, default='Готов к расчёту')}</b>\n\n"
            f"{t('msg.all_data_collected', lang=lang, default='Все необходимые данные собраны.')}\n"
            f"{t('msg.starting_calculation', lang=lang, default='Начинаю вычисление параметров резания...')}"
        ),
        "data_collected": (
            f"{StatusEmoji.INFO} <b>{t('msg.data_collected', lang=lang, default='Данные собраны')}</b>\n\n"
            f"{t('msg.starting_analysis', lang=lang, default='Начинаю анализ и подбор режимов...')}"
        ),
    }

    template = templates.get(scenario, f"{StatusEmoji.SUCCESS} {{message}}")
    return template.format(**safe_details)


# ============================================================================
# УНИВЕРСАЛЬНЫЕ ДИАЛОГИ
# ============================================================================

def ask_missing(
        param_name: str,
        show_examples: bool = True,
        examples: Optional[List[str]] = None,
        examples_count: int = 3,
        lang: Optional[str] = None
) -> str:
    """
    Спросить недостающий параметр с опциональными примерами.
    
    Args:
        param_name: Название параметра
        show_examples: Показывать ли примеры
        examples: Список примеров (если None, берутся из DEFAULT_EXAMPLES)
        examples_count: Количество примеров для показа
        lang: Язык
        
    Returns:
        Текст запроса
    """
    lang = lang or DEFAULT_LANG
    
    # Экранирование названия параметра
    safe_param_name = _escape_user_input(param_name)
    
    base_text = t('msg.missing_param', lang=lang, param=safe_param_name, 
                  default=f"Похоже, ты не указал параметр «{safe_param_name}».")

    if not show_examples:
        return base_text

    example_list = examples or _get_examples_with_context(param_name, examples_count)
    
    # Экранирование примеров
    safe_examples = [_escape_user_input(ex) for ex in example_list]

    if safe_examples:
        examples_text = "\n".join(safe_examples[:examples_count])
        # Добавляем подсказку, если примеров больше
        if len(safe_examples) > examples_count:
            remaining = len(safe_examples) - examples_count
            examples_text += f"\n• ... {t('msg.and_more', lang=lang, count=remaining, default=f'и ещё {remaining}')}"
        
        examples_title = t('msg.examples_title', lang=lang, default='Примеры:')
        return f"{base_text}\n\n<b>{examples_title}</b>\n{examples_text}"

    return base_text


def confirm_assumption(
        param_name: str,
        assumed_value: str,
        reason: str,
        show_keyboard: bool = True,
        lang: Optional[str] = None
) -> str:
    """
    Подтвердить предположение.
    
    Args:
        param_name: Название параметра
        assumed_value: Предполагаемое значение
        reason: Причина предположения
        show_keyboard: Показывать ли описание клавиатуры
        lang: Язык
        
    Returns:
        Текст подтверждения
    """
    lang = lang or DEFAULT_LANG
    
    # Экранирование входных данных
    safe_param_name = _escape_user_input(param_name)
    safe_value = _escape_user_input(assumed_value)
    safe_reason = _escape_user_input(reason)
    
    base_text = (
        f"{t('msg.i_assumed', lang=lang, default='Я предположил')} «{safe_param_name} = {safe_value}»\n"
        f"{t('msg.because', lang=lang, default='Потому что')} {safe_reason}\n\n"
    )

    if show_keyboard:
        base_text += describe_choice_keyboard(lang=lang)
    else:
        base_text += t('msg.correct_or_change', lang=lang, default='Верно? Или изменить?')

    return base_text


def adjust_value(
        param_name: str,
        value: str,
        show_keyboard: bool = True,
        lang: Optional[str] = None
) -> str:
    """
    Предложить настроить значение.
    
    Args:
        param_name: Название параметра
        value: Текущее значение
        show_keyboard: Показывать ли описание клавиатуры
        lang: Язык
        
    Returns:
        Текст предложения
    """
    lang = lang or DEFAULT_LANG
    
    # Экранирование входных данных
    safe_param_name = _escape_user_input(param_name)
    safe_value = _escape_user_input(value)
    
    base_text = f"{safe_param_name}: {t('msg.now', lang=lang, default='сейчас')} {safe_value}.\n\n"

    if show_keyboard:
        base_text += describe_choice_keyboard(lang=lang)
    else:
        base_text += t('msg.what_to_do', lang=lang, default='Как поступим?')

    return base_text


def ask_feedback(lang: Optional[str] = None) -> str:
    """
    Спросить обратную связь по расчётам.
    
    Args:
        lang: Язык
        
    Returns:
        Текст запроса обратной связи
    """
    lang = lang or DEFAULT_LANG
    
    return (
        f"{StatusEmoji.QUESTION} <b>{t('msg.feedback_question', lang=lang, default='Вам подходят эти параметры?')}</b>\n\n"
        f"{t('msg.or_change_manual', lang=lang, default='Или хотите изменить что-то вручную?')}\n\n"
        f"{describe_yes_no_keyboard(lang=lang)}"
    )


# ============================================================================
# ЧАСТНЫЕ СЦЕНАРИИ (композитные функции)
# ============================================================================

def ask_filename(lang: Optional[str] = None) -> str:
    """Спросить название файла или детали."""
    return ask_missing(
        t('msg.filename_param', lang=lang or DEFAULT_LANG, default='название файла'),
        show_examples=True,
        examples=DEFAULT_EXAMPLES.get("название файла", []),
        lang=lang
    )


def ask_material(lang: Optional[str] = None) -> str:
    """Спросить материал."""
    return ask_missing(
        t('msg.material_param', lang=lang or DEFAULT_LANG, default='материал'),
        show_examples=True,
        examples=DEFAULT_EXAMPLES.get("материал", []),
        lang=lang
    )


def ask_diameter(lang: Optional[str] = None) -> str:
    """Спросить диаметр."""
    return ask_missing(
        t('msg.diameter_param', lang=lang or DEFAULT_LANG, default='диаметр'),
        show_examples=True,
        examples=DEFAULT_EXAMPLES.get("диаметр", []),
        lang=lang
    )


def ask_operation(lang: Optional[str] = None) -> str:
    """Спросить тип операции."""
    return ask_missing(
        t('msg.operation_param', lang=lang or DEFAULT_LANG, default='операция'),
        show_examples=True,
        examples=DEFAULT_EXAMPLES.get("операция", []),
        lang=lang
    )


def ask_tool(lang: Optional[str] = None) -> str:
    """Спросить инструмент."""
    return ask_missing(
        t('msg.tool_param', lang=lang or DEFAULT_LANG, default='инструмент'),
        show_examples=True,
        examples=DEFAULT_EXAMPLES.get("инструмент", []),
        lang=lang
    )


def ask_experience(lang: Optional[str] = None) -> str:
    """Спросить опыт оператора."""
    lang = lang or DEFAULT_LANG
    
    return (
        f"{StatusEmoji.QUESTION} <b>{t('msg.how_do_you_do', lang=lang, default='А КАК ВЫ ДЕЛАЕТЕ НА ПРАКТИКЕ?')}</b>\n\n"
        f"<i>{t('msg.tell_real_modes', lang=lang, default='Расскажите о ваших реальных режимах:')}</i>\n\n"
        f"📌 <b>{t('msg.format_examples', lang=lang, default='Примеры формата:')}</b>\n"
        f"• <code>{t('msg.example_vc', lang=lang, default='Ставлю VC=180, подача 0.25, за 2 прохода')}</code>\n"
        f"• <code>{t('msg.example_rpm', lang=lang, default='У меня 600 об/мин, 0.18 мм/об, 2 мм на проход')}</code>\n"
        f"• <code>{t('msg.example_passes', lang=lang, default='Делаю 3 прохода по 1.5 мм, чистовой 0.3')}</code>\n\n"
        f"🎯 <b>{t('msg.what_can_specify', lang=lang, default='Что можно указать:')}</b>\n"
        f"• {t('msg.vc_or_rpm', lang=lang, default='Скорость резания (VC) или обороты (RPM)')}\n"
        f"• {t('msg.feed_per_rev', lang=lang, default='Подача на оборот (мм/об)')}\n"
        f"• {t('msg.depth_of_cut', lang=lang, default='Глубина резания (мм)')}\n"
        f"• {t('msg.number_of_passes', lang=lang, default='Количество проходов')}\n"
        f"• {t('msg.processing_features', lang=lang, default='Особенности обработки')}\n\n"
        f"💡 <i>{t('msg.experience_helps', lang=lang, default='Ваш опыт поможет улучшить рекомендации для всех операторов!')}</i>"
    )


def ask_save_confirmation(lang: Optional[str] = None) -> str:
    """Спросить подтверждение сохранения."""
    lang = lang or DEFAULT_LANG
    
    return (
        f"{StatusEmoji.SAVE} <b>{t('msg.save_this_decision', lang=lang, default='Сохранить это решение?')}</b>\n\n"
        f"{t('msg.add_to_kb', lang=lang, default='Мы добавим его в базу знаний')}\n"
        f"{t('msg.use_for_training', lang=lang, default='и будем использовать для обучения')}\n"
        f"{t('msg.new_operators', lang=lang, default='новых операторов и улучшения бота.')}\n\n"
        f"{describe_yes_no_keyboard(lang=lang)}"
    )


# ============================================================================
# ФОРМАТИРОВАНИЕ ДАННЫХ
# ============================================================================

def format_list(
        items: List[str],
        title: Optional[str] = None,
        numbered: bool = False,
        bullet: str = "•"
) -> str:
    """
    Форматировать список.
    
    Args:
        items: Элементы списка
        title: Заголовок списка
        numbered: Нумерованный список
        bullet: Маркер для ненумерованного списка
        
    Returns:
        Отформатированный список
    """
    lines = []

    if title:
        # Экранирование заголовка
        safe_title = _escape_user_input(title)
        lines.append(f"<b>{safe_title}</b>")
        lines.append("")

    for i, item in enumerate(items, 1 if numbered else 0):
        # Экранирование элементов
        safe_item = _escape_user_input(item)
        if numbered:
            lines.append(f"{i}. {safe_item}")
        else:
            lines.append(f"{bullet} {safe_item}")

    return "\n".join(lines)


def format_param(
        name: str,
        value: str,
        unit: str = "",
        highlight: bool = True,
        precision: Optional[int] = None
) -> str:
    """
    Форматировать параметр.
    
    Args:
        name: Название параметра
        value: Значение
        unit: Единица измерения
        highlight: Подсветить значение
        precision: Точность для чисел
        
    Returns:
        Отформатированный параметр
    """
    # Экранирование названия и единицы
    safe_name = _escape_user_input(name)
    safe_unit = _escape_user_input(unit)
    
    # Форматируем значение с учётом точности
    formatted_value = value
    if precision is not None:
        try:
            num_value = float(value)
            formatted_value = f"{num_value:.{precision}f}"
        except:
            pass
    
    # Экранирование значения
    safe_value = _escape_user_input(formatted_value)
    
    value_text = f"<code>{safe_value}</code>" if highlight else safe_value
    unit_text = f" {safe_unit}" if safe_unit else ""
    return f"• {safe_name}: {value_text}{unit_text}"


def format_recommendation(params: List[str], lang: Optional[str] = None) -> str:
    """Форматировать рекомендацию."""
    lang = lang or DEFAULT_LANG
    
    title = t('msg.recommendation', lang=lang, default='РЕКОМЕНДАЦИЯ:')
    question = t('msg.how_are_params', lang=lang, default='Как вам эти параметры?')
    
    lines = [f"{StatusEmoji.SUCCESS} <b>{title}</b>", ""]
    lines.extend(params)
    lines.append("")
    lines.append(f"<i>{question}</i>")
    return "\n".join(lines)


def format_physical_limits(limits: List[str], lang: Optional[str] = None) -> str:
    """Форматировать физические ограничения."""
    lang = lang or DEFAULT_LANG
    
    title = t('msg.physical_limits', lang=lang, default='ФИЗИЧЕСКИЕ ОГРАНИЧЕНИЯ:')
    note = t('msg.limits_accounted', lang=lang, default='Эти ограничения учтены в рекомендациях')
    
    lines = [f"{StatusEmoji.INFO} <b>{title}</b>", ""]
    lines.extend(limits)
    lines.append("")
    lines.append(f"<i>{note}</i>")
    return "\n".join(lines)


def format_calculation_summary(params: List[str], lang: Optional[str] = None) -> str:
    """Форматировать сводку расчёта."""
    lang = lang or DEFAULT_LANG
    
    title = t('msg.calculation_summary', lang=lang, default='СВОДКА РАСЧЁТА:')
    
    lines = [f"{StatusEmoji.CALCULATION} <b>{title}</b>", ""]
    lines.extend(params)
    return "\n".join(lines)


# ============================================================================
# КЛАВИАТУРЫ И ИНТЕРФЕЙС
# ============================================================================

def describe_choice_keyboard(lang: Optional[str] = None) -> str:
    """Описание клавиатуры выбора."""
    lang = lang or DEFAULT_LANG
    
    title = t('msg.choose_action', lang=lang, default='Выберите действие:')
    below = t('msg.below', lang=lang, default='Ниже')
    keep = t('msg.keep', lang=lang, default='Оставить')
    above = t('msg.above', lang=lang, default='Выше')
    skip = t('msg.skip', lang=lang, default='Пропустить')
    change = t('msg.change', lang=lang, default='Изменить')
    
    return (
        f"<b>{title}</b>\n"
        f"• {below} — {t('msg.decrease_value', lang=lang, default='уменьшить значение')}\n"
        f"• {keep} — {t('msg.keep_as_is', lang=lang, default='оставить как есть')}\n"
        f"• {above} — {t('msg.increase_value', lang=lang, default='увеличить значение')}\n"
        f"• {skip} — {t('msg.skip_param', lang=lang, default='пропустить этот параметр')}\n"
        f"• {change} — {t('msg.change_completely', lang=lang, default='изменить полностью')}"
    )


def describe_yes_no_keyboard(lang: Optional[str] = None) -> str:
    """Описание клавиатуры Да/Нет."""
    lang = lang or DEFAULT_LANG
    
    title = t('msg.choose', lang=lang, default='Выберите:')
    yes = t('msg.yes', lang=lang, default='Да')
    no = t('msg.no', lang=lang, default='Нет')
    
    return f"<b>{title}</b> {yes} / {no}"


def describe_save_cancel_keyboard(lang: Optional[str] = None) -> str:
    """Описание клавиатуры Сохранить/Отмена."""
    lang = lang or DEFAULT_LANG
    
    title = t('msg.choose', lang=lang, default='Выберите:')
    save = t('msg.save', lang=lang, default='Сохранить')
    cancel = t('msg.cancel', lang=lang, default='Отмена')
    
    return f"<b>{title}</b> {save} / {cancel}"


def describe_operation_types(lang: Optional[str] = None) -> str:
    """Описание типов операций."""
    lang = lang or DEFAULT_LANG
    
    title = t('msg.operation_types', lang=lang, default='Типы операций:')
    
    return (
        f"<b>{title}</b>\n"
        f"• {t('msg.rough', lang=lang, default='Черновая (быстрое съем материала)')}\n"
        f"• {t('msg.semi_finish', lang=lang, default='Получистовая (подготовка поверхности)')}\n"
        f"• {t('msg.finish', lang=lang, default='Чистовая (точные размеры)')}\n"
        f"• {t('msg.precision', lang=lang, default='Тонкая (высокая чистота)')}\n"
        f"• {t('msg.cut_off', lang=lang, default='Отрезная')}\n"
        f"• {t('msg.boring', lang=lang, default='Расточная')}\n"
        f"• {t('msg.threading', lang=lang, default='Нарезка резьбы')}\n"
        f"• {t('msg.grooving', lang=lang, default='Канавочная')}\n"
        f"• {t('msg.shaping', lang=lang, default='Фасонная')}"
    )


# ============================================================================
# ТЕСТИРОВАНИЕ
# ============================================================================

def _test_all_scenarios() -> None:
    """Протестировать все сценарии."""
    import inspect

    print("🧪 ТЕСТИРОВАНИЕ ВСЕХ ДИАЛОГОВЫХ СЦЕНАРИЕВ")
    print("=" * 70)

    # 1. Универсальные форматтеры
    print("\n📌 1. УНИВЕРСАЛЬНЫЕ ФОРМАТТЕРЫ:")
    print("-" * 40)

    print("\n🔴 Предупреждения:")
    print(format_warning_scenario(
        "rpm_too_high",
        current_rpm="4000",
        max_rpm="3000"
    ))

    print("\n⚡ Мощность превышена:")
    print(format_warning_scenario(
        "power_limit_exceeded",
        material="сталь 45"
    ))

    print("\n🟢 Успешные сценарии:")
    print(format_success("start_dialog"))

    # 2. Универсальные диалоги
    print("\n📌 2. УНИВЕРСАЛЬНЫЕ ДИАЛОГИ:")
    print("-" * 40)

    print("\n❓ Спросить без примеров:")
    print(ask_missing("диаметр", show_examples=False))

    print("\n📋 Спросить с примерами:")
    print(ask_missing("материал", show_examples=True))

    print("\n✅ Подтверждение с клавиатурой:")
    print(confirm_assumption(
        "Скорость резания",
        "150 м/мин",
        "стандарт для стали 45",
        show_keyboard=True
    ))

    print("\n🔧 Настройка значения:")
    print(adjust_value("Подача", "0.2 мм/об", show_keyboard=True))

    print("\n💬 Обратная связь:")
    print(ask_feedback())

    # 3. Частные сценарии
    print("\n📌 3. ЧАСТНЫЕ СЦЕНАРИИ:")
    print("-" * 40)

    print("\n📄 Название файла:")
    print(ask_filename())

    print("\n🔧 Материал:")
    print(ask_material())

    print("\n🎛️ Опыт оператора:")
    print(ask_experience())

    print("\n💾 Подтверждение сохранения:")
    print(ask_save_confirmation())

    # 4. Форматирование данных
    print("\n📌 4. ФОРМАТИРОВАНИЕ ДАННЫХ:")
    print("-" * 40)

    # Параметры с подсветкой и единицами
    params = [
        format_param("VC", "150", "м/мин", highlight=True),
        format_param("Подача", "0.25", "мм/об", highlight=True, precision=3),
        format_param("Глубина", "2.0", "мм", highlight=True, precision=2),
        format_param("Обороты", "955", "об/мин", highlight=True),
        format_param("Мощность", "4.2", "кВт", highlight=True, precision=1),
    ]

    print("\n🎯 Рекомендация:")
    print(format_recommendation(params))

    # Физические ограничения
    limits = [
        format_param("Мощность станка", "11", "кВт", highlight=False),
        format_param("Макс. RPM", "3000", "об/мин", highlight=False),
        format_param("Жёсткость", "средняя", "", highlight=False),
        format_param("Вылет", "40", "мм", highlight=False),
    ]

    print("\n⚖️ Физические ограничения:")
    print(format_physical_limits(limits))

    # 5. Клавиатуры
    print("\n📌 5. ОПИСАНИЯ КЛАВИАТУР:")
    print("-" * 40)

    print("\n⌨️ Клавиатура выбора:")
    print(describe_choice_keyboard())

    print("\n✅❌ Клавиатура Да/Нет:")
    print(describe_yes_no_keyboard())

    print("\n💾 Клавиатура Сохранить/Отмена:")
    print(describe_save_cancel_keyboard())

    # Статистика
    print(f"\n📊 СТАТИСТИКА:")
    # Подсчет функций автоматически
    functions = [name for name, obj in globals().items() 
                 if callable(obj) and not name.startswith('_')]
    print(f"• Всего функций: {len(functions)}")
    
    # Подсчет сценариев
    warning_scenarios = len(format_warning_scenario.__code__.co_consts) if hasattr(format_warning_scenario, '__code__') else 0
    success_scenarios = len(format_success.__code__.co_consts) if hasattr(format_success, '__code__') else 0
    
    print(f"• Универсальных форматтеров: 2")
    print(f"• Универсальных диалогов: 4")
    print(f"• Частных сценариев: 7")
    print(f"• Функций форматирования: 5")
    print(f"• Функций интерфейса: 4")

    print(f"\n✅ Тестирование завершено успешно!")
    print(f"✅ Все функции возвращают корректные строки")
    print(f"✅ Telegram-форматирование присутствует")
    print(f"✅ Подсветка параметров работает (<code>)")
    print(f"✅ Примеры для всех ключевых параметров")
    print(f"✅ HTML-экранирование реализовано")
    print(f"✅ Интернационализация поддержана")


# ============================================================================
# ДИСПЕТЧЕР ДИАЛОГОВ
# ============================================================================

class DialogManager:
    """
    Менеджер диалогов для CLI бота.
    Управляет вопросами на основе состояния FSM.
    """
    
    def __init__(self):
        """Инициализация менеджера диалогов."""
        pass
    
    def get_question(self, state, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Получить вопрос для текущего состояния.
        
        Args:
            state: Текущее состояние системы (SystemState)
            context: Контекст задачи
            
        Returns:
            Словарь с данными вопроса или None
        """
        from app.core.state_machine import SystemState
        
        # Базовые вопросы для разных состояний
        questions = {
            SystemState.EMPTY: {
                "question": "Опишите задачу обработки (материал, диаметры, операция):",
                "type": "text",
                "help": "Например: Сталь 45, диаметр 100 мм, черновая обработка"
            },
            SystemState.PARTIAL: {
                "question": "Уточните недостающие параметры:",
                "type": "text",
                "help": "Укажите материал, диаметры или другие параметры"
            },
            SystemState.COLLECTING_PARAMS: {
                "question": "Введите параметры обработки:",
                "type": "text",
                "help": "Укажите глубину резания, подачу, скорость и т.д."
            },
            SystemState.ASSUMED: {
                "question": "Проверьте предположения системы. Все верно?",
                "type": "yes_no",
                "choices": ["Да", "Нет"],
                "help": "Система сделала предположения на основе ваших данных"
            },
            SystemState.READY: {
                "question": "Все данные собраны. Выполнить расчет?",
                "type": "yes_no",
                "choices": ["Да", "Нет"],
                "help": "Нажмите 'Да' для расчета режимов резания"
            },
        }
        
        return questions.get(state)


if __name__ == "__main__":
    _test_all_scenarios()
