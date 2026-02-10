"""
Экспортер данных для обучения LLM.
Оптимизирован для больших объемов данных и батчинга.
"""

import logging
import json
from pathlib import Path
from typing import Iterator, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select

logger = logging.getLogger(__name__)


class TrainingDataExporter:
    """
    Экспортер данных для обучения LLM.
    Поддерживает батчинг и различные форматы экспорта.
    """
    
    def __init__(self, db_session: Session, batch_size: int = 1000):
        """
        Инициализация экспортера.
        
        Args:
            db_session: SQLAlchemy сессия
            batch_size: Размер батча для обработки
        """
        self.db_session = db_session
        self.batch_size = batch_size
    
    def export_to_jsonl(
        self,
        output_path: Path,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> int:
        """
        Экспортировать данные в JSONL формат.
        
        Args:
            output_path: Путь к выходному файлу
            limit: Максимальное количество записей (None = все)
            offset: Смещение для пагинации
            
        Returns:
            Количество экспортированных записей
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        count = 0
        with open(output_path, 'w', encoding='utf-8') as f:
            for batch in self._iterate_decisions(limit, offset):
                for record in batch:
                    json_line = json.dumps(record, ensure_ascii=False, default=str)
                    f.write(json_line + '\n')
                    count += 1
        
        logger.info(f"Exported {count} records to {output_path}")
        return count
    
    def export_to_json(
        self,
        output_path: Path,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> int:
        """
        Экспортировать данные в JSON формат (массив).
        
        Args:
            output_path: Путь к выходному файлу
            limit: Максимальное количество записей
            offset: Смещение для пагинации
            
        Returns:
            Количество экспортированных записей
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        records = []
        for batch in self._iterate_decisions(limit, offset):
            records.extend(batch)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"Exported {len(records)} records to {output_path}")
        return len(records)
    
    def export_for_finetuning(
        self,
        output_path: Path,
        format_type: str = "chatml"  # chatml, alpaca, instruction
    ) -> int:
        """
        Экспортировать данные в формате для fine-tuning LLM.
        
        Args:
            output_path: Путь к выходному файлу
            format_type: Тип формата (chatml, alpaca, instruction)
            
        Returns:
            Количество экспортированных записей
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        count = 0
        with open(output_path, 'w', encoding='utf-8') as f:
            for batch in self._iterate_decisions():
                for record in batch:
                    formatted = self._format_for_finetuning(record, format_type)
                    if formatted:
                        json_line = json.dumps(formatted, ensure_ascii=False, default=str)
                        f.write(json_line + '\n')
                        count += 1
        
        logger.info(f"Exported {count} records for fine-tuning to {output_path}")
        return count
    
    def _iterate_decisions(
        self,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> Iterator[list]:
        """Итератор по решениям пользователей батчами."""
        from app.storage.models import UserDecision
        
        query = select(UserDecision).offset(offset)
        if limit:
            query = query.limit(limit)
        
        processed = 0
        while True:
            batch = self.db_session.execute(
                query.offset(processed).limit(self.batch_size)
            ).scalars().all()
            
            if not batch:
                break
            
            records = [self._format_decision(decision) for decision in batch]
            yield records
            
            processed += len(batch)
            
            if limit and processed >= limit:
                break
    
    def _format_decision(self, decision) -> Dict[str, Any]:
        """Форматировать решение для экспорта."""
        return {
            'id': decision.id,
            'user_id': decision.user_id,
            'timestamp': decision.timestamp.isoformat() if decision.timestamp else None,
            
            # Входные данные
            'input': {
                'material': decision.full_context.get('material') if decision.full_context else None,
                'operation': decision.operation_type,
                'diameter_start': decision.diameter_start_mm,
                'diameter_end': decision.diameter_end_mm,
                'length': decision.length_mm,
                'machine_type': decision.full_context.get('machine_type') if decision.full_context else None,
                'tool_material': decision.full_context.get('tool_material') if decision.full_context else None,
            },
            
            # Рекомендация бота
            'bot_recommendation': {
                'vc': decision.bot_vc_m_min,
                'rpm': decision.bot_rpm,
                'feed': decision.bot_feed_mm_rev,
                'ap': decision.bot_ap_mm,
                'power': decision.bot_power_kw,
            },
            
            # Решение пользователя
            'user_decision': {
                'rpm': decision.user_rpm,
                'feed': decision.user_feed_mm_rev,
                'ap': decision.user_ap_mm,
            },
            
            # Сравнение
            'comparison': {
                'choice': decision.comparison_choice,
                'rpm_coeff': decision.diff_coeff_rpm,
                'feed_coeff': decision.diff_coeff_feed,
                'ap_coeff': decision.diff_coeff_ap,
            },
            
            # Результат
            'result': {
                'type': decision.result_type,
                'details': decision.result_details,
                'tool_life': decision.tool_life_minutes,
            },
            
            # Метаданные
            'metadata': {
                'experience_level': decision.experience_level,
                'was_adaptive': decision.was_decision_adaptive,
                'source': decision.source,
            }
        }
    
    def _format_for_finetuning(
        self,
        record: Dict[str, Any],
        format_type: str
    ) -> Optional[Dict[str, Any]]:
        """Форматировать запись для fine-tuning."""
        if format_type == "chatml":
            return {
                'messages': [
                    {
                        'role': 'user',
                        'content': self._create_user_prompt(record)
                    },
                    {
                        'role': 'assistant',
                        'content': self._create_assistant_response(record)
                    }
                ]
            }
        
        elif format_type == "alpaca":
            return {
                'instruction': 'Подбери режимы резания для токарной обработки',
                'input': self._create_user_prompt(record),
                'output': self._create_assistant_response(record)
            }
        
        elif format_type == "instruction":
            return {
                'instruction': self._create_user_prompt(record),
                'response': self._create_assistant_response(record)
            }
        
        return None
    
    def _create_user_prompt(self, record: Dict[str, Any]) -> str:
        """Создать промпт пользователя из записи."""
        input_data = record.get('input', {})
        parts = []
        
        if input_data.get('material'):
            parts.append(f"Материал: {input_data['material']}")
        if input_data.get('diameter_start') and input_data.get('diameter_end'):
            parts.append(f"Диаметры: Ø{input_data['diameter_start']} → Ø{input_data['diameter_end']} мм")
        if input_data.get('operation'):
            parts.append(f"Операция: {input_data['operation']}")
        
        return " ".join(parts) if parts else "Подбери режимы резания"
    
    def _create_assistant_response(self, record: Dict[str, Any]) -> str:
        """Создать ответ ассистента из записи."""
        bot_rec = record.get('bot_recommendation', {})
        parts = []
        
        if bot_rec.get('vc'):
            parts.append(f"Скорость резания: {bot_rec['vc']:.0f} м/мин")
        if bot_rec.get('rpm'):
            parts.append(f"Обороты: {bot_rec['rpm']:.0f} об/мин")
        if bot_rec.get('feed'):
            parts.append(f"Подача: {bot_rec['feed']:.2f} мм/об")
        if bot_rec.get('ap'):
            parts.append(f"Глубина: {bot_rec['ap']:.1f} мм")
        
        return "\n".join(parts) if parts else "Рекомендация не доступна"
