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
        db_session: Optional[Any] = None
    ):
        """
        Инициализация обработчика.
        
        Args:
            knowledge_service: Сервис знаний
            calculator: Калькулятор (опционально)
            pass_strategy: Стратегия проходов (опционально)
            validator: Валидатор (опционально)
            assumption_engine: Двигатель предположений (опционально)
        """
        self.knowledge_service = knowledge_service
        self.parser = TextParser()
        # ImageParser инициализируется без tesseract_cmd (использует системный PATH)
        # Если нужен кастомный путь, передайте его через параметр
        self.image_parser = ImageParser()
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
                # PROJECT MODE - работа по ГОСТ/чертежу
                # Парсер уже вызван выше, данные уже в контексте
                standard_type = orchestrator_result.get('standard_type')
                standard_number = orchestrator_result.get('standard_number')
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
                            manufacturer=None  # Будет определен автоматически
                        )
                        if machine_id:
                            context.add_to_history('machine_saved', {
                                'machine_id': machine_id,
                                'machine_name': parsed_data.machine_type
                            })
                            logger.info(f"Saved unknown machine: {parsed_data.machine_type}")
            
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
            # Вопрос о возможностях бота
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
            # Шум - вежливо уточняем с fallback меню
            # Проверяем, сколько раз подряд был UNKNOWN
            unknown_count = sum(1 for item in context.dialog_history[-3:] if item.get('event') == 'unknown_intent')
            
            if unknown_count >= 2:
                # Два раза подряд не поняли - показываем меню выбора
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
                # Первый раз не поняли - просто уточняем
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
        
        # Если стандарт распознан (даже без номера) - это STANDARD_PART сценарий
        if standard_type:
            # Получаем полную информацию о стандарте (из базы ИЛИ из классов/шаблонов)
            standard_info = self.standard_service.get_standard_info(standard_type, standard_number or '')
            
            # Сохраняем информацию о стандарте в контекст
            standard_id = standard_info.get('standard_id', f"{standard_type}_{standard_number or 'unknown'}")
            context.set_field(
                'standard_id',
                standard_id,
                DataSource.USER,
                confidence=1.0,
                reasoning=f"Стандарт распознан: {standard_type} {standard_number or 'без номера'}"
            )
            
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
        """
        # Используем машину состояний
        state = self.state_machine.determine_state(context)
        self.state_machine.current_state = state
        
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
        
        # Формируем сообщение с запросом недостающих данных
        messages = []
        
        if 'material' in missing:
            messages.append("Укажите материал заготовки (сталь, алюминий, нержавейка...)")
        
        if 'diameter_start' in missing or 'diameter_end' in missing:
            messages.append("Укажите диаметры (например: с Ø100 до Ø90)")
        
        # Показываем что уже известно
        known_info = []
        if context.material:
            known_info.append(f"Материал: {context.material}")
        if context.diameter_start:
            known_info.append(f"Начальный диаметр: Ø{context.diameter_start} мм")
        if context.diameter_end:
            known_info.append(f"Конечный диаметр: Ø{context.diameter_end} мм")
        
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
            
            # Получаем рекомендацию
            recommendation = get_turning_recommendation(
                material=context.material or 'сталь',
                operation=context.operation or 'токарка',
                machine_type=context.machine_type or 'токарный ЧПУ',
                mode=mode,
                diameter_start_mm=context.diameter_start,
                diameter_end_mm=context.diameter_end,
                tool_material=context.tool_material or 'твердый сплав'
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
