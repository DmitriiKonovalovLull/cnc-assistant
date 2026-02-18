"""
Conversation Orchestrator - единый управляющий слой для всех модулей.
Координирует FSM, Intent Parser, OCR, Commands и режимы диалога.
"""

import logging
from enum import Enum
from typing import Dict, Any, Optional
from app.core.intent_parser import IntentParser, Intent

logger = logging.getLogger(__name__)


class ConversationMode(Enum):
    """Глобальные режимы диалога."""
    CHAT = "chat"  # Свободный диалог, знакомство, вопросы
    ENGINEERING = "engineering"  # Инженерные расчеты (FSM активен)
    PROJECT = "project"  # Работа по ГОСТ/чертежу (технологическое планирование)
    OCR_WAIT = "ocr_wait"  # Ожидание изображения инструмента
    ERROR_RECOVERY = "error_recovery"  # Восстановление после ошибки
    IDLE = "idle"  # Неактивное состояние


class CommandRouter:
    """
    Маршрутизатор жестких команд.
    Команды имеют приоритет над всеми остальными модулями.
    """
    
    # Жесткие команды (точное совпадение или начало строки)
    COMMANDS = {
        'помощь': 'help',
        'help': 'help',
        'что ты можешь': 'capabilities',
        'что ты умеешь': 'capabilities',
        'твои возможности': 'capabilities',
        'кто ты': 'capabilities',
        'что за бот': 'capabilities',
        'мои работы': 'works_list',
        'список работ': 'works_list',
        'работы': 'works_list',
        'мои инструменты': 'tools_list',
        'инструменты': 'tools_list',
        'список инструментов': 'tools_list',
        'история': 'history',
        'историю': 'history',
        'покажи историю': 'history',
        'сохранить работу': 'work_save',
        'добавить работу': 'work_save',
        'эквивалент': 'material_equivalent',
        'соответствие': 'material_equivalent',
        'маркировка': 'material_equivalent',
        'start': 'start',
        'начать': 'start',
    }
    
    @staticmethod
    def is_command(text: str) -> Optional[str]:
        """
        Проверить, является ли текст командой.
        
        Args:
            text: Текст сообщения
            
        Returns:
            Имя команды или None
        """
        if not text:
            return None
        
        text_lower = text.lower().strip()
        
        # Проверяем точное совпадение
        if text_lower in CommandRouter.COMMANDS:
            return CommandRouter.COMMANDS[text_lower]
        
        # Проверяем начало строки (для команд с параметрами)
        for cmd, cmd_name in CommandRouter.COMMANDS.items():
            if text_lower.startswith(cmd + ' ') or text_lower == cmd:
                return cmd_name
        
        # Команды вида "работа W001", "work W001", "загрузить работу 1", "исправить работу 1"
        if any(p in text_lower for p in ['работа w', 'work w', 'загрузить работу', 'исправить работу', 'открыть работу']):
            return 'work_load'
        if text_lower.startswith('работа ') or text_lower.startswith('work '):
            return 'work_load'
        
        if text_lower.startswith('удалить ') or text_lower.startswith('delete '):
            return 'work_delete'
        
        # Переименование работы: "переименовать W001 в ...", "назвать работу W001 ..."
        if any(p in text_lower for p in ['переименовать работ', 'назвать работ', 'переименовать w']):
            return 'work_rename'
        
        # Название инструмента: "назови инструмент ...", "имя инструмента ..."
        if any(p in text_lower for p in ['назови инструмент', 'назови этот инструмент', 'имя инструмента']):
            return 'tool_name_set'
        
        return None


class ConversationOrchestrator:
    """
    Оркестратор диалога - единый управляющий слой.
    Координирует все модули и определяет режим работы.
    """
    
    def __init__(self):
        """Инициализация оркестратора."""
        self.intent_parser = IntentParser()
        self.command_router = CommandRouter()
        self.current_mode = ConversationMode.IDLE
        self.fsm_enabled = False  # FSM отключен по умолчанию
    
    def process_message(
        self,
        text: Optional[str] = None,
        has_image: bool = False,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Обработать сообщение и определить режим работы.
        
        Args:
            text: Текст сообщения
            has_image: Есть ли изображение
            user_id: ID пользователя
            
        Returns:
            Словарь с решением оркестратора
        """
        # 1. ПРИОРИТЕТ 1: Жесткие команды (минуют все остальное)
        if text:
            command = self.command_router.is_command(text)
            if command:
                logger.info(f"Command detected: {command}")
                return self._handle_command(command, text, has_image)
        
        # 2. ПРИОРИТЕТ 2: Обработка изображений (только если есть фото)
        if has_image:
            logger.info("Image detected, switching to OCR_WAIT mode")
            self.current_mode = ConversationMode.OCR_WAIT
            return {
                'mode': ConversationMode.OCR_WAIT.value,
                'action': 'process_image',
                'fsm_enabled': False,
                'reason': 'Изображение получено'
            }
        
        # 3. ПРИОРИТЕТ 3: Определение интента
        if text:
            intent_result = self.intent_parser.parse(text)
            intent = intent_result['intent']
            confidence = intent_result['confidence']
            
            logger.info(f"Intent detected: {intent.value} (confidence: {confidence:.2f})")
            
            # 4. Определение режима на основе интента
            if intent == Intent.GREETING:
                self.current_mode = ConversationMode.CHAT
                self.fsm_enabled = False
                return {
                    'mode': ConversationMode.CHAT.value,
                    'action': 'greeting',
                    'fsm_enabled': False,
                    'intent': intent.value,
                    'reason': 'Приветствие'
                }
            
            elif intent == Intent.META_CAPABILITIES:
                self.current_mode = ConversationMode.CHAT
                self.fsm_enabled = False
                return {
                    'mode': ConversationMode.CHAT.value,
                    'action': 'meta_capabilities',
                    'fsm_enabled': False,
                    'intent': intent.value,
                    'reason': 'Вопрос о возможностях'
                }
            
            elif intent == Intent.HELP:
                self.current_mode = ConversationMode.CHAT
                self.fsm_enabled = False
                return {
                    'mode': ConversationMode.CHAT.value,
                    'action': 'help',
                    'fsm_enabled': False,
                    'intent': intent.value,
                    'reason': 'Запрос помощи'
                }
            
            elif intent == Intent.STANDARD_PART:
                # Стандартная деталь (ГОСТ/ОСТ/DIN/ISO) - отдельный режим
                self.current_mode = ConversationMode.PROJECT
                self.fsm_enabled = True  # FSM нужен для технологического сценария
                return {
                    'mode': ConversationMode.PROJECT.value,
                    'action': 'standard_part',
                    'fsm_enabled': True,
                    'intent': intent.value,
                    'confidence': confidence,
                    'standard_type': intent_result.get('standard_type'),
                    'standard_number': intent_result.get('standard_number'),
                    'reason': f'Стандартная деталь ({intent_result.get("standard_type")} {intent_result.get("standard_number")})'
                }
            
            elif intent == Intent.TECH_PROCESS:
                # Технологический маршрут (расточка, сверление, фрезерование)
                self.current_mode = ConversationMode.PROJECT
                self.fsm_enabled = True  # FSM нужен для технологического планирования
                return {
                    'mode': ConversationMode.PROJECT.value,
                    'action': 'tech_process',
                    'fsm_enabled': True,
                    'intent': intent.value,
                    'confidence': confidence,
                    'operations': intent_result.get('operations', []),
                    'reason': f'Технологический маршрут ({len(intent_result.get("operations", []))} операций)'
                }
            
            elif intent == Intent.ENGINEERING:
                # Проверяем, не является ли это запросом на работу по ГОСТ/чертежу
                if self.check_project_mode_keywords(text):
                    self.current_mode = ConversationMode.PROJECT
                    self.fsm_enabled = True  # PROJECT MODE использует FSM для технологического планирования
                    return {
                        'mode': ConversationMode.PROJECT.value,
                        'action': 'project_mode',
                        'fsm_enabled': True,
                        'intent': intent.value,
                        'confidence': confidence,
                        'reason': 'Работа по ГОСТ/чертежу'
                    }
                
                # Инженерный запрос - активируем FSM только если уверенность высокая
                if confidence >= 0.6:
                    self.current_mode = ConversationMode.ENGINEERING
                    self.fsm_enabled = True
                    return {
                        'mode': ConversationMode.ENGINEERING.value,
                        'action': 'engineering',
                        'fsm_enabled': True,
                        'intent': intent.value,
                        'confidence': confidence,
                        'reason': 'Инженерный запрос'
                    }
                else:
                    # Низкая уверенность - уточняем
                    self.current_mode = ConversationMode.CHAT
                    self.fsm_enabled = False
                    return {
                        'mode': ConversationMode.CHAT.value,
                        'action': 'clarify_intent',
                        'fsm_enabled': False,
                        'intent': intent.value,
                        'confidence': confidence,
                        'reason': 'Неопределенный запрос'
                    }
            
            elif intent == Intent.WORK_MANAGEMENT:
                self.current_mode = ConversationMode.CHAT
                self.fsm_enabled = False
                return {
                    'mode': ConversationMode.CHAT.value,
                    'action': 'work_management',
                    'fsm_enabled': False,
                    'intent': intent.value,
                    'reason': 'Работа с сохраненными работами'
                }
            
            elif intent == Intent.HISTORY:
                self.current_mode = ConversationMode.CHAT
                self.fsm_enabled = False
                return {
                    'mode': ConversationMode.CHAT.value,
                    'action': 'history',
                    'fsm_enabled': False,
                    'intent': intent.value,
                    'reason': 'Запрос истории'
                }
            
            elif intent == Intent.NOISE:
                self.current_mode = ConversationMode.CHAT
                self.fsm_enabled = False
                return {
                    'mode': ConversationMode.CHAT.value,
                    'action': 'noise',
                    'fsm_enabled': False,
                    'intent': intent.value,
                    'reason': 'Неразборчивое сообщение'
                }
        
        # 5. По умолчанию - режим CHAT
        self.current_mode = ConversationMode.CHAT
        self.fsm_enabled = False
        return {
            'mode': ConversationMode.CHAT.value,
            'action': 'unknown',
            'fsm_enabled': False,
            'reason': 'Неопределенное сообщение'
        }
    
    def _handle_command(
        self,
        command: str,
        text: str,
        has_image: bool
    ) -> Dict[str, Any]:
        """
        Обработать жесткую команду.
        
        Args:
            command: Имя команды
            text: Текст сообщения
            has_image: Есть ли изображение
            
        Returns:
            Решение оркестратора
        """
        # Команды всегда работают в режиме CHAT и отключают FSM
        self.current_mode = ConversationMode.CHAT
        self.fsm_enabled = False
        
        return {
            'mode': ConversationMode.CHAT.value,
            'action': command,
            'fsm_enabled': False,
            'is_command': True,
            'command': command,
            'reason': f'Команда: {command}'
        }
    
    def check_project_mode_keywords(self, text: str) -> bool:
        """
        Проверить, содержит ли текст ключевые слова для PROJECT MODE.
        
        Args:
            text: Текст сообщения
            
        Returns:
            True если это запрос на работу по ГОСТ/чертежу
        """
        if not text:
            return False
        
        text_lower = text.lower()
        
        project_keywords = [
            'гост', 'gost',
            'чертеж', 'чертёж', 'drawing',
            'деталь', 'заготовка',
            'партия', 'серия',
            'номер чертежа',
            'по госту',
            'сделать по',
            'работа по'
        ]
        
        return any(keyword in text_lower for keyword in project_keywords)
    
    def enable_fsm(self) -> None:
        """Включить FSM (только для инженерных запросов)."""
        self.fsm_enabled = True
        self.current_mode = ConversationMode.ENGINEERING
    
    def disable_fsm(self) -> None:
        """Отключить FSM."""
        self.fsm_enabled = False
        if self.current_mode == ConversationMode.ENGINEERING:
            self.current_mode = ConversationMode.IDLE
    
    def reset(self) -> None:
        """Сбросить состояние оркестратора."""
        self.current_mode = ConversationMode.IDLE
        self.fsm_enabled = False
