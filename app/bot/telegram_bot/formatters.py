"""
Форматирование сообщений для Telegram бота.
"""

from typing import Dict, Any, Optional
from app.core.context import Context
from app.bot.i18n import t, get_lang
from app.bot.telegram_bot.utils import ensure_context_user_id


def _format_tool_display(context: Context) -> Optional[str]:
    """Строка для отображения инструмента: имя или марка."""
    if context.tool_display_name and context.tool_name:
        return f"{context.tool_display_name} ({context.tool_name})"
    return context.tool_name or context.tool_display_name


def format_context_summary(context: Context) -> str:
    """Форматировать краткую сводку контекста."""
    lines = []
    
    if context.material:
        source_icon = "👤" if context.is_field_from_user('material') else "🤖"
        lines.append(f"{source_icon} Материал: <b>{context.material}</b>")
    
    if context.diameter_start and context.diameter_end:
        source_icon = "👤" if context.is_field_from_user('diameter_start') else "🤖"
        lines.append(f"{source_icon} Диаметры: <b>Ø{context.diameter_start} → Ø{context.diameter_end} мм</b>")
    
    if context.operation:
        source_icon = "👤" if context.is_field_from_user('operation') else "🤖"
        lines.append(f"{source_icon} Операция: <b>{context.operation}</b>")
    
    if context.mode:
        source_icon = "👤" if context.is_field_from_user('mode') else "🤖"
        lines.append(f"{source_icon} Режим: <b>{context.mode}</b>")
    
    if context.machine_type:
        source_icon = "👤" if context.is_field_from_user('machine_type') else "🤖"
        lines.append(f"{source_icon} Станок: <b>{context.machine_type}</b>")
    
    tool_str = _format_tool_display(context)
    if tool_str:
        lines.append(f"🔧 Инструмент: <b>{tool_str}</b>")
    
    if context.assumptions_made:
        lines.append(f"\n💡 <i>Я предположил: {', '.join(context.assumptions_made)}</i>")
    
    if context.overall_confidence > 0:
        confidence_pct = int(context.overall_confidence * 100)
        lines.append(f"🎯 <i>Уверенность: {confidence_pct}%</i>")
    
    return "\n".join(lines) if lines else "Пока нет данных..."


def format_recommendation(recommendation: Dict[str, Any], context: Context) -> str:
    """Форматировать рекомендацию в естественном виде (с учётом context.lang)."""
    lang = get_lang(context)
    lines = []
    lines.append(t('rec.title', lang=lang))
    lines.append("")
    vc = recommendation.get('vc_m_min') or recommendation.get('vc', 0)
    rpm = recommendation.get('rpm', 0)
    feed = recommendation.get('feed_mm_rev') or recommendation.get('feed', 0)
    ap = recommendation.get('ap_mm') or recommendation.get('ap', 0)
    power = recommendation.get('power_kw', 0)
    lines.append(t('rec.cutting_speed', lang=lang, vc=vc))
    lines.append(t('rec.rpm', lang=lang, rpm=rpm))
    lines.append(t('rec.feed', lang=lang, feed=feed))
    lines.append(t('rec.depth', lang=lang, ap=ap))
    if power > 0:
        lines.append(t('rec.power', lang=lang, power=power))
    context_data = recommendation.get('context', {})
    machinability = context_data.get('machinability')
    if machinability:
        lines.append("")
        lines.append(t('rec.machinability', lang=lang, machinability=machinability))
        if machinability >= 100:
            lines.append(t('rec.mach_very_easy', lang=lang))
        elif machinability >= 70:
            lines.append(t('rec.mach_good', lang=lang))
        elif machinability >= 40:
            lines.append(t('rec.mach_medium', lang=lang))
        else:
            lines.append(t('rec.mach_hard', lang=lang))
    
    rigidity = context_data.get('rigidity')
    if rigidity:
        ld_ratio = rigidity.get('ld_ratio')
        if ld_ratio:
            lines.append("")
            lines.append(t('rec.rigidity', lang=lang, ld_ratio=ld_ratio))
            if rigidity.get('adjusted'):
                k_v = rigidity.get('k_v', 1.0)
                k_f = rigidity.get('k_f', 1.0)
                k_ap = rigidity.get('k_ap', 1.0)
                lines.append(t('rec.modes_adjusted', lang=lang, k_v=k_v, k_f=k_f, k_ap=k_ap))
    
    sources = recommendation.get('sources')
    if sources:
        lines.append("")
        lines.append(t('rec.internet_used', lang=lang))
        lines.append(t('rec.sources', lang=lang, sources=', '.join(sources[:3])))
    
    return "\n".join(lines)


def format_clarification_request(context: Context, missing_fields: list) -> str:
    """Форматировать запрос на уточнение в естественном виде."""
    lines = []
    
    lines.append("🤔 <b>Нужно уточнить несколько моментов:</b>")
    lines.append("")
    
    if 'material' in missing_fields:
        lines.append("• <b>Из какого материала</b> заготовка? (сталь, алюминий, нержавейка...)")
    
    if 'diameter_start' in missing_fields or 'diameter_end' in missing_fields:
        lines.append("• <b>Какие диаметры?</b> (например: с Ø100 до Ø90)")
    
    if 'operation' in missing_fields:
        lines.append("• <b>Какая операция?</b> (черновая, чистовая...)")
    
    # Показываем что уже известно
    known = format_context_summary(context)
    if known and known != "Пока нет данных...":
        lines.append("")
        lines.append("<b>Что я уже знаю:</b>")
        lines.append(known)
    
    lines.append("")
    lines.append("💬 <i>Можете описать всё в одном сообщении, я пойму.</i>")
    
    return "\n".join(lines)
