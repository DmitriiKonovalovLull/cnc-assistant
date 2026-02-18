"""
StandardResolver - резолвер стандартов с fallback стратегиями.
Архитектура: локальная база -> кэш -> веб-поиск -> ручной ввод
"""

import logging
from typing import Dict, Optional, Any, List
from pathlib import Path

from standards.utils.standard_normalizer import (
    normalize_standard_text,
    parse_standard_designation,
    normalize_standard_number,
    get_search_variants
)

logger = logging.getLogger(__name__)


class StandardResolver:
    """
    Резолвер стандартов с многоуровневой стратегией поиска.
    
    Стратегии (в порядке приоритета):
    1. Локальная база данных (YAML файлы)
    2. Кэшированные данные
    3. Веб-поиск (если доступен)
    4. Fallback - предложение альтернатив пользователю
    """
    
    def __init__(
        self,
        local_db_service=None,
        downloader=None,
        web_search_service=None
    ):
        """
        Инициализация резолвера.
        
        Args:
            local_db_service: Сервис локальной базы стандартов (StandardService)
            downloader: Сервис скачивания стандартов (StandardDownloader)
            web_search_service: Сервис веб-поиска (InternetSearchService)
        """
        self.local_db = local_db_service
        self.downloader = downloader
        self.web_search = web_search_service
    
    def resolve(
        self,
        standard_type: str,
        standard_number: str,
        try_web_search: bool = True
    ) -> Dict[str, Any]:
        """
        Найти стандарт используя все доступные стратегии.
        
        Args:
            standard_type: Тип стандарта (ГОСТ, ОСТ, DIN, ISO)
            standard_number: Номер стандарта
            try_web_search: Пытаться ли искать в интернете
            
        Returns:
            Словарь с результатом поиска:
            {
                'found': bool,
                'source': str,  # 'local', 'cache', 'web', 'not_found'
                'data': Dict,  # Данные стандарта (если найдено)
                'variants': List[str],  # Варианты для поиска
                'suggestions': List[str]  # Предложения для пользователя
            }
        """
        # Нормализуем входные данные
        normalized_type = standard_type.upper().strip()
        if normalized_type == 'ОСТ':
            normalized_type = 'OST'
        
        normalized_number = normalize_standard_text(standard_number)
        
        # Получаем варианты для поиска
        search_variants = get_search_variants(normalized_type, normalized_number)
        logger.debug(f"Search variants for {standard_type} {standard_number}: {search_variants}")
        
        # ========================================================================
        # СТРАТЕГИЯ 1: Локальная база данных
        # ========================================================================
        if self.local_db:
            for variant in search_variants:
                # Извлекаем тип и номер из варианта
                parts = variant.split('_', 1)
                if len(parts) == 2:
                    var_type, var_number = parts
                    result = self.local_db.find_standard(var_type, var_number)
                    if result:
                        logger.info(f"✅ Found in local DB: {variant}")
                        return {
                            'found': True,
                            'source': 'local',
                            'data': result,
                            'variants': search_variants,
                            'standard_id': variant
                        }
        
        # ========================================================================
        # СТРАТЕГИЯ 2: Кэшированные данные (если есть)
        # ========================================================================
        # TODO: Реализовать кэш стандартов
        
        # ========================================================================
        # СТРАТЕГИЯ 3: Веб-поиск (если разрешен и доступен)
        # ========================================================================
        if try_web_search and self.web_search:
            try:
                # Парсим обозначение для правильного поиска
                parsed = parse_standard_designation(f"{normalized_type} {normalized_number}")
                if parsed:
                    search_result = self.web_search.search_standard_info(
                        parsed['type'],
                        parsed.get('full_number', normalized_number)
                    )
                    if search_result and search_result.get('success'):
                        logger.info(f"✅ Found via web search: {standard_type} {standard_number}")
                        return {
                            'found': True,
                            'source': 'web',
                            'data': search_result.get('data'),
                            'variants': search_variants,
                            'message': search_result.get('message')
                        }
            except Exception as e:
                logger.warning(f"Web search failed: {e}")
        
        # ========================================================================
        # СТРАТЕГИЯ 4: Fallback - стандарт не найден
        # ========================================================================
        logger.info(f"❌ Standard not found: {standard_type} {standard_number}")
        
        # Генерируем предложения для пользователя
        suggestions = self._generate_suggestions(normalized_type, normalized_number, search_variants)
        
        return {
            'found': False,
            'source': 'not_found',
            'data': None,
            'variants': search_variants,
            'suggestions': suggestions,
            'message': self._format_not_found_message(normalized_type, normalized_number, suggestions)
        }
    
    def _generate_suggestions(
        self,
        standard_type: str,
        standard_number: str,
        search_variants: List[str]
    ) -> List[str]:
        """
        Сгенерировать предложения для пользователя когда стандарт не найден.
        
        Args:
            standard_type: Тип стандарта
            standard_number: Номер стандарта
            search_variants: Варианты поиска
            
        Returns:
            Список предложений
        """
        suggestions = []
        
        # Проверяем, может быть опечатка в номере
        parsed = parse_standard_designation(f"{standard_type} {standard_number}")
        if parsed:
            # Для ОСТ проверяем известные номера
            if standard_type == 'OST':
                # Известные ОСТ номера из стандартных классов
                known_ost_numbers = ['33056', '33057', '33058', '33059', '33060']
                number = parsed.get('number', '')
                if number not in known_ost_numbers:
                    suggestions.append(
                        f"⚠️ Проверьте номер стандарта. Возможно опечатка?\n"
                        f"Известные ОСТ: {', '.join(known_ost_numbers)}"
                    )
        
        return suggestions
    
    def _format_not_found_message(
        self,
        standard_type: str,
        standard_number: str,
        suggestions: List[str]
    ) -> str:
        """
        Форматировать сообщение когда стандарт не найден.
        
        Args:
            standard_type: Тип стандарта
            standard_number: Номер стандарта
            suggestions: Предложения для пользователя
            
        Returns:
            Отформатированное сообщение
        """
        lines = [
            f"❌ <b>Стандарт {standard_type} {standard_number} не найден</b>\n",
            "",
            "🔍 <b>Попытка поиска:</b>",
            "• Локальная база данных",
            "• Кэшированные данные",
        ]
        
        if self.web_search:
            lines.append("• Внешние источники")
        
        lines.append("")
        lines.append("💡 <b>Что можно сделать:</b>")
        lines.append("1. Загрузить файл стандарта (PDF)")
        lines.append("2. Ввести параметры детали вручную")
        lines.append("3. Продолжить без стандарта")
        
        if suggestions:
            lines.append("")
            lines.append("\n".join(suggestions))
        
        return "\n".join(lines)
