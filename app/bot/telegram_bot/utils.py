"""
Вспомогательные функции для Telegram бота.
"""

import re
import logging
from typing import Optional, Dict
from datetime import datetime

from app.core.context import Context
from app.bot.context_manager import (
    context_manager, file_storage, user_contexts
)

logger = logging.getLogger(__name__)


def ensure_context_user_id(context: Context, user_id: str) -> None:
    """
    Убедиться что user_id установлен в контексте перед сохранением.
    
    Args:
        context: Контекст для проверки
        user_id: ID пользователя для установки
    """
    if not context.user_id and user_id:
        context.user_id = user_id
    if not context.session_id:
        context.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


async def get_user_context(user_id: str) -> Context:
    """
    Получить контекст пользователя из любого хранилища.
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Контекст пользователя (создается если не существует)
    """
    context = None
    
    # Приоритет: context_manager > file_storage > context_repository > user_contexts
    if context_manager:
        context = context_manager.get(user_id)
    
    if not context and file_storage:
        context = file_storage.get(user_id)
        # Если загрузили из файла, сохраняем в context_manager
        if context and context_manager:
            context_manager.set(user_id, context)
    
    # Импортируем context_repository динамически чтобы избежать циклических зависимостей
    try:
        # Используем глобальную переменную из main если доступна
        import app.bot.telegram_bot.main as main_module
        context_repository = getattr(main_module, 'context_repository', None)
        if not context and context_repository:
            context = context_repository.get_context(user_id)
            # Если загрузили из репозитория, сохраняем в context_manager
            if context and context_manager:
                context_manager.set(user_id, context)
    except (ImportError, AttributeError):
        pass
    
    if not context:
        context = user_contexts.get(user_id)
    
    if not context:
        context = Context()
        context.user_id = user_id
        context.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        ensure_context_user_id(context, user_id)
    
    return context


def _extract_work_number(text: str) -> Optional[str]:
    """Мягкое распознавание номера работы: W001, работа 1, 1 работа, 1, раб 1, w1."""
    if not text or not text.strip():
        return None
    t = text.strip()
    low = t.lower()
    # Явный W + цифры (W001, w1, W12)
    m = re.search(r'\b(w\d+)\b', low, re.I)
    if m:
        num = m.group(1).upper()
        if num[1:].isdigit():
            return f"W{int(num[1:]):03d}" if len(num) <= 4 else f"W{num[1:]}"
    # "работа 1", "work 1", "работу 1", "работа W001"
    m = re.search(r'(?:работа|work|работ[уа])\s+(?:w)?(\d+)', low, re.I)
    if m:
        n = m.group(1)
        return f"W{int(n):03d}" if len(n) <= 3 else f"W{n}"
    # "1 работа", "1 work", "1 раб"
    m = re.search(r'(\d+)\s*(?:работ[ауи]?|work)', low, re.I)
    if m:
        n = m.group(1)
        return f"W{int(n):03d}" if len(n) <= 3 else f"W{n}"
    # Одиночное число в контексте выбора (короткое сообщение: "1", "2", "01")
    m = re.search(r'^(?:№\s*)?(\d+)\s*$', low)
    if m:
        n = m.group(1)
        return f"W{int(n):03d}" if len(n) <= 3 else f"W{n}"
    # (работа|w|№)? цифры — в любом месте для "загрузить работу 1", "открой 3"
    m = re.search(r'(?:работа|work|w|№)\s*(\d+)', low, re.I)
    if m:
        n = m.group(1)
        return f"W{int(n):03d}" if len(n) <= 3 else f"W{n}"
    return None


def _looks_like_experience_feedback(text: str) -> bool:
    """Проверить, похоже ли сообщение на ответ оператора с режимами (обороты, скорость, глубина, подача)."""
    if not text or not text.strip():
        return False
    t = text.strip().lower()
    # Есть числа и ключевые слова режимов
    has_digit = bool(re.search(r'\d+', t))
    patterns = [
        r'оборот', r'об/мин', r'rpm', r'vc\s*=', r'м/мин', r'скорость\s*(?:резания)?',
        r'подач', r'глубин', r'сьем', r'съём', r'съем', r'глубин', r'ap\s*=', r'feed\s*=',
        r'(\d+)\s*мм', r'около\s*\d+', r'максимум\s*\d+', r'даю\s+', r'ставлю\s+',
        r'работаю\s+на\s+\d+', r'применяю\s+\d+'
    ]
    return has_digit and any(re.search(p, t) for p in patterns)


def _extract_work_rename_params(text: str) -> Optional[tuple[str, str]]:
    """Извлечь (work_number, new_name) из текста: переименовать работу W001 в Втулка М12."""
    if not text or not text.strip():
        return None
    t = text.strip()
    # "переименовать работу W001 в Новое название", "назвать работу W001 Втулка"
    m = re.search(
        r'(?:переименовать|назвать)\s+работ[уа]?\s+(W\d+)\s+(?:в\s+)?(.+)',
        t, re.IGNORECASE | re.DOTALL
    )
    if m:
        num = m.group(1).upper()
        name = m.group(2).strip()
        if name:
            return (num, name)
    # "переименовать W001 в Название"
    m = re.search(r'переименовать\s+(W\d+)\s+(?:в\s+)?(.+)', t, re.IGNORECASE | re.DOTALL)
    if m:
        num = m.group(1).upper()
        name = m.group(2).strip()
        if name:
            return (num, name)
    return None


def _extract_tool_display_name(text: str) -> Optional[str]:
    """Извлечь имя инструмента из текста: назови инструмент Мой черновой."""
    if not text or not text.strip():
        return None
    t = text.strip()
    prefixes = [
        r'назови\s+(?:этот\s+)?инструмент\s+',
        r'имя\s+инструмента\s+',
        r'назови\s+инструмент\s+',
    ]
    for pat in prefixes:
        m = re.search(pat + r'(.+)', t, re.IGNORECASE | re.DOTALL)
        if m:
            name = m.group(1).strip()
            if name and len(name) < 100:
                return name
    return None


def _parse_modes_from_caption(caption: Optional[str]) -> Dict[str, float]:
    """Парсить режимы из подписи к фото: n=1200 ap=2 f=0.2 z=4."""
    out = {"rpm": 0.0, "ap_mm": 0.0, "feed_mm_rev": 0.0, "teeth_count": 0.0}
    if not caption:
        return out
    
    for pat, key in [
        (r"[nN]\s*[=:]\s*(\d+)", "rpm"),
        (r"[nN]\s+(\d+)", "rpm"),
        (r"[aA][pP]\s*[=:]\s*(\d+(?:[.,]\d+)?)", "ap_mm"),
        (r"[aA][pP]\s+(\d+(?:[.,]\d+)?)", "ap_mm"),
        (r"[fF]\s*[=:]\s*(\d+(?:[.,]\d+)?)", "feed_mm_rev"),
        (r"[fF]\s+(\d+(?:[.,]\d+)?)", "feed_mm_rev"),
        (r"[zZ]\s*[=:]\s*(\d+)", "teeth_count"),
        (r"[zZ]\s+(\d+)", "teeth_count"),
    ]:
        m = re.search(pat, caption)
        if m:
            try:
                val = float(m.group(1).replace(",", "."))
                if key == "teeth_count":
                    val = int(val)
                out[key] = val
            except ValueError:
                pass
    return out


def _collect_my_tools_from_context(context: Context) -> list:
    """Собрать список инструментов из истории диалога."""
    tools = []
    if not context or not context.dialog_history:
        return tools
    
    for entry in context.dialog_history:
        if entry.get('event') == 'tool_saved':
            tool_name = entry.get('data', {}).get('tool_name')
            if tool_name and tool_name not in tools:
                tools.append(tool_name)
    
    return tools
