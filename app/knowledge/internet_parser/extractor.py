"""
Извлечение фактов из текста.
Находит: "Ti-6Al-4V vc 25-40", "CNMG 120408 radius 0.8" и т.д.
"""

import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class FactExtractor:
    """
    Извлечение фактов о материалах, инструментах, режимах резания из текста.
    """
    
    def __init__(self):
        """Инициализация экстрактора."""
        # Паттерны для извлечения фактов
        self.material_patterns = [
            r'([A-Za-zА-Яа-я]+\s*\d+[A-Za-zА-Яа-я]*)\s+vc\s+(\d+)\s*[-–]\s*(\d+)',  # "Ti-6Al-4V vc 25-40"
            r'материал[аы]?\s+([А-Яа-яA-Za-z]+)\s+скорость\s+(\d+)\s*[-–]\s*(\d+)',  # "материал титан скорость 20-60"
        ]
        
        self.tool_patterns = [
            r'(CNMG|WNMG|TNMG|DNMG)\s+(\d{6})\s+radius\s+(\d+\.?\d*)',  # "CNMG 120408 radius 0.8"
            r'инструмент[аы]?\s+([A-Z]+)\s+радиус\s+(\d+\.?\d*)',  # "инструмент CNMG радиус 0.8"
        ]
        
        self.cutting_speed_patterns = [
            r'vc\s*[=:]\s*(\d+)\s*м/мин',  # "vc = 150 м/мин"
            r'скорость\s+резания\s+(\d+)\s*м/мин',  # "скорость резания 150 м/мин"
            r'(\d+)\s*м/мин\s+для\s+([А-Яа-яA-Za-z]+)',  # "150 м/мин для титана"
        ]
    
    def extract_facts(self, text: str) -> List[Dict[str, Any]]:
        """
        Извлечь факты из текста.
        
        Args:
            text: Текст для анализа
            
        Returns:
            Список извлеченных фактов
        """
        facts = []
        text_upper = text.upper()
        
        # Извлекаем факты о материалах и скоростях
        for pattern in self.material_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                facts.append({
                    'type': 'material_speed',
                    'material': match.group(1),
                    'vc_min': float(match.group(2)),
                    'vc_max': float(match.group(3)),
                    'source': 'internet_parser',
                    'confidence': 0.7
                })
        
        # Извлекаем факты об инструментах
        for pattern in self.tool_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                facts.append({
                    'type': 'tool',
                    'tool_name': match.group(1),
                    'tool_code': match.group(2) if len(match.groups()) > 1 else None,
                    'radius': float(match.group(-1)),
                    'source': 'internet_parser',
                    'confidence': 0.7
                })
        
        # Извлекаем скорости резания
        for pattern in self.cutting_speed_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                facts.append({
                    'type': 'cutting_speed',
                    'vc': float(match.group(1)),
                    'material': match.group(2) if len(match.groups()) > 1 else None,
                    'source': 'internet_parser',
                    'confidence': 0.6
                })
        
        return facts
    
    def save_facts_to_knowledge_base(self, facts: List[Dict[str, Any]]) -> bool:
        """
        Сохранить извлеченные факты в базу знаний.
        
        Args:
            facts: Список фактов
            
        Returns:
            True если успешно сохранено
        """
        try:
            import json
            from pathlib import Path
            
            knowledge_file = Path("app/knowledge/knowledge_base/extracted_facts.json")
            knowledge_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Загружаем существующие факты
            existing_facts = []
            if knowledge_file.exists():
                with open(knowledge_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    existing_facts = data.get('facts', [])
            
            # Добавляем новые факты
            existing_facts.extend(facts)
            
            # Сохраняем обратно
            with open(knowledge_file, 'w', encoding='utf-8') as f:
                json.dump({'facts': existing_facts}, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Saved {len(facts)} facts to knowledge base")
            return True
        
        except Exception as e:
            logger.error(f"Failed to save facts: {e}", exc_info=True)
            return False
