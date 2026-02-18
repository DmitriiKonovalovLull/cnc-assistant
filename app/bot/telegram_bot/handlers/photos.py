"""
Обработчики фотографий (инструменты, спектры вибрации).
"""

from aiogram import Dispatcher, F
from aiogram import types
from aiogram.fsm.context import FSMContext

from app.bot.telegram_bot.main import image_parser, bot, handler, VibrationStates
from app.bot.telegram_bot.utils import get_user_context, _parse_modes_from_caption
from app.bot.telegram_bot.keyboards import create_main_nav_keyboard
from app.bot.context_manager import metrics
from app.bot.telegram_bot.main import rate_limiter
from app.core.context import DataSource
import time


def register_photo_handlers(dp: Dispatcher):
    """Зарегистрировать обработчики фото."""
    dp.message.register(handle_photo, F.photo)


async def handle_photo(message: types.Message, state: FSMContext):
    """Обработка фотографий: инструмент или спектр вибрации (по состоянию)."""
    start_time = time.time()
    
    user_id = str(message.from_user.id)
    current_state = await state.get_state()
    
    # Rate limiting (используем async версию)
    if rate_limiter:
        is_allowed = await rate_limiter.is_allowed(user_id)
        if not is_allowed:
            remaining_time = await rate_limiter.get_remaining_time(user_id)
            await message.answer(
                f"⏳ <b>Слишком много сообщений</b>\n\n"
                f"Пожалуйста, подождите {int(remaining_time)} секунд перед отправкой следующего сообщения."
            )
            return
    
    # Обновляем метрики
    metrics.total_photos += 1
    
    # Если ожидаем фото спектра для анализа вибрации
    if current_state and "waiting_photo" in (current_state or ""):
        await handle_vibration_photo(message, state)
        return
    
    # Обработка фото инструмента
    await handle_tool_photo(message, state, user_id)
    
    # Обновляем метрики времени ответа
    response_time = time.time() - start_time
    metrics.add_response_time(response_time)


async def handle_vibration_photo(message: types.Message, state: FSMContext):
    """Обработка фото спектра вибрации."""
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        image_data = await bot.download_file(file.file_path)
        image_bytes = image_data.read()
    except Exception as e:
        from app.bot.telegram_bot.main import logger
        logger.warning(f"Download vibration photo failed: {e}")
        await message.answer("❌ Не удалось загрузить фото. Попробуйте ещё раз.")
        return

    if not image_parser or not image_parser.ocr_available:
        await state.clear()
        await message.answer(
            "⚠️ OCR не настроен. Установите Tesseract для распознавания спектра.",
            reply_markup=create_main_nav_keyboard(),
        )
        return

    try:
        from app.services.vibration_analyzer import (
            analyze_vibration_from_image,
            CurrentModes,
        )
        from app.bot.telegram_bot.main import get_session, DB_URL
        
        modes_dict = _parse_modes_from_caption(message.caption)
        current_modes = CurrentModes(
            rpm=modes_dict["rpm"],
            ap_mm=modes_dict["ap_mm"],
            feed_mm_rev=modes_dict["feed_mm_rev"],
            teeth_count=int(modes_dict["teeth_count"]) if modes_dict["teeth_count"] >= 1 else 1,
        )
        session = None
        try:
            session = get_session(DB_URL)
            result = analyze_vibration_from_image(
                image_bytes,
                current_modes,
                image_parser,
                tolerance=0.05,
                db_session=session,
            )
        finally:
            if session:
                try:
                    session.close()
                except Exception:
                    pass
    except Exception as e:
        from app.bot.telegram_bot.main import logger
        logger.exception("Vibration analysis failed")
        await state.clear()
        await message.answer(
            f"❌ Ошибка анализа: {e}",
            reply_markup=create_main_nav_keyboard(),
        )
        return

    await state.clear()
    if not result.success:
        await message.answer(
            f"❌ <b>Анализ вибрации</b>\n\n{result.error}\n\n"
            "💡 Убедитесь, что на фото виден спектр/FFT с подписью частоты (Hz). "
            "В подписи к фото можно указать режимы: <code>n=1200 ap=2 f=0.2 z=4</code>",
            reply_markup=create_main_nav_keyboard(),
        )
        return

    # Форматируем результат анализа
    lines = [
        "📈 <b>Анализ вибрации</b>",
        "",
        f"🔍 <b>Тип:</b> {result.problem_type_ru}",
        f"📊 Частота на спектре: <b>{result.f_measured_hz:.1f} Гц</b>",
        f"🔄 f_шпиндель = n/60 = <b>{result.f_spindle_hz:.1f} Гц</b>",
        f"🦷 f_зубовая = f_шп × z = <b>{result.f_tooth_hz:.1f} Гц</b>",
        "",
    ]
    if result.new_rpm is not None or result.new_ap_mm is not None or result.new_feed_mm_rev is not None:
        lines.append("📐 <b>Рекомендуемые режимы:</b>")
        if result.new_rpm is not None:
            lines.append(f"🔄 Обороты: <b>{result.new_rpm:.0f} об/мин</b>")
        if result.new_ap_mm is not None:
            lines.append(f"🔪 Глубина: <b>{result.new_ap_mm:.2f} мм</b>")
        if result.new_feed_mm_rev is not None:
            lines.append(f"📏 Подача: <b>{result.new_feed_mm_rev:.2f} мм/об</b>")
    
    await message.answer("\n".join(lines), reply_markup=create_main_nav_keyboard())


async def handle_tool_photo(message: types.Message, state: FSMContext, user_id: str):
    """Обработка фото инструмента."""
    from app.bot.telegram_bot.main import logger
    from app.bot.telegram_bot.utils import ensure_context_user_id
    from app.bot.telegram_bot.context_storage import save_context_safe
    
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        image_data = await bot.download_file(file.file_path)
        image_bytes = image_data.read()

        if not image_parser:
            await message.answer(
                "❌ OCR не настроен. Установите pytesseract и Pillow для распознавания фотографий."
            )
            return
        
        # Проверяем, что OCR доступен перед парсингом (graceful degradation)
        if not image_parser.ocr_available:
            await message.answer(
                "📸 <b>OCR временно недоступен</b>\n\n"
                "Пожалуйста, опишите инструмент текстом:\n"
                "• Тип инструмента (CNMG, WNMG...)\n"
                "• Производитель (Sandvik, Iscar...)\n"
                "• Радиус пластины (0.4, 0.8 мм)\n\n"
                "💡 <i>Или установите Tesseract OCR для распознавания фотографий.</i>"
            )
            return
        
        try:
            parse_result = image_parser.parse_tool_image(image_bytes)
        except Exception as ocr_error:
            logger.error(f"OCR error: {ocr_error}", exc_info=True)
            metrics.total_errors += 1
            
            if 'tesseract' in str(ocr_error).lower() or 'TesseractNotFoundError' in str(type(ocr_error)):
                await message.answer(
                    "❌ <b>Tesseract OCR не установлен</b>\n\n"
                    "Для распознавания фотографий установите Tesseract OCR:\n"
                    "• Windows: https://github.com/UB-Mannheim/tesseract/wiki\n"
                    "• Linux: sudo apt-get install tesseract-ocr\n\n"
                    "💡 <i>А пока опишите инструмент текстом.</i>"
                )
            else:
                await message.answer(
                    "⚠️ <b>Не удалось распознать фото</b>\n\n"
                    "Попробуйте сфотографировать чётче или опишите инструмент текстом."
                )
            return
        
        if not parse_result.get('success'):
            error_message = parse_result.get('error', 'Не удалось распознать инструмент на фотографии.')
            metrics.total_errors += 1
            
            if 'tesseract' in error_message.lower() or 'ocr' in error_message.lower():
                await message.answer(
                    "❌ <b>Tesseract OCR не установлен</b>\n\n"
                    "Для распознавания фотографий установите Tesseract OCR:\n"
                    "• Windows: https://github.com/UB-Mannheim/tesseract/wiki\n"
                    "• Linux: sudo apt-get install tesseract-ocr\n\n"
                    "💡 <i>А пока опишите инструмент текстом.</i>"
                )
            else:
                await message.answer(
                    f"⚠️ <b>Не удалось распознать фото</b>\n\n"
                    f"Попробуйте сфотографировать чётче или опишите инструмент текстом."
                )
            return
        
        # Успешное распознавание
        if parse_result.get('success'):
            # Сохраняем инструмент в БД
            tool_id = None
            if handler and handler.tool_saver:
                tool_id = handler.tool_saver.save_tool_from_image(parse_result)
            
            # Получаем контекст
            context = await get_user_context(user_id)
            
            # Название для отображения
            tool_name_recognized = parse_result.get('tool_name')
            if not tool_name_recognized:
                raw = (parse_result.get('extracted_text') or '').strip()
                first_line = next((ln.strip() for ln in raw.replace('\r', '\n').split('\n') if ln.strip()), '')
                if first_line:
                    tool_name_recognized = first_line[:60].strip() if len(first_line) > 60 else first_line
                else:
                    tool_name_recognized = raw[:60].strip() if raw else None
            if not tool_name_recognized:
                tool_name_recognized = 'Инструмент с фото'
            
            # Обновляем контекст
            context.set_field(
                'tool_name',
                tool_name_recognized,
                DataSource.USER,
                confidence=parse_result.get('confidence', 0.7),
                reasoning="Распознано с фотографии инструмента"
            )
            
            context.add_to_history('tool_saved', {
                'tool_name': tool_name_recognized,
                'tool_id': tool_id,
            })
            
            if parse_result.get('tool_type'):
                context.set_field(
                    'tool_type',
                    parse_result['tool_type'],
                    DataSource.USER,
                    confidence=parse_result.get('confidence', 0.7),
                    reasoning="Определено по ISO коду"
                )
            
            if parse_result.get('insert_material'):
                context.set_field(
                    'tool_material',
                    parse_result['insert_material'],
                    DataSource.USER,
                    confidence=parse_result.get('confidence', 0.7),
                    reasoning="Распознано с фотографии"
                )
            
            # Формируем ответ
            response_lines = []
            response_lines.append("✅ <b>Инструмент распознан!</b>")
            response_lines.append("")
            response_lines.append(f"📌 <b>Распознал номер/маркировку:</b> <code>{tool_name_recognized}</code>")
            response_lines.append("")
            
            if parse_result.get('tool_type'):
                response_lines.append(f"🔧 <b>Тип:</b> {parse_result['tool_type']}")
            
            if parse_result.get('manufacturer'):
                response_lines.append(f"🏭 <b>Производитель:</b> {parse_result['manufacturer']}")
            
            if parse_result.get('insert_material'):
                response_lines.append(f"💎 <b>Материал:</b> {parse_result['insert_material']}")
            
            response_lines.append("")
            response_lines.append("💾 <i>Записал в «Мои инструменты» — увидишь по кнопке ниже.</i>")
            if tool_id:
                response_lines.append(f"<i>В базе под ID: {tool_id}</i>")
            response_lines.append("")
            response_lines.append("💬 <b>Теперь опиши задачу обработки, и я учту этот инструмент.</b>")
            
            from app.bot.i18n import get_lang
            await message.answer(
                "\n".join(response_lines),
                reply_markup=create_main_nav_keyboard(lang=get_lang(context))
            )
            
            # Сохраняем контекст
            save_context_safe(context, user_id)
    
    except Exception as e:
        logger.error(f"Error handling photo: {e}", exc_info=True)
        metrics.total_errors += 1
        await message.answer(
            f"❌ <b>Ошибка обработки фотографии</b>\n\n"
            f"Попробуйте ещё раз или опишите инструмент текстом."
        )
