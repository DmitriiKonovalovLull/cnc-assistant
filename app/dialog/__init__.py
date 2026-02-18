"""
Dialog system - система обработки диалогов.
Строгая архитектура с State Machine и rule-based intent detection.
"""

from app.dialog.message_processor import MessageProcessor
from app.dialog.state_machine import StateMachine
from app.dialog.intent_detector import IntentDetector
from app.dialog.context_manager import ContextManager
from app.dialog.validators import Validator
from app.dialog.constants import DialogState, Intent

__all__ = [
    'MessageProcessor',
    'StateMachine',
    'IntentDetector',
    'ContextManager',
    'Validator',
    'DialogState',
    'Intent',
]
