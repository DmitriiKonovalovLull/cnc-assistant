"""
Очистка текста от мусора перед извлечением фактов.
"""

import re
from typing import str as StringType


class TextCleaner:
    """
    Очистка текста от HTML, рекламы, мусора.
    """
    
    @staticmethod
    def clean_html(html: str) -> str:
        """
        Очистить HTML от тегов.
        
        Args:
            html: HTML контент
            
        Returns:
            Очищенный текст
        """
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            # Удаляем скрипты и стили
            for script in soup(["script", "style"]):
                script.decompose()
            return soup.get_text()
        except ImportError:
            # Fallback без BeautifulSoup
            text = re.sub(r'<[^>]+>', '', html)
            return text
    
    @staticmethod
    def clean_text(text: str) -> str:
        """
        Очистить текст от мусора.
        
        Args:
            text: Исходный текст
            
        Returns:
            Очищенный текст
        """
        # Удаляем множественные пробелы
        text = re.sub(r'\s+', ' ', text)
        
        # Удаляем спецсимволы (оставляем буквы, цифры, основные знаки)
        text = re.sub(r'[^\w\s\.\,\;\:\-\(\)]', '', text)
        
        # Удаляем короткие строки (менее 3 символов)
        lines = text.split('\n')
        lines = [line.strip() for line in lines if len(line.strip()) >= 3]
        
        return '\n'.join(lines)
    
    @staticmethod
    def extract_tables(text: str) -> list:
        """
        Извлечь таблицы из текста.
        
        Args:
            text: Текст с таблицами
            
        Returns:
            Список таблиц
        """
        # Простое извлечение таблиц (можно улучшить)
        tables = []
        lines = text.split('\n')
        
        current_table = []
        for line in lines:
            # Если строка содержит разделители таблицы
            if '|' in line or '\t' in line:
                current_table.append(line)
            else:
                if current_table:
                    tables.append('\n'.join(current_table))
                    current_table = []
        
        if current_table:
            tables.append('\n'.join(current_table))
        
        return tables
