"""
ГЛАВНЫЙ ОБРАБОТЧИК - оркестратор системы.
Связывает парсер, контекст, калькулятор, assumptions.
Решает: считать, уточнять, показывать результат.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from app.core.context import Context, DataSource
from app.core.parser import TextParser
from app.core.image_parser import ImageParser
from app.core.assumptions import AssumptionEngine
from app.core.calculator import PhysicsCalculator, CuttingParametersCalculator
from app.core.pass_strategy import PassStrategy
from app.core.validator import Validator
from app.core.intent_parser import IntentParser, Intent
from app.core.conversation_orchestrator import ConversationOrchestrator, ConversationMode
from app.services.knowledge_service import KnowledgeService
from app.services.standard_service import StandardService
from app.services.tool_saver import ToolSaver
from app.services.machine_saver import MachineSaver
from app.services.material_saver import MaterialSaver
from app.services.work_manager import WorkManager
from app.services.data_collector import DataCollector
from app.core.state_machine import StateMachine, SystemState

logger = logging.getLogger(__name__)


class MessageHandler:
    """
    Главный обработчик сообщений.
    Оркестрирует работу всех компонентов системы.
    """
    
    def __init__(
        self,
        knowledge_service: KnowledgeService,
        calculator: Optional[PhysicsCalculator] = None,
        pass_strategy: Optional[PassStrategy] = None,
        validator: Optional[Validator] = None,
        assumption_engine: Optional[AssumptionEngine] = None,
        db_session: Optional[Any] = None,
        tesseract_cmd: Optional[str] = None
    ):
        """
        Инициализация обработчика.
        
        Args:
            knowledge_service: Сервис знаний
            calculator: Калькулятор (опционально)
            pass_strategy: Стратегия проходов (опционально)
            validator: Валидатор (опционально)
            assumption_engine: Двигатель предположений (опционально)
            tesseract_cmd: Путь к Tesseract OCR (опционально, для распознавания фото)
        """
        self.knowledge_service = knowledge_service
        self.parser = TextParser()
        self.image_parser = ImageParser(tesseract_cmd=tesseract_cmd)
        self.assumption_engine = assumption_engine or AssumptionEngine(knowledge_service)
        self.intent_parser = IntentParser()  # Парсер интентов
        self.orchestrator = ConversationOrchestrator()  # Оркестратор диалога
        self.standard_service = StandardService()  # Сервис стандартов
        self.calculator = calculator
        self.pass_strategy = pass_strategy
        self.validator = validator
        self.tool_saver = ToolSaver(db_session) if db_session else None
        self.machine_saver = MachineSaver(db_session) if db_session else None
        self.material_saver = MaterialSaver(db_session) if db_session else None
        
        # Сервис поиска в интернете (опционально)
        try:
            from app.services.internet_search_service import InternetSearchService
            self.internet_search = InternetSearchService(knowledge_service)
        except ImportError:
            self.internet_search = None
            logger.warning("InternetSearchService not available")
        self.work_manager = WorkManager(db_session) if db_session else None
        self.data_collector = DataCollector(db_session) if db_session else None
        self.state_machine = StateMachine()
        self.fsm_active = False  # Флаг активности FSM
    
    async def process_message(
        self,
        user_text: Optional[str] = None,
        user_id: str = None,
        session_id: Optional[str] = None,
        existing_context: Optional[Context] = None,
        image_data: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """
        Обработать сообщение пользователя.
        
        Сначала определяет интент, затем решает что делать:
        - Если не инженерный интент - возвращает ответ без FSM
        - Если инженерный - активирует FSM и обрабатывает через него
        """
        """
        Обработать сообщение пользователя.
        
        Args:
            user_text: Текст сообщения
            user_id: ID пользователя
            session_id: ID сессии (опционально)
            existing_context: Существующий контекст (опционально)
            
        Returns:
            Словарь с результатом обработки
        """
        # 0. ОРКЕСТРАТОР - единый управляющий слой
        # Определяет режим работы и разрешает ли запускать FSM
        orchestrator_result = self.orchestrator.process_message(
            text=user_text,
            has_image=bool(image_data),
            user_id=user_id
        )
        
        # Получаем решение оркестратора
        mode = orchestrator_result.get('mode', ConversationMode.IDLE.value)
        action = orchestrator_result.get('action', 'unknown')
        fsm_allowed = orchestrator_result.get('fsm_enabled', False)
        
        logger.info(f"Orchestrator decision: mode={mode}, action={action}, fsm_enabled={fsm_allowed}")
        
        # Создаем или получаем контекст
        if existing_context:
            context = existing_context
            # ВАЖНО: Всегда обновляем user_id и session_id если они переданы
            if user_id:
                context.user_id = user_id
            if session_id:
                context.session_id = session_id
        else:
            context = Context()
            if user_id:
                context.user_id = user_id
            context.session_id = session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Ожидание подтверждения поиска стандарта ("да давай" после standard_not_found)
        if context.pending_standard_search and user_text:
            text_lower = user_text.strip().lower()
            affirmative = any(w in text_lower for w in ['да', 'давай', 'ок', 'ага', 'хочу', 'попробуй', 'yes', 'окей'])
            if affirmative:
                pending_std = context.pending_standard_search
                context.pending_standard_search = None
                if self.internet_search:
                    try:
                        parts = pending_std.split(None, 1)
                        stype = parts[0] if parts else 'ОСТ'
                        snum = parts[1] if len(parts) > 1 else ''
                        search_result = await self.internet_search.search_standard_info(stype, snum)
                        if search_result.get('success') and search_result.get('message'):
                            return {
                                'action': 'standard_search_result',
                                'message': (
                                    search_result['message'] + "\n\n"
                                    "💡 <i>Укажите параметры детали: диаметр/резьбу, длину, количество — и подготовлю технологию.</i>"
                                ),
                                'mode': 'project',
                                'fsm_enabled': True,
                                'context': context.to_dict()
                            }
                        else:
                            return {
                                'action': 'standard_search_result',
                                'message': (
                                    f"🔍 <b>По запросу {pending_std} ничего не найдено во внешних источниках.</b>\n\n"
                                    "💡 Укажите параметры детали вручную: диаметр/резьбу, длину, количество."
                                ),
                                'mode': 'project',
                                'fsm_enabled': True,
                                'context': context.to_dict()
                            }
                    except Exception as e:
                        logger.warning(f"Standard search failed: {e}", exc_info=True)
                        return {
                            'action': 'standard_search_result',
                            'message': (
                                f"⚠️ <b>Не удалось выполнить поиск по {pending_std}.</b>\n\n"
                                "💡 Укажите параметры детали вручную: диаметр/резьбу, длину, количество."
                            ),
                            'mode': 'project',
                            'fsm_enabled': True,
                            'context': context.to_dict()
                        }
                else:
                    return {
                        'action': 'standard_search_result',
                        'message': (
                            f"🔍 <b>Поиск временно недоступен.</b>\n\n"
                            f"💡 Укажите параметры детали вручную для {pending_std}: диаметр/резьбу, длину, количество."
                        ),
                        'mode': 'project',
                        'fsm_enabled': True,
                        'context': context.to_dict()
                    }
        
        # Обработка простых утвердительных ответов ("давай", "ок" и т.д.) когда контекст уже загружен
        # Это позволяет продолжить работу после загрузки работы или когда есть данные в контексте
        if user_text and not orchestrator_result.get('is_command'):
            text_lower = user_text.strip().lower()
            affirmative_words = ['давай', 'да', 'ок', 'ага', 'хочу', 'попробуй', 'yes', 'окей', 'начать', 'продолжить']
            is_affirmative = any(w == text_lower or text_lower.startswith(w + ' ') for w in affirmative_words)
            
            # Проверяем, есть ли данные в контексте (материал, диаметры, операция, стандарт)
            has_context_data = bool(
                context.material or 
                context.diameter_start or 
                context.diameter_end or 
                context.operation or
                context.standard_id or
                context.machine_type
            )
            
            # Если это простое утверждение и есть данные в контексте - активируем FSM
            if is_affirmative and has_context_data:
                logger.info(f"Affirmative response detected with context data, activating FSM")
                # Активируем FSM и переходим к обработке как инженерный запрос
                self.fsm_active = True
                # Определяем действие на основе состояния контекста
                action = self._determine_action(context)
                return await self._execute_action(action, context, user_text)
        
        # ВАЖНО: Парсим текст ПЕРЕД проверкой режима, чтобы извлечь данные
        # Парсер должен работать для ВСЕХ типов запросов (инженерных, проектных, команд)
        parsed_data = None
        if user_text:
            try:
                parsed_data = self.parser.parse(user_text)
                logger.debug(f"Parsed data: {parsed_data.parsed_fields if parsed_data else 'None'}")
                
                # Обновляем контекст извлеченными данными (для всех режимов)
                if parsed_data:
                    self._update_context_from_parsed(context, parsed_data)
            except Exception as e:
                logger.error(f"Error parsing text: {e}", exc_info=True)
                parsed_data = None
        
        # КРИТИЧНО: Если уже идет сбор параметров (стандарт задан или операции заданы) —
        # маршрутизируем в PROJECT MODE независимо от интента текущего сообщения.
        # Иначе "м6 длина 20 кол 50" после "ост" попадает в NOISE и получает "не понял".
        if (
            not orchestrator_result.get('is_command') and
            (context.standard_id or context.collecting_params or context.operation)
        ):
            # Продолжаем сбор параметров — standard_type/standard_number из текущего сообщения
            # (для "м6 длина 20" они будут None, для "ост 33057" — заданы)
            return await self._handle_project_mode(
                user_text or '',
                context,
                standard_type=orchestrator_result.get('standard_type'),
                standard_number=orchestrator_result.get('standard_number')
            )
        
        # Если это команда или не-инженерный запрос - обрабатываем отдельно
        if orchestrator_result.get('is_command') or mode not in [ConversationMode.ENGINEERING.value]:
            # FSM отключен для команд и не-инженерных запросов
            self.fsm_active = False
            
            # Обрабатываем через соответствующий обработчик
            if orchestrator_result.get('is_command'):
                # Команды обрабатываются в telegram_bot.py
                return {
                    'action': action,
                    'mode': mode,
                    'fsm_enabled': False,
                    'is_command': True,
                    'context': context.to_dict()
                }
            elif mode == ConversationMode.PROJECT.value:
                # PROJECT MODE - работа по ГОСТ/чертежу или технологический маршрут
                # Парсер уже вызван выше, данные уже в контексте
                
                # Проверяем тип действия
                if action == 'tech_process':
                    # Технологический маршрут (расточка, сверление, фрезерование)
                    operations = orchestrator_result.get('operations', [])
                    context.collecting_params = True
                    context.operation = ', '.join(operations) if operations else None
                    
                    # Парсим станок из текста если есть
                    if parsed_data and parsed_data.machine_type:
                        context.set_field(
                            'machine_type',
                            parsed_data.machine_type,
                            DataSource.USER,
                            confidence=1.0,
                            reasoning="Станок распознан из технологического маршрута"
                        )
                    
                    return {
                        'action': 'tech_process',
                        'message': (
                            f"✅ <b>Технологический маршрут распознан:</b>\n\n"
                            f"📋 <b>Операции:</b> {', '.join(operations)}\n"
                            f"{f'🏭 <b>Станок:</b> {context.machine_type}\n' if context.machine_type else ''}\n"
                            f"💬 <b>Укажите параметры:</b>\n"
                            f"• Материал заготовки\n"
                            f"• Диаметры и размеры\n"
                            f"• Количество деталей\n"
                        ),
                        'mode': 'project',
                        'fsm_enabled': True,
                        'context': context.to_dict()
                    }
                
                # Стандартная деталь (ГОСТ/ОСТ)
                standard_type = orchestrator_result.get('standard_type')
                standard_number = orchestrator_result.get('standard_number')
                
                # ВАЖНО: Если стандарт уже есть в контексте, но новый стандарт не распознан
                # значит это продолжение сбора параметров
                if context.standard_id and not standard_type:
                    # Стандарт уже был распознан - собираем параметры
                    return await self._handle_project_mode(
                        user_text or '', 
                        context,
                        standard_type=None,
                        standard_number=None
                    )
                else:
                    # Новый стандарт распознан или первый запрос
                    return await self._handle_project_mode(
                        user_text or '', 
                        context,
                        standard_type=standard_type,
                        standard_number=standard_number
                    )
            else:
                # Не-инженерные интенты
                intent = Intent(orchestrator_result.get('intent', 'noise'))
                intent_result = {
                    'intent': intent,
                    'confidence': orchestrator_result.get('confidence', 0.5)
                }
                return await self._handle_non_engineering_intent(
                    intent, intent_result, user_text or '', context
                )
        
        # Инженерный запрос - FSM разрешен оркестратором
        self.fsm_active = fsm_allowed
        
        # Контекст уже создан выше, user_id и session_id уже установлены
        
        # Парсер уже вызван выше для всех режимов, данные уже в контексте
        # parsed_data уже определен выше
        
        # 1. Обрабатываем изображение если есть (для всех режимов, где это уместно)
        if image_data:
            image_result = self.image_parser.parse_tool_image(image_data)
            if image_result.get('success'):
                # Сохраняем инструмент из изображения в БД
                if self.tool_saver:
                    tool_id = self.tool_saver.save_tool_from_image(image_result)
                    if tool_id:
                        context.add_to_history('tool_from_image', {
                            'tool_id': tool_id,
                            'tool_name': image_result.get('tool_name')
                        })
                
                # Обновляем контекст данными из изображения
                if image_result.get('tool_name'):
                    context.set_field(
                        'tool_name',
                        image_result['tool_name'],
                        DataSource.USER,
                        confidence=image_result.get('confidence', 0.7),
                        reasoning="Распознано с фотографии инструмента"
                    )
                
                if image_result.get('tool_type'):
                    context.set_field(
                        'tool_type',
                        image_result['tool_type'],
                        DataSource.USER,
                        confidence=image_result.get('confidence', 0.7),
                        reasoning="Определено по ISO коду с фотографии"
                    )
                
                if image_result.get('insert_material'):
                    context.set_field(
                        'tool_material',
                        image_result['insert_material'],
                        DataSource.USER,
                        confidence=image_result.get('confidence', 0.7),
                        reasoning="Распознано с фотографии"
                    )
        
        # Сохраняем неизвестные сущности в БД (для всех режимов, где есть parsed_data)
        if parsed_data:
            # 4.1. Сохраняем неизвестный станок если найден
            if parsed_data.machine_type and self.machine_saver:
                # Проверяем, известен ли станок
                machine_info = self.knowledge_service.find_machine(parsed_data.machine_type)
                
                if not machine_info:
                    # Проверяем, не является ли это просто типом (токарный ЧПУ) или реальным названием
                    known_types = ['токарный чпу', 'токарный ручной', 'фрезерный чпу', 'фрезерный ручной']
                    if parsed_data.machine_type.lower() not in known_types:
                        # Это неизвестный станок - сохраняем
                        machine_id = self.machine_saver.save_unknown_machine(
                            machine_name=parsed_data.machine_type,
                            machine_type=None,  # Будет определен автоматически
                            power_kw=parsed_data.machine_power,
                            max_rpm=getattr(parsed_data, "rpm", None),
                            manufacturer=None  # Будет определен автоматически
                        )
                        if machine_id:
                            context.add_to_history('machine_saved', {
                                'machine_id': machine_id,
                                'machine_name': parsed_data.machine_type
                            })
                            logger.info(f"Saved unknown machine: {parsed_data.machine_type}")
                            
                            # Пробуем найти информацию в интернете
                            if self.internet_search:
                                try:
                                    search_result = await self.internet_search.search_and_save_machine(
                                        parsed_data.machine_type
                                    )
                                    if search_result.get('success'):
                                        logger.info(f"Found machine info online: {search_result.get('data')}")
                                        context.add_to_history('machine_info_found', {
                                            'machine_name': parsed_data.machine_type,
                                            'sources': search_result.get('sources', [])
                                        })
                                except Exception as e:
                                    logger.debug(f"Internet search failed: {e}")
            
            # 4.2. Сохраняем неизвестный материал если найден
            if parsed_data.material and self.material_saver:
                # Проверяем, известен ли материал
                material_info = self.knowledge_service.find_material(parsed_data.material)
                
                if not material_info:
                    # Это неизвестный материал - сохраняем
                    material_id = self.material_saver.save_unknown_material(
                        material_name=parsed_data.material,
                        material_type=None  # Будет определен автоматически
                    )
                    if material_id:
                        context.add_to_history('material_saved', {
                            'material_id': material_id,
                            'material_name': parsed_data.material
                        })
                        logger.info(f"Saved unknown material: {parsed_data.material}")
            
            # 4.3. Сохраняем неизвестный инструмент если найден
            if parsed_data.tool_name and self.tool_saver:
                # Проверяем, известен ли инструмент
                tool_info = self.knowledge_service.find_tool(
                    parsed_data.tool_type or 'токарный проходной',
                    parsed_data.tool_material or 'твердый сплав'
                )
                
                if not tool_info:
                    # Сохраняем неизвестный инструмент
                    tool_id = self.tool_saver.save_unknown_tool(
                        tool_name=parsed_data.tool_name,
                        tool_type=parsed_data.tool_type,
                        insert_material=parsed_data.tool_material,
                        insert_grade=parsed_data.tool_grade,
                        insert_radius_mm=parsed_data.tool_radius,
                        manufacturer=parsed_data.tool_manufacturer
                    )
                    if tool_id:
                        context.add_to_history('tool_saved', {
                            'tool_id': tool_id,
                            'tool_name': parsed_data.tool_name
                        })
                        logger.info(f"Saved unknown tool: {parsed_data.tool_name}")
                        
                        # Пробуем найти информацию в интернете
                        if self.internet_search:
                            try:
                                search_result = await self.internet_search.search_and_save_tool(
                                    parsed_data.tool_name
                                )
                                if search_result.get('success'):
                                    logger.info(f"Found tool info online: {search_result.get('data')}")
                                    context.add_to_history('tool_info_found', {
                                        'tool_name': parsed_data.tool_name,
                                        'sources': search_result.get('sources', [])
                                    })
                            except Exception as e:
                                logger.debug(f"Internet search failed: {e}")
        
        # 5. Делаем предположения (ТОЛЬКО если FSM активен)
        if self.fsm_active:
            context = self.assumption_engine.make_assumptions(context)
        else:
            # FSM не активен - не делаем предположения автоматически
            logger.info("FSM disabled, skipping assumptions")
        
        # 6. Определяем, что делать дальше (ТОЛЬКО если FSM активен)
        if self.fsm_active:
            action = self._determine_action(context)
        else:
            # FSM не активен - возвращаем результат без обработки через FSM
            return {
                'action': 'chat_mode',
                'mode': 'chat',
                'fsm_enabled': False,
                'context': context.to_dict(),
                'message': 'FSM отключен, режим свободного диалога'
            }
        
        # 7. Выполняем действие
        result = await self._execute_action(action, context, user_text or "")
        
        # 8. Сохраняем контекст после всех изменений (если есть work_manager, он может сохранить)
        # Контекст уже обновлен через existing_context, но нужно убедиться что он сохранен
        # Это делается в telegram_bot.py после получения result
        
        return result
    
    async def _handle_non_engineering_intent(
        self,
        intent: Intent,
        intent_result: Dict[str, Any],
        user_text: str,
        context: Context
    ) -> Dict[str, Any]:
        """
        Обработать не-инженерные интенты (приветствие, мета-вопросы и т.д.).
        
        Args:
            intent: Определенный интент
            intent_result: Результат парсинга интента
            user_text: Текст пользователя
            context: Контекст
            
        Returns:
            Результат обработки
        """
        # Деактивируем FSM для не-инженерных запросов
        self.fsm_active = False
        
        if intent == Intent.GREETING:
            # Приветствие обрабатывается в telegram_bot.py
            return {
                'action': 'greeting',
                'message': None,  # Обработка в telegram_bot.py
                'context': context.to_dict()
            }
        
        elif intent == Intent.META_CAPABILITIES:
            # Проверяем, это вопрос о станках или общий вопрос о возможностях
            subtype = intent_result.get('subtype')
            if subtype == 'machine_query':
                # Вопрос о станках - возвращаем специальный action
                return {
                    'action': 'machine_query',
                    'message': None,  # Сообщение формируется в telegram_bot.py с кнопками
                    'context': context.to_dict()
                }
            
            # Общий вопрос о возможностях бота
            return {
                'action': 'meta_capabilities',
                'message': (
                    "🤖 <b>Я инженерный помощник для токарной и фрезерной обработки.</b>\n\n"
                    "💡 <b>Что я умею:</b>\n\n"
                    "• Подбирать режимы резания (обороты, подачи, глубины)\n"
                    "• Учитывать материал, диаметр и тип обработки\n"
                    "• Адаптироваться под уровень оператора\n"
                    "• Запоминать твои решения и улучшать рекомендации\n"
                    "• Распознавать инструменты с фотографий\n"
                    "• Сохранять работы для быстрого доступа\n\n"
                    "📝 <b>Как работать:</b>\n\n"
                    "Просто опиши задачу в любом порядке:\n"
                    "<i>\"Титан, токарный ЧПУ, снять с Ø200 до Ø50, черновая\"</i>\n\n"
                    "Или используй команды:\n"
                    "• <code>история</code> - показать историю и работы\n"
                    "• <code>мои работы</code> - список сохраненных работ\n"
                    "• <code>сохранить работу</code> - сохранить текущую задачу\n"
                    "• <code>помощь</code> - подробная инструкция\n\n"
                    "💬 <i>Хочешь рассчитать режим — просто напиши параметры.</i>"
                ),
                'context': context.to_dict()
            }
        
        elif intent == Intent.HELP:
            # Запрос помощи
            return {
                'action': 'help',
                'message': (
                    "📖 <b>Помощь по использованию бота</b>\n\n"
                    "🎯 <b>Основная функция:</b>\n"
                    "Подбор режимов резания для токарной и фрезерной обработки.\n\n"
                    "📝 <b>Как описать задачу:</b>\n\n"
                    "Опиши в любом порядке:\n"
                    "• Материал (сталь, алюминий, титан...)\n"
                    "• Диаметры (с Ø100 до Ø90)\n"
                    "• Тип обработки (черновая, чистовая)\n"
                    "• Станок (если известен)\n"
                    "• Инструмент (или отправь фото)\n\n"
                    "💡 <b>Примеры:</b>\n"
                    "<code>Титан, токарный ЧПУ, снять с Ø200 до Ø50</code>\n"
                    "<code>Сталь 45, черновая, Ø100→90</code>\n\n"
                    "🔧 <b>Команды:</b>\n"
                    "• <code>история</code> - история диалога и работы\n"
                    "• <code>мои работы</code> - список сохраненных работ\n"
                    "• <code>сохранить работу</code> - сохранить задачу\n"
                    "• <code>работа W001</code> - загрузить работу\n"
                    "• <code>что ты можешь</code> - описание возможностей\n\n"
                    "💬 <i>Просто опиши задачу — я пойму.</i>"
                ),
                'context': context.to_dict()
            }
        
        elif intent == Intent.NOISE:
            # Шум — пробуем поиск в интернете перед ответом «не понял»
            if self.internet_search and user_text and len(user_text.strip()) >= 2:
                try:
                    search_result = await self.internet_search.search_unknown_query(user_text.strip())
                    if search_result.get('success') and search_result.get('message'):
                        return {
                            'action': 'internet_search_result',
                            'message': (
                                search_result['message'] + "\n\n"
                                "💡 <i>Опиши задачу подробнее, и я подберу режимы резания.</i>"
                            ),
                            'context': context.to_dict()
                        }
                except Exception as e:
                    logger.debug(f"Internet search on unknown query failed: {e}")
            
            # Поиск не помог — вежливо уточняем
            unknown_count = sum(1 for item in context.dialog_history[-3:] if item.get('event') == 'unknown_intent')
            
            if unknown_count >= 2:
                return {
                    'action': 'noise_fallback',
                    'message': (
                        "🤔 <b>Не совсем понял ваш запрос.</b>\n\n"
                        "💬 <b>Я могу помочь с:</b>\n\n"
                        "1️⃣ <b>Рассчитать режимы резания</b>\n"
                        "   (опиши задачу: материал, диаметры, тип обработки)\n\n"
                        "2️⃣ <b>Сделать деталь по ГОСТ/ОСТ</b>\n"
                        "   (напиши номер стандарта, например: ГОСТ 7798-30)\n\n"
                        "3️⃣ <b>Помочь с технологией</b>\n"
                        "   (задай вопрос или опиши проблему)\n\n"
                        "💡 <i>Или просто опиши что нужно сделать, я пойму.</i>"
                    ),
                    'context': context.to_dict()
                }
            else:
                context.add_to_history('unknown_intent', {'text': user_text})
                return {
                    'action': 'noise',
                    'message': (
                        "🤔 <b>Не совсем понял ваш запрос.</b>\n\n"
                        "💬 <i>Вы можете:</i>\n"
                        "• Описать задачу обработки\n"
                        "• Указать ГОСТ/ОСТ для стандартной детали\n"
                        "• Написать \"что ты можешь\" для описания возможностей\n"
                        "• Написать \"помощь\" для инструкции\n\n"
                        "<i>Просто опишите что нужно, я пойму.</i>"
                    ),
                    'context': context.to_dict()
                }
        
        # Остальные интенты обрабатываются в telegram_bot.py
        return {
            'action': 'non_engineering',
            'intent': intent.value,
            'message': None,
            'context': context.to_dict()
        }
    
    async def _handle_project_mode(
        self,
        text: str,
        context: Context,
        standard_type: Optional[str] = None,
        standard_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Обработать запрос на работу по ГОСТ/чертежу (PROJECT MODE).
        
        ВАЖНО: Стандарт распознан → это уже STANDARD_PART сценарий.
        База данных опциональна - работаем даже если стандарта нет в базе.
        
        Args:
            text: Текст сообщения
            context: Контекст
            standard_type: Тип стандарта (ГОСТ, ОСТ, DIN, ISO)
            standard_number: Номер стандарта
            
        Returns:
            Результат обработки
        """
        from app.core.context import DataSource
        
        # КЛЮЧЕВАЯ ЛОГИКА: Если стандарт УЖЕ есть в контексте - собираем параметры
        existing_standard_id = context.standard_id
        if existing_standard_id and not standard_type:
            # Стандарт уже был распознан ранее - это продолжение сбора параметров
            context.collecting_params = True
            
            # Парсим текст для извлечения параметров
            parsed_data = self.parser.parse(text)
            if parsed_data:
                self._update_context_from_parsed(context, parsed_data)
            
            # Проверяем какие параметры собраны
            part_type = context.part_type
            collected_params = []
            missing_params = []
            
            if part_type == 'nut':
                # Для гаек нужны: резьба, количество, станок (опционально)
                if context.thread_size:
                    collected_params.append(f"Резьба: {context.thread_size}")
                else:
                    missing_params.append("размер резьбы")
                
                if context.quantity:
                    collected_params.append(f"Количество: {context.quantity} шт")
                else:
                    missing_params.append("количество")
            else:
                # Для болтов нужны: диаметр/резьба, длина, количество, станок (опционально)
                if context.thread_size or context.diameter_start:
                    if context.thread_size:
                        collected_params.append(f"Резьба/Диаметр: {context.thread_size}")
                    else:
                        collected_params.append(f"Диаметр: {context.diameter_start} мм")
                else:
                    missing_params.append("диаметр/резьбу")
                
                if context.length:
                    collected_params.append(f"Длина: {context.length} мм")
                else:
                    missing_params.append("длину")
                
                if context.quantity:
                    collected_params.append(f"Количество: {context.quantity} шт")
                else:
                    missing_params.append("количество")
            
            if context.machine_type:
                collected_params.append(f"Станок: {context.machine_type}")
            
            # Формируем ответ
            if collected_params:
                response_parts = [
                    f"✅ <b>Принято:</b>\n"
                ]
                
                # Формируем описание детали
                if part_type == 'nut':
                    part_desc = f"Гайка {context.thread_size or '?'}"
                else:
                    part_desc = f"Болт {context.thread_size or context.diameter_start or '?'}"
                    if context.length:
                        part_desc += f"×{context.length}"
                
                response_parts.append(f"• {part_desc}")
                response_parts.append("")
                response_parts.append("\n".join([f"• {p}" for p in collected_params]))
                
                if missing_params:
                    response_parts.append("")
                    response_parts.append(f"📋 <b>Осталось указать:</b> {', '.join(missing_params)}")
                else:
                    # Все параметры собраны - генерируем технологию изготовления
                    response_parts.append("")
                    response_parts.append("✅ <b>Все параметры собраны!</b>")
                    response_parts.append("")
                    
                    # Получаем информацию о стандарте для генерации технологии
                    standard_id = context.standard_id
                    if standard_id:
                        # Извлекаем тип и номер стандарта из ID
                        parts = standard_id.split('_', 1)
                        if len(parts) == 2:
                            standard_type = parts[0]
                            standard_number = parts[1]
                            standard_info = self.standard_service.get_standard_info(standard_type, standard_number)
                            
                            # Формируем контекст для генерации технологии
                            tech_context = {
                                'thread_size': context.thread_size,
                                'length': context.length,
                                'quantity': context.quantity,
                                'material': context.material,
                                'machine_type': context.machine_type,
                                'diameter_start': context.diameter_start,
                                'diameter_end': context.diameter_end
                            }
                            
                            # Генерируем технологию
                            technology = self.standard_service.generate_manufacturing_technology(standard_info, tech_context)
                            response_parts.append(technology)
                        else:
                            response_parts.append("🧠 <b>Готовлю технологию...</b>")
                    else:
                        response_parts.append("🧠 <b>Готовлю технологию...</b>")
                
                return {
                    'action': 'collecting_params',
                    'message': "\n".join(response_parts),
                    'mode': 'project',
                    'fsm_enabled': True,
                    'context': context.to_dict()
                }
            else:
                # Ничего не распознано - но в состоянии COLLECTING_PARAMS НЕ говорим "не понял"
                # Вместо этого показываем что приняли и просим уточнить конкретные параметры
                part_type = context.part_type or 'деталь'
                return {
                    'action': 'collecting_params',
                    'message': (
                        f"✅ <b>Продолжаем сбор параметров для {part_type}.</b>\n\n"
                        f"📋 <b>Укажите параметры:</b>\n"
                        f"{'• Размер резьбы (M6, M12 и т.д.)\n' if part_type == 'nut' else '• Диаметр/резьбу (M6, M12 или Ø12)\n'}"
                        f"{'' if part_type == 'nut' else '• Длину (в мм)\n'}"
                        f"• Количество (например: 100 шт или кол 50)\n"
                        f"• Станок (опционально)\n\n"
                        f"💡 <i>Можно указать всё одним сообщением, например:</i>\n"
                        f"<code>м6 длина 20 кол 50</code>"
                    ),
                    'mode': 'project',
                    'fsm_enabled': True,
                    'context': context.to_dict()
                }
        
        # Если стандарт распознан (даже без номера) - это STANDARD_PART сценарий
        if standard_type:
            # Получаем полную информацию о стандарте (из базы ИЛИ из классов/шаблонов)
            standard_info = self.standard_service.get_standard_info(standard_type, standard_number or '')
            
            # ВАЖНО: Честно проверяем наличие стандарта в базе
            in_database = standard_info.get('in_database', False)
            standard_data = standard_info.get('standard_data')
            
            # Если стандарта НЕТ в базе - честно об этом говорим
            if not in_database and standard_number:
                # Проверяем есть ли хотя бы класс стандарта
                part_class = standard_info.get('part_class', {})
                part_type = part_class.get('type')
                
                if not part_type:
                    # Стандарт не найден — предлагаем поиск и сохраняем ожидание подтверждения
                    context.pending_standard_search = f"{standard_type} {standard_number}"
                    return {
                        'action': 'standard_not_found',
                        'message': (
                            f"❌ <b>Стандарт {standard_type} {standard_number} отсутствует в базе данных.</b>\n\n"
                            f"🔎 Хотите, я попробую разобрать стандарт по внешнему источнику?\n"
                            f"Напишите <b>да</b> или <b>давай</b> — и я поищу в интернете.\n\n"
                            f"Или укажите параметры детали вручную."
                        ),
                        'mode': 'project',
                        'fsm_enabled': False,
                        'context': context.to_dict()
                    }
            
            # Сохраняем информацию о стандарте в контекст
            standard_id = standard_info.get('standard_id', f"{standard_type}_{standard_number or 'unknown'}")
            context.set_field(
                'standard_id',
                standard_id,
                DataSource.USER,
                confidence=1.0,
                reasoning=f"Стандарт распознан: {standard_type} {standard_number or 'без номера'}"
            )
            
            # Включаем режим сбора параметров
            context.collecting_params = True
            
            # Определяем тип детали из класса стандарта
            part_class = standard_info.get('part_class', {})
            part_type = part_class.get('type')
            part_name = part_class.get('name')
            
            if part_type:
                context.set_field(
                    'part_type',
                    part_type,
                    DataSource.USER,
                    confidence=0.95,
                    reasoning=f"Тип детали определен по классу стандарта"
                )
            
            # Материал из шаблона или базы данных
            template = standard_info.get('template', {})
            default_material = template.get('default_material')
            
            # Если есть данные из базы - используем их, иначе из шаблона
            standard_data = standard_info.get('standard_data')
            if standard_data:
                materials = self.standard_service.get_materials(standard_data)
                if materials:
                    context.set_field(
                        'material',
                        materials[0],
                        DataSource.USER,
                        confidence=0.9,
                        reasoning=f"Материал по стандарту {standard_type} {standard_number}"
                    )
            elif default_material:
                context.set_field(
                    'material',
                    default_material,
                    DataSource.USER,
                    confidence=0.8,
                    reasoning=f"Материал по умолчанию для типа детали"
                )
            
            # Форматируем информацию о стандарте
            standard_info_text = self.standard_service.format_standard_info(standard_info)
            
            # Формируем ответ в зависимости от типа детали
            standard_display = f"{standard_type} {standard_number}" if standard_number else standard_type
            part_type = part_class.get('type')
            
            # Для гаек - другой запрос параметров (без длины)
            if part_type == 'nut':
                prompt_text = (
                    f"👉 <b>Напиши:</b>\n"
                    f"• <b>Размер резьбы</b> (например: M12, M16)\n"
                    f"• <b>Количество</b> (1 шт / серия)\n"
                    f"• <b>Станок</b> (если известен)\n\n"
                    f"💡 <i>После этого я подготовлю технологический маршрут с режимами резания.</i>"
                )
            else:
                # Для болтов и других деталей - стандартный запрос
                prompt_text = (
                    f"👉 <b>Напиши:</b>\n"
                    f"• <b>Диаметр</b> (например: M12, Ø20)\n"
                    f"• <b>Длину</b> (например: 50 мм)\n"
                    f"• <b>Количество</b> (1 шт / серия)\n"
                    f"• <b>Станок</b> (если известен)\n\n"
                    f"💡 <i>После этого я подготовлю технологический маршрут с режимами резания.</i>"
                )
            
            return {
                'action': 'standard_part',
                'message': (
                    f"✅ <b>Отлично! Стандарт {standard_display} распознан.</b>\n\n"
                    f"{standard_info_text}\n\n"
                    f"📋 <b>Что именно будем делать?</b>\n\n"
                    f"{prompt_text}"
                ),
                'mode': 'project',
                'fsm_enabled': True,
                'standard_info': standard_info,
                'context': context.to_dict()
            }
        
        # PROJECT MODE без конкретного стандарта - общий запрос
        return {
            'action': 'project_mode',
            'message': (
                "✅ <b>Отлично! Работа по ГОСТ/ОСТ — давай оформим задачу правильно.</b>\n\n"
                "📋 <b>Мне нужно:</b>\n\n"
                "1️⃣ <b>Какой ГОСТ/ОСТ или номер чертежа?</b>\n"
                "   (например: ГОСТ 7798-30, ОСТ 33056-80)\n\n"
                "2️⃣ <b>Материал</b> (если не указан в стандарте)\n"
                "3️⃣ <b>Тип обработки</b> (токарная / фрезерная)\n"
                "4️⃣ <b>Количество</b> (1 шт / серия / партия)\n\n"
                "💡 <i>Можешь прислать текстом или фото чертежа.</i>\n\n"
                "📝 <i>После этого я подготовлю технологическую карту с режимами резания.</i>"
            ),
            'mode': 'project',
            'fsm_enabled': True,
            'context': context.to_dict()
        }
    
    def _update_context_from_parsed(self, context: Context, parsed_data) -> None:
        """Обновить контекст из распарсенных данных."""
        # Материал
        if parsed_data.material:
            context.set_field(
                'material',
                parsed_data.material,
                DataSource.USER,
                confidence=1.0,
                reasoning="Извлечено из текста пользователя"
            )
        
        # Операция
        if parsed_data.operation:
            context.set_field(
                'operation',
                parsed_data.operation,
                DataSource.USER,
                confidence=1.0,
                reasoning="Извлечено из текста пользователя"
            )
        
        # Режим
        if parsed_data.mode:
            context.set_field(
                'mode',
                parsed_data.mode,
                DataSource.USER,
                confidence=1.0,
                reasoning="Извлечено из текста пользователя"
            )
        
        # Геометрия
        if parsed_data.diameter_start:
            context.set_field(
                'diameter_start',
                parsed_data.diameter_start,
                DataSource.USER,
                confidence=1.0,
                reasoning="Извлечено из текста пользователя"
            )
        
        if parsed_data.diameter_end:
            context.set_field(
                'diameter_end',
                parsed_data.diameter_end,
                DataSource.USER,
                confidence=1.0,
                reasoning="Извлечено из текста пользователя"
            )
        
        if parsed_data.length:
            context.set_field(
                'length',
                parsed_data.length,
                DataSource.USER,
                confidence=1.0,
                reasoning="Извлечено из текста пользователя"
            )
        
        # Размер резьбы
        if parsed_data.thread_size:
            context.thread_size = parsed_data.thread_size
            context.set_field(
                'thread_size',
                parsed_data.thread_size,
                DataSource.USER,
                confidence=1.0,
                reasoning="Извлечено из текста пользователя"
            )
        
        # Количество деталей
        if parsed_data.quantity:
            context.quantity = parsed_data.quantity
            context.set_field(
                'quantity',
                parsed_data.quantity,
                DataSource.USER,
                confidence=1.0,
                reasoning="Извлечено из текста пользователя"
            )
        
        # Станок
        if parsed_data.machine_type:
            context.set_field(
                'machine_type',
                parsed_data.machine_type,
                DataSource.USER,
                confidence=1.0,
                reasoning="Извлечено из текста пользователя"
            )
        
        if parsed_data.machine_power:
            context.set_field(
                'machine_power',
                parsed_data.machine_power,
                DataSource.USER,
                confidence=1.0,
                reasoning="Извлечено из текста пользователя"
            )
        
        # Инструмент
        if parsed_data.tool_material:
            context.set_field(
                'tool_material',
                parsed_data.tool_material,
                DataSource.USER,
                confidence=1.0,
                reasoning="Извлечено из текста пользователя"
            )
        
        if parsed_data.tool_radius:
            context.set_field(
                'tool_radius',
                parsed_data.tool_radius,
                DataSource.USER,
                confidence=1.0,
                reasoning="Извлечено из текста пользователя"
            )
        
        if parsed_data.tool_overhang:
            context.set_field(
                'tool_overhang',
                parsed_data.tool_overhang,
                DataSource.USER,
                confidence=1.0,
                reasoning="Извлечено из текста пользователя"
            )
        
        if parsed_data.tool_diameter:
            context.set_field(
                'tool_diameter',
                parsed_data.tool_diameter,
                DataSource.USER,
                confidence=1.0,
                reasoning="Извлечено из текста пользователя"
            )
        
        if parsed_data.tool_name:
            context.set_field(
                'tool_name',
                parsed_data.tool_name,
                DataSource.USER,
                confidence=1.0,
                reasoning="Извлечено из текста пользователя"
            )
        
        if parsed_data.tool_manufacturer:
            context.set_field(
                'tool_manufacturer',
                parsed_data.tool_manufacturer,
                DataSource.USER,
                confidence=1.0,
                reasoning="Извлечено из текста пользователя"
            )
        
        if parsed_data.tool_grade:
            context.set_field(
                'tool_grade',
                parsed_data.tool_grade,
                DataSource.USER,
                confidence=1.0,
                reasoning="Извлечено из текста пользователя"
            )
        
        # Добавляем в историю
        context.add_to_history('user_message', {
            'text': parsed_data.to_dict(),
            'parsed_fields': parsed_data.parsed_fields
        })
    
    def _determine_action(self, context: Context) -> str:
        """
        Определить, что делать дальше.
        Использует машину состояний для определения действия.
        
        Returns:
            'calculate' - можно считать
            'clarify' - нужно уточнить
            'show_result' - показать результат
            'collecting_params' - собираем параметры (стандарт/операции заданы)
        """
        # Используем машину состояний
        state = self.state_machine.determine_state(context)
        self.state_machine.current_state = state
        
        # КРИТИЧЕСКОЕ ПРАВИЛО: Если идет сбор параметров - НЕ возвращаем 'clarify'
        if state == SystemState.COLLECTING_PARAMS:
            # В состоянии сбора параметров - продолжаем собирать, не уточняем
            return 'collecting_params'
        
        # Определяем действие на основе состояния
        if state == SystemState.READY or state == SystemState.ASSUMED:
            return 'calculate'
        elif state == SystemState.CALCULATED:
            return 'show_result'
        elif state == SystemState.FEEDBACK:
            return 'feedback'
        else:
            # EMPTY или PARTIAL - нужно уточнить
            return 'clarify'
    
    async def _execute_action(
        self,
        action: str,
        context: Context,
        user_text: str
    ) -> Dict[str, Any]:
        """Выполнить действие."""
        if action == 'clarify':
            return await self._handle_clarify(context)
        elif action == 'calculate':
            return await self._handle_calculate(context)
        else:
            return {
                'action': 'unknown',
                'message': 'Неизвестное действие',
                'context': context.to_dict()
            }
    
    async def _handle_clarify(self, context: Context) -> Dict[str, Any]:
        """Обработать запрос на уточнение."""
        required_fields = ['material', 'diameter_start', 'diameter_end']
        missing = context.get_missing_fields(required_fields)
        
        # Проверяем, загружена ли работа (по session_id)
        is_loaded_work = context.session_id and context.session_id.startswith('work_')
        
        # Формируем сообщение с запросом недостающих данных
        messages = []
        
        # Показываем что уже известно
        known_info = []
        if context.material:
            known_info.append(f"Материал: {context.material}")
        if context.diameter_start:
            known_info.append(f"Начальный диаметр: Ø{context.diameter_start} мм")
        if context.diameter_end:
            known_info.append(f"Конечный диаметр: Ø{context.diameter_end} мм")
        if context.operation:
            known_info.append(f"Операция: {context.operation}")
        if context.machine_type:
            known_info.append(f"Станок: {context.machine_type}")
        
        # Формируем приветственное сообщение
        if is_loaded_work and known_info:
            messages.append("✅ <b>Продолжаем работу с загруженной задачей.</b>\n")
        elif is_loaded_work:
            messages.append("📋 <b>Работа загружена, но данных пока нет.</b>\n")
        else:
            messages.append("💬 <b>Чтобы рассчитать режимы резания, мне нужны:</b>\n")
        
        if known_info:
            messages.append("\n📌 <b>Уже известно:</b>")
            messages.extend([f"• {info}" for info in known_info])
            messages.append("")
        
        if missing:
            messages.append("📋 <b>Нужно указать:</b>")
            if 'material' in missing:
                messages.append("• Материал заготовки (сталь, алюминий, титан, нержавейка...)")
            if 'diameter_start' in missing or 'diameter_end' in missing:
                messages.append("• Диаметры (например: с Ø100 до Ø90)")
            messages.append("")
            messages.append("💡 <i>Просто опишите задачу в любом порядке, я пойму.</i>")
        else:
            messages.append("💡 <i>Опишите что нужно сделать, и я подберу режимы резания.</i>")
        
        return {
            'action': 'clarify',
            'message': '\n'.join(messages),
            'known_info': known_info,
            'missing_fields': missing,
            'context': context.to_dict()
        }
    
    async def _handle_calculate(self, context: Context) -> Dict[str, Any]:
        """Обработать расчет."""
        try:
            from app.services.recommendation import get_turning_recommendation
            
            # Определяем режим обработки
            mode = 'черновая'  # По умолчанию
            if context.mode:
                mode_lower = context.mode.lower()
                if 'чистов' in mode_lower:
                    mode = 'чистовая'
                elif 'получист' in mode_lower:
                    mode = 'получистовая'
                elif 'чернов' in mode_lower:
                    mode = 'черновая'
            
            # Определяем диаметр инструмента (если не указан, используем типичные значения)
            tool_diameter_mm = context.tool_diameter
            
            # 1. Если диаметр указан явно в контексте - используем его
            if not tool_diameter_mm:
                # 2. Из названия инструмента (пытаемся извлечь размер державки)
                if context.tool_name:
                    import re
                    # Паттерны для токарных резцов: CNMG 120408 -> 12мм, WNMG 080408 -> 8мм
                    # Ищем первые две цифры после букв
                    match = re.search(r'[A-Z]+\s*(\d{2})', context.tool_name.upper())
                    if match:
                        size_code = int(match.group(1))
                        # Коды размеров: 08=8мм, 12=12мм, 16=16мм, 20=20мм, 25=25мм
                        if size_code in [8, 12, 16, 20, 25]:
                            tool_diameter_mm = float(size_code)
                        elif size_code < 20:
                            tool_diameter_mm = float(size_code)  # Для кодов 08-19
            
            # 3. Для фрезерования пытаемся определить из операции или контекста
            if not tool_diameter_mm:
                operation_lower = (context.operation or '').lower()
                if 'фрезер' in operation_lower or 'сверл' in operation_lower:
                    # Типичные диаметры фрез и сверл
                    tool_diameter_mm = 10.0  # Типичный диаметр фрезы
                else:
                    # Для токарки - типичный диаметр державки
                    tool_diameter_mm = 12.0  # Типичный диаметр державки токарного резца
            
            # Пытаемся найти актуальные данные в интернете для улучшения рекомендаций
            internet_data = None
            internet_sources = []
            
            if self.internet_search:
                try:
                    # 1. Поиск режимов резания для конкретной комбинации материал + операция
                    if context.material and context.operation:
                        search_result = await self.internet_search.search_operation_modes(
                            operation_type=context.operation or 'токарная',
                            material=context.material
                        )
                        
                        if search_result.get('success') and search_result.get('data'):
                            internet_data = search_result.get('data', {})
                            if search_result.get('sources'):
                                internet_sources.extend(search_result.get('sources', []))
                            logger.info(f"Found internet operation data for recommendation")
                    
                    # 2. Поиск информации о станке (если неизвестен)
                    if context.machine_type and not self.knowledge_service.find_machine(context.machine_type):
                        machine_search = await self.internet_search.search_and_save_machine(context.machine_type)
                        if machine_search.get('success') and machine_search.get('data'):
                            # Обновляем информацию о станке в базе знаний
                            if machine_search.get('sources'):
                                internet_sources.extend(machine_search.get('sources', []))
                            logger.info(f"Found and saved machine info: {context.machine_type}")
                    
                    # 3. Поиск информации об инструменте (если указан и неизвестен)
                    if context.tool_name:
                        # Проверяем, есть ли инструмент в базе знаний
                        # find_tool требует tool_type и tool_material, поэтому просто проверяем через поиск
                        tool_found = False
                        if hasattr(self.knowledge_service, 'tools'):
                            # Ищем по имени инструмента в базе
                            tool_name_lower = context.tool_name.lower()
                            for tool_key, tool_data in self.knowledge_service.tools.items():
                                if tool_name_lower in tool_key or tool_key in tool_name_lower:
                                    tool_found = True
                                    break
                        
                        if not tool_found:
                            tool_search = await self.internet_search.search_and_save_tool(context.tool_name)
                            if tool_search.get('success') and tool_search.get('data'):
                                if tool_search.get('sources'):
                                    internet_sources.extend(tool_search.get('sources', []))
                                logger.info(f"Found and saved tool info: {context.tool_name}")
                    
                    # Добавляем источники в данные
                    if internet_data:
                        internet_data['sources'] = list(set(internet_sources))  # Убираем дубликаты
                        
                except Exception as e:
                    logger.debug(f"Internet search for recommendation failed: {e}")
            
            # Получаем рекомендацию
            recommendation = get_turning_recommendation(
                material=context.material or 'сталь',
                operation=context.operation or 'токарка',
                machine_type=context.machine_type or 'токарный ЧПУ',
                mode=mode,
                diameter_start_mm=context.diameter_start,
                diameter_end_mm=context.diameter_end,
                tool_material=context.tool_material or 'твердый сплав',
                knowledge_service=self.knowledge_service,
                tool_overhang_mm=context.tool_overhang,
                tool_diameter_mm=tool_diameter_mm,
                internet_data=internet_data  # Передаем данные из интернета
            )
            
            # Приводим формат к ожидаемому
            vc = recommendation.get('vc') or recommendation.get('vc_m_min', 0)
            rpm = recommendation.get('rpm', 0)
            feed = recommendation.get('feed') or recommendation.get('feed_mm_rev', 0)
            ap = recommendation.get('ap') or recommendation.get('ap_mm', 0)
            power = recommendation.get('power_kw', 0)
            
            # Нормализуем формат
            normalized_recommendation = {
                'vc': vc,
                'vc_m_min': vc,
                'rpm': rpm,
                'feed': feed,
                'feed_mm_rev': feed,
                'ap': ap,
                'ap_mm': ap,
                'power_kw': power,
                'warnings': recommendation.get('warnings', []),
                'physical_limits': recommendation.get('physical_limits', {}),
                'calculation_context': recommendation.get('calculation_context', {})
            }
            
            # Обновляем контекст рекомендациями
            context.recommended_vc = vc
            context.recommended_rpm = rpm
            context.recommended_feed = feed
            context.recommended_ap = ap
            context.recommended_power = power
            
            # Обновляем состояние машины состояний
            self.state_machine.transition_to_calculated()
            
            # Собираем данные для обучения (если доступен data_collector)
            if self.data_collector and context.user_id:
                self.data_collector.collect_interaction(
                    user_id=context.user_id,
                    context=context,
                    bot_recommendation=normalized_recommendation
                )
            
            # Добавляем в историю
            context.add_to_history('calculation', {
                'recommendation': normalized_recommendation,
                'state': self.state_machine.current_state.value
            })
            
            return {
                'action': 'calculate',
                'recommendation': normalized_recommendation,
                'context': context.to_dict(),
                'assumptions_made': context.assumptions_made,
                'defaults_used': context.defaults_used,
                'confidence': context.overall_confidence,
                'state': self.state_machine.current_state.value
            }
        
        except Exception as e:
            logger.error(f"Error in calculation: {e}", exc_info=True)
            return {
                'action': 'error',
                'message': f'Ошибка расчета: {str(e)}',
                'context': context.to_dict()
            }
