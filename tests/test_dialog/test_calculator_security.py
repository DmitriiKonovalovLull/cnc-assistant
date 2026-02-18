"""
Тесты безопасности калькулятора - защита от RCE.
"""

import pytest

from app.dialog.expression_calculator import ExpressionCalculator


@pytest.fixture
def calculator():
    """Фикстура для ExpressionCalculator."""
    return ExpressionCalculator()


def test_rce_import_os(calculator):
    """Попытка выполнить __import__('os').system() должна быть заблокирована."""
    result = calculator.calculate("__import__('os').system('ls')")
    assert result is None, "RCE через __import__ должен быть заблокирован"


def test_rce_class_mro(calculator):
    """Попытка доступа к __class__.__mro__ должна быть заблокирована."""
    result = calculator.calculate("().__class__.__mro__")
    assert result is None, "Доступ к __class__ должен быть заблокирован"


def test_rce_open_file(calculator):
    """Попытка открыть файл должна быть заблокирована."""
    result = calculator.calculate("open('file.txt')")
    assert result is None, "open() должен быть заблокирован"


def test_rce_exec(calculator):
    """Попытка выполнить exec() должна быть заблокирована."""
    result = calculator.calculate("exec('print(1)')")
    assert result is None, "exec() должен быть заблокирован"


def test_rce_eval(calculator):
    """Попытка выполнить eval() должна быть заблокирован."""
    result = calculator.calculate("eval('1+1')")
    assert result is None, "eval() должен быть заблокирован"


def test_rce_compile(calculator):
    """Попытка выполнить compile() должна быть заблокирована."""
    result = calculator.calculate("compile('1+1', '<string>', 'eval')")
    assert result is None, "compile() должен быть заблокирован"


def test_rce_subprocess(calculator):
    """Попытка использовать subprocess должна быть заблокирована."""
    result = calculator.calculate("__import__('subprocess').call(['ls'])")
    assert result is None, "subprocess должен быть заблокирован"


def test_safe_expressions(calculator):
    """Безопасные выражения должны работать."""
    assert calculator.calculate("2+2") == 4
    assert calculator.calculate("10*5") == 50
    assert calculator.calculate("sqrt(16)") == 4.0
    assert calculator.calculate("sin(0)") == 0.0
    assert calculator.calculate("3.14*2") == pytest.approx(6.28, rel=1e-2)


def test_allowed_functions_only(calculator):
    """Только разрешенные функции должны работать."""
    # Разрешенные функции
    assert calculator.calculate("sqrt(4)") == 2.0
    assert calculator.calculate("abs(-5)") == 5
    assert calculator.calculate("round(3.7)") == 4
    
    # Запрещенные функции (не в ALLOWED_FUNCTIONS)
    assert calculator.calculate("print('test')") is None
    assert calculator.calculate("len([1,2,3])") is None


def test_allowed_operators_only(calculator):
    """Только разрешенные операторы должны работать."""
    assert calculator.calculate("2+3") == 5
    assert calculator.calculate("10-4") == 6
    assert calculator.calculate("3*4") == 12
    assert calculator.calculate("8/2") == 4.0
    assert calculator.calculate("2**3") == 8
    assert calculator.calculate("-5") == -5


def test_complex_safe_expression(calculator):
    """Сложные безопасные выражения должны работать."""
    assert calculator.calculate("(2+3)*4") == 20
    assert calculator.calculate("sqrt(16)+sqrt(9)") == 7.0
    assert calculator.calculate("2**3+3*2") == 14
    assert calculator.calculate("sin(0)+cos(0)") == 1.0


def test_malicious_nested_calls(calculator):
    """Вложенные вызовы запрещенных функций должны быть заблокированы."""
    result = calculator.calculate("__import__('os').system(__import__('subprocess').call(['ls']))")
    assert result is None, "Вложенные вызовы должны быть заблокированы"


def test_ast_node_validation(calculator):
    """Проверка что только разрешенные AST узлы обрабатываются."""
    # Попытка использовать запрещенный узел должна привести к ошибке
    # Например, ast.Attribute для доступа к атрибутам
    result = calculator.calculate("object.__class__")
    assert result is None, "Доступ к атрибутам должен быть заблокирован"
