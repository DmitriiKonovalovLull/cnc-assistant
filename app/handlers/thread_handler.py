"""Обработчик расчёта резьбы."""

import logging
from typing import Dict, Any

from app.core.session import Session

logger = logging.getLogger(__name__)


def handle_thread_calculation(text: str, session: Session, metadata: Dict, **kwargs) -> Dict[str, Any]:
    """Обработка расчёта резьбы."""
    # TODO: Интегрировать с standards.calculations.thread_geometry
    return {
        'success': False,
        'message': 'Расчёт резьбы в разработке',
        'session': session.to_dict()
    }
