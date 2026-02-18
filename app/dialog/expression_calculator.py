"""
Парсер и калькулятор математических выражений.
Безопасный парсинг без использования eval() напрямую.
"""

import ast
import math
import logging
import re
from typing import Optional, Union

logger = logging.getLogger(__name__)


class ExpressionCalculator:
    """
    Безопасный калькулятор математических выражений.
    Использует ast.parse с whitelist разрешенных операций.
    """
    
    # Разрешенные функции
    ALLOWED_FUNCTIONS = {
        'sqrt': math.sqrt,
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan,
        'asin': math.asin,
        'acos': math.acos,
        'atan': math.atan,
        'log': math.log,
        'log10': math.log10,
        'exp': math.exp,
        'abs': abs,
        'round': round,
        'floor': math.floor,
        'ceil': math.ceil,
        'pi': math.pi,
        'e': math.e,
    }
    
    # Разрешенные операторы
    ALLOWED_OPERATORS = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b if b != 0 else float('inf'),
        ast.Pow: lambda a, b: a ** b,
        ast.USub: lambda a: -a,
        ast.UAdd: lambda a: +a,
    }
    
    def __init__(self):
        """Инициализация калькулятора."""
        pass
    
    def is_expression(self, text: str) -> bool:
        """
        Проверить является ли текст математическим выражением.
        
        Args:
            text: Текст для проверки
            
        Returns:
            True если это математическое выражение
        """
        if not text or not text.strip():
            return False
        
        text = text.strip()
        
        # Простые паттерны для математических выражений
        # Должны содержать операторы или функции
        math_patterns = [
            r'[\d\s+\-*/()]+[+\-*/]',  # Содержит операторы
            r'sqrt|sin|cos|tan|log|exp|pi|e',  # Содержит функции/константы
            r'\d+\s*[+\-*/]\s*\d+',  # Простые операции
            r'^\d+[\s+\-*/()\d.]+$',  # Только числа и операторы
        ]
        
        for pattern in math_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                # Проверяем что это не стандарт (ГОСТ, ОСТ и т.д.)
                if not self._is_standard(text):
                    return True
        
        return False
    
    def _is_standard(self, text: str) -> bool:
        """Проверить является ли текст стандартом."""
        standard_patterns = [
            r'\b(?:ГОСТ|GOST|ОСТ|OST|ISO|DIN|EN|ANSI|ASME|JIS|BS)\s*\d+',
        ]
        for pattern in standard_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def calculate(self, expression: str) -> Optional[Union[float, int]]:
        """
        Вычислить математическое выражение.
        
        Args:
            expression: Математическое выражение
            
        Returns:
            Результат вычисления или None если ошибка
        """
        if not expression or not expression.strip():
            return None
        
        try:
            # Заменяем константы
            expr = expression.strip()
            expr = expr.replace('pi', str(math.pi))
            expr = expr.replace('e', str(math.e))
            
            # Парсим AST
            tree = ast.parse(expr, mode='eval')
            
            # Вычисляем безопасно
            result = self._eval_node(tree.body)
            
            return result
        
        except Exception as e:
            logger.warning(f"Error calculating expression '{expression}': {e}")
            return None
    
    def _eval_node(self, node: ast.AST) -> Union[float, int]:
        """
        Безопасное вычисление AST узла.
        
        Args:
            node: AST узел
            
        Returns:
            Результат вычисления
        """
        if isinstance(node, ast.Num):  # Python < 3.8
            return node.n
        elif isinstance(node, ast.Constant):  # Python >= 3.8
            if isinstance(node.value, (int, float)):
                return node.value
            else:
                raise ValueError(f"Unsupported constant type: {type(node.value)}")
        
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op_type = type(node.op)
            
            if op_type not in self.ALLOWED_OPERATORS:
                raise ValueError(f"Unsupported operator: {op_type}")
            
            return self.ALLOWED_OPERATORS[op_type](left, right)
        
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            op_type = type(node.op)
            
            if op_type not in self.ALLOWED_OPERATORS:
                raise ValueError(f"Unsupported operator: {op_type}")
            
            return self.ALLOWED_OPERATORS[op_type](operand)
        
        elif isinstance(node, ast.Call):
            func_name = node.func.id if isinstance(node.func, ast.Name) else None
            
            if func_name not in self.ALLOWED_FUNCTIONS:
                raise ValueError(f"Unsupported function: {func_name}")
            
            args = [self._eval_node(arg) for arg in node.args]
            return self.ALLOWED_FUNCTIONS[func_name](*args)
        
        elif isinstance(node, ast.Name):
            # Константы (pi, e уже заменены, но на всякий случай)
            if node.id in self.ALLOWED_FUNCTIONS:
                value = self.ALLOWED_FUNCTIONS[node.id]
                if isinstance(value, (int, float)):
                    return value
            
            raise ValueError(f"Unsupported name: {node.id}")
        
        else:
            raise ValueError(f"Unsupported AST node type: {type(node)}")
