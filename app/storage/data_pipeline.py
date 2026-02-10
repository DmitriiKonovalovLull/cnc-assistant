"""
Подготовка датасета для обучения LLM.
Преобразует данные из БД в формат для fine-tuning.
"""

import logging
import json
from pathlib import Path
from typing import Iterator, Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select

logger = logging.getLogger(__name__)


class DataPipeline:
    """
    Пайплайн подготовки данных для обучения LLM.
    """
    
    def __init__(self, db_session: Session, output_dir: Path = Path("training/datasets")):
        """
        Инициализация пайплайна.
        
        Args:
            db_session: SQLAlchemy сессия
            output_dir: Директория для выходных файлов
        """
        self.db_session = db_session
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def prepare_dataset(
        self,
        format_type: str = "chatml",  # chatml, alpaca, instruction
        limit: Optional[int] = None
    ) -> Path:
        """
        Подготовить датасет для обучения.
        
        Args:
            format_type: Тип формата (chatml, alpaca, instruction)
            limit: Максимальное количество записей
            
        Returns:
            Путь к созданному файлу
        """
        from app.storage.models import UserDecision
        
        output_file = self.output_dir / f"dataset_{format_type}_{datetime.now().strftime('%Y%m%d')}.jsonl"
        
        count = 0
        with open(output_file, 'w', encoding='utf-8') as f:
            query = select(UserDecision).order_by(UserDecision.timestamp.desc())
            if limit:
                query = query.limit(limit)
            
            decisions = self.db_session.execute(query).scalars().all()
            
            for decision in decisions:
                try:
                    # Формируем запись для обучения
                    record = self._format_for_training(decision, format_type)
                    if record:
                        json_line = json.dumps(record, ensure_ascii=False, default=str)
                        f.write(json_line + '\n')
                        count += 1
                except Exception as e:
                    logger.warning(f"Failed to format decision {decision.id}: {e}")
                    continue
        
        logger.info(f"Prepared dataset: {count} records in {output_file}")
        return output_file
    
    def _format_for_training(self, decision, format_type: str) -> Optional[Dict[str, Any]]:
        """
        Форматировать решение для обучения.
        
        Args:
            decision: Запись UserDecision
            format_type: Тип формата
            
        Returns:
            Отформатированная запись или None
        """
        import json
        
        # Загружаем контекст
        full_context = json.loads(decision.full_context_json) if decision.full_context_json else {}
        context_data = full_context.get('context', {})
        
        # Формируем входные данные (промпт пользователя)
        user_input = self._create_user_input(context_data, decision)
        
        # Формируем выходные данные (ответ ассистента)
        assistant_output = self._create_assistant_output(decision, context_data)
        
        if format_type == "chatml":
            return {
                'messages': [
                    {'role': 'user', 'content': user_input},
                    {'role': 'assistant', 'content': assistant_output}
                ],
                'metadata': {
                    'decision_id': decision.id,
                    'user_id': decision.user_id,
                    'timestamp': decision.timestamp.isoformat() if decision.timestamp else None
                }
            }
        
        elif format_type == "alpaca":
            return {
                'instruction': 'Подбери режимы резания для токарной обработки',
                'input': user_input,
                'output': assistant_output
            }
        
        elif format_type == "instruction":
            return {
                'instruction': user_input,
                'response': assistant_output
            }
        
        return None
    
    def _create_user_input(self, context: Dict[str, Any], decision) -> str:
        """Создать входной промпт пользователя."""
        parts = []
        
        if context.get('material'):
            parts.append(f"Материал: {context['material']}")
        
        if decision.diameter_start_mm and decision.diameter_end_mm:
            parts.append(f"Диаметры: Ø{decision.diameter_start_mm} → Ø{decision.diameter_end_mm} мм")
        
        if context.get('machine_type'):
            parts.append(f"Станок: {context['machine_type']}")
        
        if context.get('tool_name'):
            parts.append(f"Инструмент: {context['tool_name']}")
        
        if context.get('mode'):
            parts.append(f"Режим: {context['mode']}")
        
        return " ".join(parts) if parts else "Подбери режимы резания"
    
    def _create_assistant_output(self, decision, context: Dict[str, Any]) -> str:
        """Создать выходной ответ ассистента."""
        parts = []
        
        if decision.bot_vc_m_min:
            parts.append(f"Скорость резания: {decision.bot_vc_m_min:.0f} м/мин")
        if decision.bot_rpm:
            parts.append(f"Обороты: {decision.bot_rpm:.0f} об/мин")
        if decision.bot_feed_mm_rev:
            parts.append(f"Подача: {decision.bot_feed_mm_rev:.2f} мм/об")
        if decision.bot_ap_mm:
            parts.append(f"Глубина: {decision.bot_ap_mm:.1f} мм")
        
        # Если есть решение оператора, добавляем сравнение
        if decision.user_rpm > 0:
            parts.append(f"\nОператор использовал: {decision.user_rpm:.0f} об/мин, "
                        f"{decision.user_feed_mm_rev:.2f} мм/об, {decision.user_ap_mm:.1f} мм")
        
        return "\n".join(parts) if parts else "Рекомендация не доступна"
    
    def prepare_prompts(self, output_dir: Optional[Path] = None) -> Path:
        """
        Подготовить системные промпты для LLM.
        
        Args:
            output_dir: Директория для промптов (по умолчанию training/prompts)
            
        Returns:
            Путь к файлу с промптами
        """
        prompts_dir = output_dir or Path("training/prompts")
        prompts_dir.mkdir(parents=True, exist_ok=True)
        
        prompts_file = prompts_dir / "system_prompts.json"
        
        prompts = {
            'main_assistant': (
                "Ты — опытный технолог-консультант по металлообработке на станках ЧПУ. "
                "Твоя задача — помогать операторам подбирать оптимальные режимы резания. "
                "Ты понимаешь физику резания, знаешь ограничения станков и инструментов, "
                "и можешь делать разумные предположения на основе контекста. "
                "Всегда объясняй свои рекомендации и предупреждай о возможных проблемах."
            ),
            'assumption_engine': (
                "Когда данных недостаточно, делай разумные предположения на основе контекста. "
                "Например: если указан ЧПУ станок — предполагай твердый сплав; "
                "если большой припуск — предполагай черновую обработку. "
                "Всегда помечай предположения и снижай уверенность."
            ),
            'recommendation': (
                "Формулируй рекомендации естественным языком, без формул. "
                "Объясняй почему такие параметры, предупреждай о рисках. "
                "Спрашивай как оператор делает на практике — это ценный опыт."
            )
        }
        
        with open(prompts_file, 'w', encoding='utf-8') as f:
            json.dump(prompts, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Prepared prompts in {prompts_file}")
        return prompts_file
