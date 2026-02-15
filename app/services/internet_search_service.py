"""
СЕРВИС ПОИСКА В ИНТЕРНЕТЕ - автоматический поиск и сохранение информации.
Интегрирует BrowserParser с KnowledgeService для автоматического обогащения базы знаний.
"""

import logging
from typing import Dict, Any, Optional
import asyncio

from app.knowledge.internet_parser.browser_parser import BrowserParser
from app.services.knowledge_service import KnowledgeService

logger = logging.getLogger(__name__)


class InternetSearchService:
    """
    Сервис для автоматического поиска информации в интернете
    и сохранения найденных характеристик в базу знаний.
    """
    
    def __init__(self, knowledge_service: KnowledgeService):
        """
        Инициализация сервиса поиска.
        
        Args:
            knowledge_service: Сервис знаний для сохранения данных
        """
        self.knowledge_service = knowledge_service
        self.browser_parser = BrowserParser()
        self.search_enabled = True  # Можно отключить через конфиг
    
    async def search_and_save_tool(self, tool_name: str) -> Dict[str, Any]:
        """
        Найти информацию об инструменте в интернете и сохранить в базу знаний.
        
        Args:
            tool_name: Название инструмента
            
        Returns:
            Результат поиска и сохранения
        """
        if not self.search_enabled:
            return {'success': False, 'error': 'Internet search disabled'}
        
        try:
            # Ищем информацию в интернете
            search_result = await self.browser_parser.search_tool_info(tool_name)
            
            if search_result.get('success') and search_result.get('found_data'):
                found_data = search_result['found_data']
                
                # Сохраняем найденные данные в базу знаний
                # Здесь можно добавить сохранение в JSON файлы или БД
                logger.info(f"Found tool info for {tool_name}: {found_data}")
                
                return {
                    'success': True,
                    'tool_name': tool_name,
                    'data': found_data,
                    'sources': search_result.get('sources', [])
                }
            else:
                return {
                    'success': False,
                    'tool_name': tool_name,
                    'error': 'No data found'
                }
        
        except Exception as e:
            logger.error(f"Error searching tool: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def search_and_save_machine(self, machine_name: str) -> Dict[str, Any]:
        """
        Найти информацию о станке в интернете и сохранить в базу знаний.
        
        Args:
            machine_name: Название станка
            
        Returns:
            Результат поиска и сохранения
        """
        if not self.search_enabled:
            return {'success': False, 'error': 'Internet search disabled'}
        
        try:
            # Ищем информацию в интернете
            search_result = await self.browser_parser.search_machine_info(machine_name)
            
            if search_result.get('success') and search_result.get('found_data'):
                found_data = search_result['found_data']
                
                # Сохраняем найденные данные в базу знаний
                logger.info(f"Found machine info for {machine_name}: {found_data}")
                
                # Обновляем базу знаний
                await self._save_machine_to_kb(machine_name, found_data)
                
                return {
                    'success': True,
                    'machine_name': machine_name,
                    'data': found_data,
                    'sources': search_result.get('sources', [])
                }
            else:
                return {
                    'success': False,
                    'machine_name': machine_name,
                    'error': 'No data found'
                }
        
        except Exception as e:
            logger.error(f"Error searching machine: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def search_operation_modes(self, operation_type: str, material: str = None) -> Dict[str, Any]:
        """
        Найти информацию о режимах обработки для типа операции.
        
        Args:
            operation_type: Тип операции
            material: Материал (опционально)
            
        Returns:
            Результат поиска
        """
        if not self.search_enabled:
            return {'success': False, 'error': 'Internet search disabled'}
        
        try:
            search_result = await self.browser_parser.search_operation_info(operation_type, material)
            
            if search_result.get('success'):
                return {
                    'success': True,
                    'operation_type': operation_type,
                    'material': material,
                    'data': search_result.get('found_data', {}),
                    'sources': search_result.get('sources', [])
                }
            else:
                return {
                    'success': False,
                    'error': 'No data found'
                }
        
        except Exception as e:
            logger.error(f"Error searching operation: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def search_standard_info(self, standard_type: str, standard_number: str) -> Dict[str, Any]:
        """
        Поиск информации о стандарте (ГОСТ/ОСТ) в интернете.
        
        Args:
            standard_type: ГОСТ, ОСТ, DIN, ISO
            standard_number: Номер стандарта (30560-80, 7798-30)
            
        Returns:
            Результат поиска с полем success и message
        """
        if not self.search_enabled:
            return {'success': False, 'error': 'Internet search disabled'}
        
        query = f"{standard_type} {standard_number}"
        try:
            # Ищем как режимы обработки — запрос "ОСТ 30560-80 характеристики"
            r = await self.search_operation_modes(f"{query} характеристики болт гайка")
            if r.get('success') and r.get('data'):
                data = r['data']
                lines = [f"🔍 <b>Найдено по {query}:</b>"]
                for k, v in (data or {}).items():
                    if v:
                        lines.append(f"• {k}: {v}")
                return {'success': True, 'message': '\n'.join(lines)}
            # Пробуем общий поиск
            r = await self.search_operation_modes(query)
            if r.get('success') and r.get('data'):
                data = r['data']
                lines = [f"🔍 <b>Информация о {query}:</b>"]
                for k, v in (data or {}).items():
                    if v:
                        lines.append(f"• {k}: {v}")
                return {'success': True, 'message': '\n'.join(lines)}
        except Exception as e:
            logger.debug(f"Search standard failed: {e}")
        return {'success': False, 'error': 'Nothing found'}

    async def search_unknown_query(self, query: str) -> Dict[str, Any]:
        """
        Поиск в интернете по непонятному запросу.
        Пробует станок, инструмент, операции — возвращает первый успешный результат.
        
        Args:
            query: Текст запроса пользователя
            
        Returns:
            Результат с полем success и найденными данными или сообщением
        """
        if not self.search_enabled or not query or len(query.strip()) < 2:
            return {'success': False, 'error': 'Query too short'}
        
        query = query.strip()
        
        # 1. Похоже на станок (числа + буквы): гамма 1250, NEF500
        if any(c.isdigit() for c in query) and len(query) >= 4:
            r = await self.search_and_save_machine(query)
            if r.get('success'):
                data = r.get('data', {})
                lines = [f"🔍 <b>Найдено в интернете про {query}:</b>"]
                if data.get('power'):
                    lines.append(f"• Мощность: {data.get('power')} кВт")
                if data.get('max_rpm'):
                    lines.append(f"• Макс. обороты: {data.get('max_rpm')} об/мин")
                if not any([data.get('power'), data.get('max_rpm')]) and data:
                    lines.append(f"• Данные: {str(data)[:200]}...")
                return {'success': True, 'message': '\n'.join(lines), 'type': 'machine'}
        
        # 2. Похоже на инструмент (ISO-коды: CNMG, WNMG и т.д.)
        tool_codes = ['cnmg', 'wnmg', 'tnmg', 'dnmg', 'vnmg', 'snmg', 'vbmt', 'tbmt', 'cbmt', 'apmt', 'apkt']
        if any(code in query.lower() for code in tool_codes):
            r = await self.search_and_save_tool(query)
            if r.get('success'):
                data = r.get('data', {})
                lines = [f"🔍 <b>Найдено про инструмент {query}:</b>"]
                for k, v in (data or {}).items():
                    if v:
                        lines.append(f"• {k}: {v}")
                return {'success': True, 'message': '\n'.join(lines) if len(lines) > 1 else lines[0], 'type': 'tool'}
        
        # 3. Общий поиск: материал, операция, режимы (титан, сталь, расточка и т.д.)
        r = await self.search_operation_modes(query)
        if r.get('success'):
            data = r.get('data', {})
            if data and any(v for v in (data.values() if isinstance(data, dict) else [])):
                lines = [f"🔍 <b>Найдено по запросу «{query}»:</b>"]
                for k, v in (data or {}).items():
                    if v:
                        lines.append(f"• {k}: {v}")
                return {'success': True, 'message': '\n'.join(lines), 'type': 'operation'}
        
        return {'success': False, 'error': 'Nothing found'}

    async def _save_machine_to_kb(self, machine_name: str, data: Dict[str, Any]) -> None:
        """
        Сохранить данные о станке в базу знаний.
        
        Args:
            machine_name: Название станка
            data: Найденные данные
        """
        try:
            import json
            from pathlib import Path
            
            machines_file = Path("app/knowledge/knowledge_base/machines.json")
            machines_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Загружаем существующие данные
            machines_data = {'machines': []}
            if machines_file.exists():
                with open(machines_file, 'r', encoding='utf-8') as f:
                    machines_data = json.load(f)
            
            # Добавляем или обновляем данные о станке
            machine_entry = {
                'machine_type': machine_name,
                'power_kw': data.get('power'),
                'max_rpm': data.get('max_rpm'),
                'source': 'internet_search',
                'sources': data.get('sources', [])
            }
            
            # Проверяем, есть ли уже такой станок
            existing_index = None
            for i, m in enumerate(machines_data['machines']):
                if m.get('machine_type', '').lower() == machine_name.lower():
                    existing_index = i
                    break
            
            if existing_index is not None:
                # Обновляем существующий
                machines_data['machines'][existing_index].update(machine_entry)
            else:
                # Добавляем новый
                machines_data['machines'].append(machine_entry)
            
            # Сохраняем обратно
            with open(machines_file, 'w', encoding='utf-8') as f:
                json.dump(machines_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Saved machine {machine_name} to knowledge base")
        
        except Exception as e:
            logger.error(f"Failed to save machine to KB: {e}", exc_info=True)
