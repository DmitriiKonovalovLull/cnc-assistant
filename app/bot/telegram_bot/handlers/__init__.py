"""
Обработчики сообщений, команд, фото и callbacks.
"""

from .commands import register_commands
from .messages import register_message_handlers
from .photos import register_photo_handlers
from .callbacks import register_callback_handlers

__all__ = [
    'register_commands',
    'register_message_handlers',
    'register_photo_handlers',
    'register_callback_handlers',
]
