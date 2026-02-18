"""Обработчик расчёта шероховатости."""

import logging
from typing import Dict, Any

from app.core.session import Session

logger = logging.getLogger(__name__)


def handle_surface_calculation(text: str, session: Session, metadata: Dict, **kwargs) -> Dict[str, Any]:
    """Обработка расчёта шероховатости."""
    # TODO: Интегрировать с standards.calculations.surface_roughness
    return {
        'success': False,
        'message': 'Расчёт шероховатости в разработке',
        'session': session.to_dict()
    }
