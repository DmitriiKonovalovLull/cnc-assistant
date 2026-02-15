"""
Сервис для работы со стандартными деталями (ГОСТ, ОСТ, DIN, ISO).
Загружает данные о стандартах и формирует технологические маршруты.
"""

import logging
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List

from app.domain.standard_classes import get_standard_class
from app.domain.part_templates import get_template

logger = logging.getLogger(__name__)


class StandardService:
    """
    Сервис для работы со стандартами деталей.
    Загружает данные из YAML файлов и формирует технологические маршруты.
    """
    
    def __init__(self, standards_dir: Path = None):
        """
        Инициализация сервиса стандартов.
        
        Args:
            standards_dir: Директория со стандартами (по умолчанию data/standards)
        """
        if standards_dir is None:
            project_root = Path(__file__).parent.parent.parent.parent
            standards_dir = project_root / "data" / "standards"
        
        self.standards_dir = standards_dir
        self.standards_dir.mkdir(parents=True, exist_ok=True)
        self._standards_cache: Dict[str, Dict[str, Any]] = {}
        self._load_standards()
    
    def _load_standards(self) -> None:
        """Загрузить все стандарты из YAML файлов."""
        if not self.standards_dir.exists():
            logger.warning(f"Standards directory not found: {self.standards_dir}")
            return
        
        yaml_files = list(self.standards_dir.glob("*.yaml")) + list(self.standards_dir.glob("*.yml"))
        
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    standard_data = yaml.safe_load(f)
                    if standard_data and 'standard_id' in standard_data:
                        standard_id = standard_data['standard_id']
                        self._standards_cache[standard_id] = standard_data
                        logger.info(f"Loaded standard: {standard_id}")
            except Exception as e:
                logger.error(f"Failed to load standard from {yaml_file}: {e}")
        
        logger.info(f"Loaded {len(self._standards_cache)} standards")
    
    def find_standard(self, standard_type: str, standard_number: str) -> Optional[Dict[str, Any]]:
        """
        Найти стандарт по типу и номеру в базе данных (YAML файлы).
        
        Args:
            standard_type: Тип стандарта (ГОСТ, ОСТ, DIN, ISO)
            standard_number: Номер стандарта (например, "7798-30")
            
        Returns:
            Данные стандарта из YAML или None
        """
        # Нормализуем номер стандарта
        standard_number = standard_number.replace(' ', '-').replace('_', '-')
        standard_id = f"{standard_type}_{standard_number}"
        
        # Ищем точное совпадение
        if standard_id in self._standards_cache:
            return self._standards_cache[standard_id]
        
        # Ищем частичное совпадение
        for cached_id, standard_data in self._standards_cache.items():
            if standard_type.lower() in cached_id.lower() and standard_number in cached_id:
                return standard_data
        
        return None
    
    def get_standard_info(self, standard_type: str, standard_number: str) -> Dict[str, Any]:
        """
        Получить информацию о стандарте (из базы ИЛИ из классов/шаблонов).
        
        ВАЖНО: Работает даже если стандарта нет в базе данных.
        Использует классы стандартов и шаблоны деталей.
        
        Args:
            standard_type: Тип стандарта (ГОСТ, ОСТ, DIN, ISO)
            standard_number: Номер стандарта
            
        Returns:
            Полная информация о стандарте
        """
        # 1. Пытаемся найти в базе данных (YAML)
        standard_data = None
        if standard_number:
            standard_data = self.find_standard(standard_type, standard_number)
        
        # 2. Определяем класс стандарта
        standard_class = get_standard_class(standard_type, standard_number) if standard_number else None
        part_type = standard_class.get('type') if standard_class else None
        part_name = standard_class.get('name') if standard_class else None
        
        # 3. Загружаем шаблон детали
        template = get_template(part_type) if part_type else {}
        
        # 4. Формируем результат
        result = {
            'standard_type': standard_type,
            'standard_number': standard_number,
            'standard_id': f"{standard_type}_{standard_number}" if standard_number else f"{standard_type}_unknown",
            'in_database': standard_data is not None,
            'standard_data': standard_data,  # Данные из YAML (если есть)
            'part_class': {
                'type': part_type,
                'name': part_name
            },
            'template': template  # Шаблон детали (всегда есть если определен класс)
        }
        
        return result
    
    def get_materials(self, standard_data: Dict[str, Any]) -> List[str]:
        """Получить список материалов из стандарта."""
        materials = standard_data.get('materials', [])
        if isinstance(materials, list):
            return materials
        elif isinstance(materials, str):
            return [materials]
        return []
    
    def format_standard_info(self, standard_info: Dict[str, Any]) -> str:
        """
        Форматировать информацию о стандарте для пользователя.
        
        ВАЖНО: Использует классы и шаблоны, работает даже без базы данных.
        
        Args:
            standard_info: Полная информация о стандарте (из get_standard_info)
            
        Returns:
            Отформатированная строка
        """
        lines = []
        
        standard_type = standard_info.get('standard_type', '')
        standard_number = standard_info.get('standard_number', '')
        standard_display = f"{standard_type} {standard_number}" if standard_number else standard_type
        
        lines.append(f"📘 <b>{standard_display}</b>")
        lines.append("")
        
        # Информация о классе детали
        part_class = standard_info.get('part_class', {})
        part_type = part_class.get('type')
        part_name = part_class.get('name')
        
        if part_name:
            lines.append(f"🔩 <b>Тип детали:</b> {part_name}")
        elif part_type:
            # Переводим тип на русский
            type_names = {
                'bolt': 'болт',
                'screw': 'винт',
                'stud': 'шпилька',
                'shaft': 'вал',
                'bushing': 'втулка',
                'nut': 'гайка'
            }
            lines.append(f"🔩 <b>Тип детали:</b> {type_names.get(part_type, part_type)}")
        
        # Информация из шаблона (если определен класс детали)
        template = standard_info.get('template', {})
        if template and part_type:
            # Для гаек показываем размеры резьбы, а не диаметры
            if part_type == 'nut':
                thread_sizes = template.get('thread_sizes')
                if thread_sizes:
                    thread_str = ', '.join(thread_sizes[:8])  # Показываем первые 8
                    if len(thread_sizes) > 8:
                        thread_str += f" ... (всего {len(thread_sizes)})"
                    lines.append(f"📏 <b>Резьбы:</b> {thread_str}")
                
                # Размер под ключ (если есть)
                wrench_sizes = template.get('wrench_sizes')
                if wrench_sizes:
                    lines.append(f"🔧 <b>Под ключ:</b> по стандарту")
                
                # У гаек НЕТ длины - не показываем
            else:
                # Для болтов и других деталей - диаметры
                diameters = template.get('diameters')
                if diameters:
                    if isinstance(diameters, list):
                        diameters_str = ', '.join(diameters[:8])  # Показываем первые 8
                        if len(diameters) > 8:
                            diameters_str += f" ... (всего {len(diameters)})"
                        lines.append(f"📏 <b>Возможные диаметры:</b> {diameters_str}")
                    elif isinstance(diameters, dict):
                        min_d = diameters.get('min')
                        max_d = diameters.get('max')
                        if min_d and max_d:
                            lines.append(f"📏 <b>Диаметры:</b> {min_d}–{max_d} мм")
                
                # Длины (только для деталей, у которых есть длина)
                has_length = template.get('has_length', True)  # По умолчанию True для болтов
                if has_length:
                    lengths = template.get('lengths')
                    if lengths and isinstance(lengths, dict):
                        min_l = lengths.get('min')
                        max_l = lengths.get('max')
                        if min_l and max_l:
                            lines.append(f"📐 <b>Длины:</b> {min_l}–{max_l} мм")
            
            # Материал по умолчанию
            default_material = template.get('default_material')
            if default_material:
                lines.append(f"⚙️ <b>Материал по умолчанию:</b> {default_material}")
        
        # Дополнительная информация из базы данных (если есть)
        standard_data = standard_info.get('standard_data')
        if standard_data:
            description = standard_data.get('description')
            if description:
                lines.append("")
                lines.append(f"📝 <b>Описание:</b> {description}")
            
            materials = self.get_materials(standard_data)
            if materials:
                lines.append(f"🧱 <b>Материалы по стандарту:</b> {', '.join(materials)}")
        
        # Если нет информации ни из базы, ни из шаблона - показываем базовую информацию
        if not template and not standard_data:
            lines.append("")
            lines.append("💡 <i>Стандарт распознан. Укажи параметры детали для продолжения.</i>")
        
        return "\n".join(lines)
    
    def generate_manufacturing_technology(self, standard_info: Dict[str, Any], context: Dict[str, Any]) -> str:
        """
        Сгенерировать технологию изготовления для стандартной детали.
        
        Args:
            standard_info: Информация о стандарте (из get_standard_info)
            context: Контекст с параметрами детали (thread_size, length, quantity, material и т.д.)
            
        Returns:
            Отформатированная технология изготовления
        """
        lines = []
        
        # Получаем тип детали и шаблон
        part_class = standard_info.get('part_class', {})
        part_type = part_class.get('type')
        part_name = part_class.get('name', 'деталь')
        template = standard_info.get('template', {})
        
        # Параметры детали из контекста
        thread_size = context.get('thread_size')
        length = context.get('length')
        quantity = context.get('quantity', 1)
        material = context.get('material', template.get('default_material', 'сталь'))
        machine_type = context.get('machine_type', 'токарный ЧПУ')
        
        # Формируем описание детали
        if part_type == 'nut':
            part_desc = f"Гайка {thread_size or '?'}"
        elif part_type == 'bolt':
            part_desc = f"Болт {thread_size or '?'}"
            if length:
                part_desc += f"×{length} мм"
        else:
            part_desc = part_name
            if thread_size:
                part_desc += f" {thread_size}"
            if length:
                part_desc += f"×{length} мм"
        
        lines.append(f"🔧 <b>Технология изготовления:</b> {part_desc}")
        lines.append("")
        
        # Получаем операции из шаблона
        operations = template.get('operations', [])
        
        if not operations:
            # Если операций нет в шаблоне, формируем стандартный маршрут
            if part_type == 'nut':
                operations = [
                    "1. Подготовка заготовки",
                    "2. Токарная обработка торцов",
                    "3. Сверление отверстия",
                    "4. Нарезание резьбы",
                    "5. Фрезерование граней (шестигранник)",
                    "6. Фаска"
                ]
            elif part_type == 'bolt':
                operations = [
                    "1. Подготовка заготовки",
                    "2. Токарная обработка стержня",
                    "3. Нарезание резьбы",
                    "4. Фрезерование головки (шестигранник)",
                    "5. Фаска"
                ]
            else:
                operations = [
                    "1. Подготовка заготовки",
                    "2. Токарная обработка",
                    "3. Фрезерование (при необходимости)",
                    "4. Финишная обработка"
                ]
        
        # Форматируем операции
        for i, operation in enumerate(operations, 1):
            # Если операция уже содержит номер, не добавляем еще раз
            if isinstance(operation, str):
                # Проверяем, начинается ли строка с цифры и точки
                if len(operation) > 2 and operation[0].isdigit() and operation[1] == '.':
                    lines.append(f"{operation}")
                else:
                    # Переводим операции на русский язык, если нужно
                    operation_ru = operation.replace('_', ' ').title()
                    # Капитализируем первую букву
                    operation_ru = operation_ru[0].upper() + operation_ru[1:] if len(operation_ru) > 1 else operation_ru
                    lines.append(f"{i}. {operation_ru}")
            else:
                lines.append(f"{i}. {operation}")
        
        lines.append("")
        lines.append(f"📋 <b>Параметры:</b>")
        lines.append(f"• Материал: {material}")
        lines.append(f"• Станок: {machine_type}")
        if thread_size:
            lines.append(f"• Резьба/Диаметр: {thread_size}")
        if length:
            lines.append(f"• Длина: {length} мм")
        if quantity:
            lines.append(f"• Количество: {quantity} шт")
        
        lines.append("")
        lines.append("💡 <i>Для получения режимов резания опишите конкретную операцию или используйте команду расчета.</i>")
        
        return "\n".join(lines)
