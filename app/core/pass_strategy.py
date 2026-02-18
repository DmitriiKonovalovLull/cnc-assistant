"""
Стратегия разбивки припуска на проходы.
ЧИСТЫЙ CORE-МОДУЛЬ: только генерация проходов, без аналитики, UI и проверок.
С поддержкой итеративной генерации, численной стабильности и разных типов операций.
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import math
import json
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS И БАЗОВЫЕ КЛАССЫ
# ============================================================================

class PassType(Enum):
    """Тип прохода обработки."""
    ROUGHING = "roughing"
    SEMI_FINISHING = "semi_finishing"
    FINISHING = "finishing"


class OperationType(Enum):
    """Тип операции обработки."""
    ROUGHING = "roughing"
    SEMI_FINISHING = "semi_finishing"
    FINISHING = "finishing"
    MIXED = "mixed"  # когда нужны все типы


# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

@dataclass
class StrategyConfig:
    """Конфигурация стратегии разбивки."""
    # Основные параметры стратегии
    operation_type: OperationType = OperationType.MIXED
    is_external: bool = True  # наружная обработка

    # Ограничения по инструменту
    max_ap_rough_mm: float = 6.0  # макс глубина для черновой
    max_ap_finish_mm: float = 0.8  # макс глубина для чистовой
    min_ap_mm: float = 0.1  # минимальная глубина

    # Ограничения по станку/обработке
    max_total_passes: int = 20  # абсолютный максимум проходов
    preferred_max_passes: int = 12  # желаемый максимум

    # Правила разбивки
    semi_finish_stock_mm: float = 1.0  # припуск на получистовую

    # Критерии качества
    require_finish_pass: bool = True  # всегда делать чистовой проход?
    allow_variable_ap: bool = True  # разрешить разную глубину в черновых проходах

    # Точность
    tolerance_mm: float = 0.05  # допуск на размер
    
    # Пороги для определения количества проходов
    STOCK_THRESHOLD_VERY_LOW: float = 0.5  # мм, очень маленький припуск
    STOCK_THRESHOLD_LOW: float = 2.0  # мм, маленький припуск
    STOCK_THRESHOLD_MEDIUM: float = 10.0  # мм, средний припуск
    STOCK_THRESHOLD_HIGH: float = 30.0  # мм, большой припуск
    
    # Количество проходов для разных диапазонов
    PASSES_VERY_LOW: int = 1
    PASSES_LOW: int = 2
    PASSES_MEDIUM_MIN: int = 2
    PASSES_MEDIUM_MAX: int = 4
    PASSES_HIGH_MIN: int = 4
    PASSES_HIGH_MAX: int = 8
    PASSES_VERY_HIGH_MIN: int = 8
    PASSES_VERY_HIGH_MAX: int = 12
    
    # Коэффициенты для расчета глубины
    AP_PER_PASS_LOW: float = 2.5  # мм на проход для малых припусков
    AP_PER_PASS_MEDIUM: float = 5.0  # мм на проход для средних припусков
    AP_PER_PASS_HIGH: float = 8.0  # мм на проход для больших припусков
    
    # Коэффициенты жесткости
    RIGIDITY_FACTOR_VERY_RIGID: float = 1.0
    RIGIDITY_FACTOR_NORMAL: float = 0.8
    RIGIDITY_FACTOR_FLEXIBLE: float = 0.6
    RIGIDITY_FACTOR_VERY_FLEXIBLE: float = 0.4
    
    # Пороги L/D
    LD_RATIO_RIGID: float = 3.0
    LD_RATIO_NORMAL: float = 5.0
    LD_RATIO_FLEXIBLE: float = 8.0
    
    # Численная стабильность
    EPSILON: float = 1e-6  # Допуск для сравнения float


# ============================================================================
# МОДЕЛИ ДАННЫХ
# ============================================================================

@dataclass
class Pass:
    """Один проход обработки - ТОЛЬКО ГЕОМЕТРИЯ."""
    number: int  # номер прохода
    type: PassType  # тип прохода
    ap_mm: float  # глубина резания, мм
    diameter_before_mm: float  # диаметр до прохода
    diameter_after_mm: float  # диаметр после прохода

    @property
    def stock_removed_mm(self) -> float:
        """Снятый припуск за проход, мм."""
        return (self.diameter_before_mm - self.diameter_after_mm) / 2
    
    def to_dict(self) -> Dict:
        """Конвертировать в словарь для сериализации."""
        return {
            'number': self.number,
            'type': self.type.value,
            'ap_mm': round(self.ap_mm, 3),
            'diameter_before_mm': round(self.diameter_before_mm, 3),
            'diameter_after_mm': round(self.diameter_after_mm, 3),
            'stock_removed_mm': round(self.stock_removed_mm, 3)
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Pass':
        """Создать из словаря."""
        return cls(
            number=data['number'],
            type=PassType(data['type']),
            ap_mm=data['ap_mm'],
            diameter_before_mm=data['diameter_before_mm'],
            diameter_after_mm=data['diameter_after_mm']
        )


@dataclass
class StrategyStatistics:
    """Статистика сгенерированной стратегии."""
    total_passes: int
    roughing_passes: int
    semi_finishing_passes: int
    finishing_passes: int
    total_stock_removed: float
    avg_ap_rough: float
    max_ap: float
    min_ap: float
    
    def to_dict(self) -> Dict:
        """Конвертировать в словарь."""
        return {
            'total_passes': self.total_passes,
            'roughing_passes': self.roughing_passes,
            'semi_finishing_passes': self.semi_finishing_passes,
            'finishing_passes': self.finishing_passes,
            'total_stock_removed': round(self.total_stock_removed, 3),
            'avg_ap_rough': round(self.avg_ap_rough, 3),
            'max_ap': round(self.max_ap, 3),
            'min_ap': round(self.min_ap, 3)
        }


# ============================================================================
# АБСТРАКТНЫЙ БАЗОВЫЙ КЛАСС
# ============================================================================

class BasePassStrategy(ABC):
    """Абстрактный базовый класс для стратегий разбивки."""
    
    @abstractmethod
    def generate_strategy(self) -> List[Pass]:
        """Сгенерировать стратегию."""
        pass
    
    @abstractmethod
    def validate_inputs(self) -> List[str]:
        """Проверить входные данные."""
        pass


# ============================================================================
# СТРАТЕГИЯ ДЛЯ ТОКАРНОЙ ОБРАБОТКИ
# ============================================================================

class TurningPassStrategy(BasePassStrategy):
    """
    Интеллектуальная разбивка припуска на проходы для токарной обработки.
    CORE: только генерация проходов, без валидации, аналитики и UI.
    """

    def __init__(
            self,
            diameter_start_mm: float,
            diameter_end_mm: float,
            config: StrategyConfig,
            length_mm: Optional[float] = None
    ):
        """
        Инициализация стратегии.
        
        Args:
            diameter_start_mm: Начальный диаметр
            diameter_end_mm: Конечный диаметр
            config: Конфигурация стратегии
            length_mm: Длина обработки (для учета жесткости)
        """
        # Округляем до разумной точности
        self.d_start = round(diameter_start_mm, 3)
        self.d_end = round(diameter_end_mm, 3)
        self.config = config
        self.length_mm = length_mm
        self.eps = config.EPSILON
        
        # Проверка входных данных
        errors = self.validate_inputs()
        if errors:
            raise ValueError(f"Invalid inputs: {', '.join(errors)}")

        # Рассчитываем общий припуск с округлением
        self.total_stock_mm = round((diameter_start_mm - diameter_end_mm) / 2, 3)

    def validate_inputs(self) -> List[str]:
        """
        Проверка корректности входных данных.
        
        Returns:
            Список ошибок (пустой если все ок)
        """
        errors = []
        
        if not self._float_gt(self.d_start, self.d_end):
            errors.append("Начальный диаметр должен быть больше конечного")

        stock = (self.d_start - self.d_end) / 2
        if not self._float_gt(stock, 0):
            errors.append("Припуск должен быть положительным")

        if stock > 100:  # 100 мм припуска - это уже абсурд
            errors.append(f"Припуск {stock} мм слишком велик. Проверьте входные данные.")
        
        return errors
    
    def _float_eq(self, a: float, b: float) -> bool:
        """Сравнение float с допуском."""
        return abs(a - b) < self.eps
    
    def _float_gt(self, a: float, b: float) -> bool:
        """Проверка a > b с допуском."""
        return a - b > self.eps
    
    def _float_gte(self, a: float, b: float) -> bool:
        """Проверка a >= b с допуском."""
        return a - b > -self.eps
    
    def _get_rigidity_factor(self, length_mm: Optional[float] = None, diameter_mm: Optional[float] = None) -> float:
        """
        Получить коэффициент жесткости на основе L/D.
        
        Args:
            length_mm: Длина обработки
            diameter_mm: Диаметр обработки
            
        Returns:
            Коэффициент жесткости (0.4-1.0)
        """
        if not length_mm or not diameter_mm or diameter_mm <= 0:
            return self.config.RIGIDITY_FACTOR_NORMAL
        
        ld_ratio = length_mm / diameter_mm
        
        if ld_ratio < self.config.LD_RATIO_RIGID:
            return self.config.RIGIDITY_FACTOR_VERY_RIGID
        elif ld_ratio < self.config.LD_RATIO_NORMAL:
            return self.config.RIGIDITY_FACTOR_NORMAL
        elif ld_ratio < self.config.LD_RATIO_FLEXIBLE:
            return self.config.RIGIDITY_FACTOR_FLEXIBLE
        else:
            return self.config.RIGIDITY_FACTOR_VERY_FLEXIBLE

    def _calculate_optimal_ap_for_roughing(self, total_stock_mm: float) -> float:
        """
        Рассчитать оптимальную глубину резания для черновой обработки.
        CORE: чистая логика расчета, без оценок.
        """
        # Используем конфигурацию вместо магических чисел
        if total_stock_mm <= self.config.STOCK_THRESHOLD_VERY_LOW:
            desired_passes = self.config.PASSES_VERY_LOW
            return total_stock_mm / desired_passes if desired_passes > 0 else total_stock_mm

        elif total_stock_mm <= self.config.STOCK_THRESHOLD_LOW:
            desired_passes = self.config.PASSES_LOW
            return total_stock_mm / desired_passes

        elif total_stock_mm <= self.config.STOCK_THRESHOLD_MEDIUM:
            desired_passes = min(
                self.config.PASSES_MEDIUM_MAX,
                max(self.config.PASSES_MEDIUM_MIN, int(total_stock_mm / self.config.AP_PER_PASS_LOW))
            )
            return total_stock_mm / desired_passes if desired_passes > 0 else total_stock_mm

        elif total_stock_mm <= self.config.STOCK_THRESHOLD_HIGH:
            desired_passes = min(
                self.config.PASSES_HIGH_MAX,
                max(self.config.PASSES_HIGH_MIN, int(total_stock_mm / self.config.AP_PER_PASS_MEDIUM))
            )
            return total_stock_mm / desired_passes if desired_passes > 0 else total_stock_mm

        else:
            desired_passes = min(
                self.config.PASSES_VERY_HIGH_MAX,
                max(self.config.PASSES_VERY_HIGH_MIN, int(total_stock_mm / self.config.AP_PER_PASS_HIGH))
            )
            return total_stock_mm / desired_passes if desired_passes > 0 else total_stock_mm

    def _calculate_roughing_passes(
            self,
            target_ap_mm: float,
            remaining_stock_mm: float,
            start_pass_num: int,
            current_diameter: float,
            rigidity_factor: float = 1.0
    ) -> Tuple[List[Pass], float, int, float]:
        """
        Рассчитать черновые проходы без нумерации.
        Возвращает: (пассы, остаток_припуска, след_номер, текущий_диаметр)
        """
        # Корректируем целевую глубину с учетом жесткости
        adjusted_target = target_ap_mm * rigidity_factor
        adjusted_target = min(adjusted_target, self.config.max_ap_rough_mm)
        
        rough_passes = []
        pass_num = start_pass_num

        if self._float_lte(remaining_stock_mm, adjusted_target):
            ap_actual = remaining_stock_mm
            next_diameter = self._calculate_next_diameter(current_diameter, ap_actual)

            rough_passes.append(Pass(
                number=pass_num,
                type=PassType.ROUGHING,
                ap_mm=round(ap_actual, 3),
                diameter_before_mm=round(current_diameter, 3),
                diameter_after_mm=round(next_diameter, 3)
            ))
            remaining_stock_mm = 0
            current_diameter = next_diameter
            pass_num += 1

        else:
            optimal_ap = self._calculate_optimal_ap_for_roughing(remaining_stock_mm)
            optimal_ap = min(optimal_ap, adjusted_target)

            # Защита от деления на ноль
            if optimal_ap <= self.eps:
                optimal_ap = self.config.min_ap_mm
            
            calculated_passes = math.ceil(remaining_stock_mm / optimal_ap) if optimal_ap > 0 else 1
            max_available_passes = self.config.preferred_max_passes - 2
            actual_passes = min(calculated_passes, max_available_passes)

            if actual_passes > 0:
                ap_per_pass = remaining_stock_mm / actual_passes

                for i in range(actual_passes):
                    if self._float_lte(remaining_stock_mm, 0):
                        break

                    if i == actual_passes - 1:
                        ap_actual = remaining_stock_mm
                    else:
                        if i < actual_passes // 2 and self.config.allow_variable_ap:
                            ap_actual = ap_per_pass * 1.2
                            ap_actual = min(ap_actual, adjusted_target)
                        else:
                            ap_actual = ap_per_pass

                    if ap_actual < self.config.min_ap_mm:
                        if rough_passes:
                            last_pass = rough_passes[-1]
                            last_pass.ap_mm += ap_actual
                            last_pass.diameter_after_mm = self._calculate_next_diameter(
                                last_pass.diameter_before_mm, last_pass.ap_mm
                            )
                        remaining_stock_mm = 0
                        break

                    next_diameter = self._calculate_next_diameter(current_diameter, ap_actual)

                    rough_passes.append(Pass(
                        number=pass_num,
                        type=PassType.ROUGHING,
                        ap_mm=round(ap_actual, 3),
                        diameter_before_mm=round(current_diameter, 3),
                        diameter_after_mm=round(next_diameter, 3)
                    ))

                    current_diameter = next_diameter
                    remaining_stock_mm -= ap_actual
                    remaining_stock_mm = round(remaining_stock_mm, 3)  # Округление для стабильности
                    pass_num += 1

        return rough_passes, round(remaining_stock_mm, 3), pass_num, round(current_diameter, 3)
    
    def _float_lte(self, a: float, b: float) -> bool:
        """Проверка a <= b с допуском."""
        return a - b <= self.eps

    def _calculate_next_diameter(self, current_diameter: float, ap_mm: float) -> float:
        """Рассчитать следующий диаметр."""
        if self.config.is_external:
            return current_diameter - (2 * ap_mm)
        else:
            return current_diameter + (2 * ap_mm)

    def _calculate_finishing_passes(
            self,
            current_diameter: float,
            remaining_stock_mm: float,
            start_pass_num: int
    ) -> List[Pass]:
        """
        Рассчитать чистовые проходы с правильной нумерацией.
        """
        finish_passes = []
        pass_num = start_pass_num

        if self._float_lte(remaining_stock_mm, 0):
            return finish_passes

        finish_type = PassType.FINISHING
        target_ap = min(self.config.max_ap_finish_mm, remaining_stock_mm)

        if self._float_lte(remaining_stock_mm, target_ap * 1.5):
            ap_actual = remaining_stock_mm
            next_diameter = self._calculate_next_diameter(current_diameter, ap_actual)

            finish_passes.append(Pass(
                number=pass_num,
                type=finish_type,
                ap_mm=round(ap_actual, 3),
                diameter_before_mm=round(current_diameter, 3),
                diameter_after_mm=round(next_diameter, 3)
            ))

        else:
            # Получистовой проход
            semi_finish_ap = min(self.config.semi_finish_stock_mm, remaining_stock_mm * 0.7)
            next_diameter = self._calculate_next_diameter(current_diameter, semi_finish_ap)

            finish_passes.append(Pass(
                number=pass_num,
                type=PassType.SEMI_FINISHING,
                ap_mm=round(semi_finish_ap, 3),
                diameter_before_mm=round(current_diameter, 3),
                diameter_after_mm=round(next_diameter, 3)
            ))

            # Чистовой проход
            pass_num += 1
            remaining_finish = remaining_stock_mm - semi_finish_ap
            remaining_finish = round(remaining_finish, 3)
            current_diameter = next_diameter

            finish_ap = min(self.config.max_ap_finish_mm, remaining_finish)
            next_diameter = self._calculate_next_diameter(current_diameter, finish_ap)

            finish_passes.append(Pass(
                number=pass_num,
                type=PassType.FINISHING,
                ap_mm=round(finish_ap, 3),
                diameter_before_mm=round(current_diameter, 3),
                diameter_after_mm=round(next_diameter, 3)
            ))

        return finish_passes

    def generate_strategy(self, target_ap_mm: Optional[float] = None) -> List[Pass]:
        """
        Сгенерировать стратегию разбивки.
        
        Args:
            target_ap_mm: целевая глубина резания (если None - рассчитывается)

        Returns:
            Список проходов обработки - ТОЛЬКО ДАННЫЕ, без аналитики
        """
        # Используем итеративную версию по умолчанию (безопаснее)
        return self.generate_strategy_iterative(target_ap_mm=target_ap_mm)

    def generate_strategy_iterative(self, target_ap_mm: Optional[float] = None) -> List[Pass]:
        """
        Итеративная генерация стратегии (безопаснее при большом количестве проходов).
        
        Args:
            target_ap_mm: целевая глубина резания
            
        Returns:
            Список проходов
        """
        current_diameter = self.d_start
        remaining_stock = self.total_stock_mm
        all_passes = []
        pass_num = 1
        
        # Получаем коэффициент жесткости
        rigidity_factor = self._get_rigidity_factor(self.length_mm, current_diameter)
        
        # Определяем целевую глубину
        if target_ap_mm is None:
            target_ap_mm = self._calculate_optimal_ap_for_roughing(remaining_stock)
            
            if self.config.operation_type == OperationType.ROUGHING:
                target_ap_mm = min(target_ap_mm, self.config.max_ap_rough_mm)
            elif self.config.operation_type == OperationType.SEMI_FINISHING:
                target_ap_mm = min(target_ap_mm, self.config.semi_finish_stock_mm)
            else:
                target_ap_mm = min(target_ap_mm, self.config.max_ap_finish_mm)
        
        # Ограничиваем целевую глубину
        target_ap_mm = min(target_ap_mm, self.config.max_ap_rough_mm)
        target_ap_mm = max(target_ap_mm, self.config.min_ap_mm)
        
        # Корректируем с учетом жесткости
        target_ap_mm *= rigidity_factor
        
        # Генерируем черновые проходы
        while self._float_gt(remaining_stock, self.config.semi_finish_stock_mm * 2):
            # Определяем тип прохода
            if remaining_stock > self.config.semi_finish_stock_mm * 2:
                # Черновой проход
                ap = min(self.config.max_ap_rough_mm * rigidity_factor, remaining_stock * 0.3)
                ap = max(ap, self.config.min_ap_mm)
                pass_type = PassType.ROUGHING
            else:
                break
            
            # Создаем проход
            next_diameter = self._calculate_next_diameter(current_diameter, ap)
            
            all_passes.append(Pass(
                number=pass_num,
                type=pass_type,
                ap_mm=round(ap, 3),
                diameter_before_mm=round(current_diameter, 3),
                diameter_after_mm=round(next_diameter, 3)
            ))
            
            current_diameter = next_diameter
            remaining_stock -= ap
            remaining_stock = round(remaining_stock, 3)
            pass_num += 1
            
            # Защита от бесконечного цикла
            if pass_num > self.config.max_total_passes:
                raise RuntimeError(f"Превышено максимальное количество проходов ({self.config.max_total_passes})")
        
        # Генерируем получистовые и чистовые проходы
        if self._float_gt(remaining_stock, 0) and (self.config.require_finish_pass or
                                                     self.config.operation_type != OperationType.ROUGHING):
            finish_passes = self._calculate_finishing_passes(
                current_diameter=current_diameter,
                remaining_stock_mm=remaining_stock,
                start_pass_num=pass_num
            )
            all_passes.extend(finish_passes)
        
        if len(all_passes) == 0:
            raise ValueError("Не удалось сгенерировать ни одного прохода")
        
        return all_passes

    def _generate_strategy_recursive(
            self,
            target_ap_mm: Optional[float],
            current_diameter: float,
            remaining_stock: float,
            start_pass_num: int,
            recursion_depth: int
    ) -> List[Pass]:
        """
        Рекурсивная генерация стратегии с правильной нумерацией.
        Используется как fallback или для совместимости.
        """
        # Защита от бесконечной рекурсии
        if recursion_depth > 10:
            raise RuntimeError("Превышена глубина рекурсии при генерации стратегии")

        # Определяем целевую глубину резания
        if target_ap_mm is None:
            target_ap_mm = self._calculate_optimal_ap_for_roughing(remaining_stock)

            if self.config.operation_type == OperationType.ROUGHING:
                target_ap_mm = min(target_ap_mm, self.config.max_ap_rough_mm)
            elif self.config.operation_type == OperationType.SEMI_FINISHING:
                target_ap_mm = min(target_ap_mm, self.config.semi_finish_stock_mm)
            else:
                target_ap_mm = min(target_ap_mm, self.config.max_ap_finish_mm)

        # Ограничиваем целевую глубину
        target_ap_mm = min(target_ap_mm, self.config.max_ap_rough_mm)
        target_ap_mm = max(target_ap_mm, self.config.min_ap_mm)
        
        # Получаем коэффициент жесткости
        rigidity_factor = self._get_rigidity_factor(self.length_mm, current_diameter)

        # 1. Рассчитываем черновые проходы
        rough_passes, remaining_after_rough, next_pass_num, current_d_after_rough = \
            self._calculate_roughing_passes(
                target_ap_mm=target_ap_mm,
                remaining_stock_mm=remaining_stock,
                start_pass_num=start_pass_num,
                current_diameter=current_diameter,
                rigidity_factor=rigidity_factor
            )

        all_passes = rough_passes

        # 2. Рассчитываем чистовые проходы (если нужно)
        if self._float_gt(remaining_after_rough, 0) and (self.config.require_finish_pass or
                                                         self.config.operation_type != OperationType.ROUGHING):
            finish_passes = self._calculate_finishing_passes(
                current_diameter=current_d_after_rough,
                remaining_stock_mm=remaining_after_rough,
                start_pass_num=next_pass_num
            )

            all_passes.extend(finish_passes)

        # 3. Проверяем общее количество проходов
        total_passes = len(all_passes)

        # НЕ ДОПУСКАЕМ слишком много проходов!
        if total_passes > self.config.max_total_passes:
            # Пересчитываем с большей глубиной резания
            new_target_ap = self._calculate_optimal_ap_for_roughing(self.total_stock_mm) * 1.5
            new_target_ap = min(new_target_ap, self.config.max_ap_rough_mm)

            return self._generate_strategy_recursive(
                target_ap_mm=new_target_ap,
                current_diameter=self.d_start,
                remaining_stock=self.total_stock_mm,
                start_pass_num=1,
                recursion_depth=recursion_depth + 1
            )

        if total_passes == 0:
            raise ValueError("Не удалось сгенерировать ни одного прохода")

        return all_passes
    
    def get_statistics(self, passes: List[Pass]) -> StrategyStatistics:
        """
        Получить статистику по проходам.
        
        Args:
            passes: Список проходов
            
        Returns:
            Статистика стратегии
        """
        rough_aps = [p.ap_mm for p in passes if p.type == PassType.ROUGHING]
        all_aps = [p.ap_mm for p in passes]
        
        return StrategyStatistics(
            total_passes=len(passes),
            roughing_passes=sum(1 for p in passes if p.type == PassType.ROUGHING),
            semi_finishing_passes=sum(1 for p in passes if p.type == PassType.SEMI_FINISHING),
            finishing_passes=sum(1 for p in passes if p.type == PassType.FINISHING),
            total_stock_removed=sum(p.stock_removed_mm for p in passes),
            avg_ap_rough=sum(rough_aps) / len(rough_aps) if rough_aps else 0,
            max_ap=max(all_aps) if all_aps else 0,
            min_ap=min(all_aps) if all_aps else 0
        )
    
    def export_to_json(self, passes: List[Pass], filepath: Union[str, Path]):
        """
        Экспортировать стратегию в JSON.
        
        Args:
            passes: Список проходов
            filepath: Путь к файлу
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'generated_at': datetime.now().isoformat(),
            'parameters': {
                'diameter_start_mm': self.d_start,
                'diameter_end_mm': self.d_end,
                'total_stock_mm': self.total_stock_mm,
                'length_mm': self.length_mm,
                'operation_type': self.config.operation_type.value,
                'is_external': self.config.is_external
            },
            'passes': [p.to_dict() for p in passes],
            'statistics': self.get_statistics(passes).to_dict()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# ============================================================================
# СТРАТЕГИЯ ДЛЯ ФРЕЗЕРНОЙ ОБРАБОТКИ
# ============================================================================

@dataclass
class MillingPass(Pass):
    """Проход для фрезерной обработки."""
    ae_mm: float = 0.0  # ширина резания (мм)
    depth_before_mm: float = 0.0  # глубина до прохода
    depth_after_mm: float = 0.0  # глубина после прохода
    
    def to_dict(self) -> Dict:
        """Конвертировать в словарь."""
        result = super().to_dict()
        result.update({
            'ae_mm': round(self.ae_mm, 3),
            'depth_before_mm': round(self.depth_before_mm, 3),
            'depth_after_mm': round(self.depth_after_mm, 3)
        })
        return result


class MillingPassStrategy(BasePassStrategy):
    """Стратегия для фрезерной обработки."""
    
    def __init__(
        self,
        width_mm: float,
        depth_mm: float,
        tool_diameter_mm: float,
        config: StrategyConfig
    ):
        """
        Инициализация стратегии фрезерования.
        
        Args:
            width_mm: Ширина фрезерования
            depth_mm: Глубина фрезерования
            tool_diameter_mm: Диаметр инструмента
            config: Конфигурация стратегии
        """
        self.width = round(width_mm, 3)
        self.depth = round(depth_mm, 3)
        self.tool_diameter = round(tool_diameter_mm, 3)
        self.config = config
        self.eps = config.EPSILON
        
        errors = self.validate_inputs()
        if errors:
            raise ValueError(f"Invalid inputs: {', '.join(errors)}")
    
    def validate_inputs(self) -> List[str]:
        """Проверить входные данные."""
        errors = []
        
        if self.width <= 0:
            errors.append("Ширина фрезерования должна быть положительной")
        
        if self.depth <= 0:
            errors.append("Глубина фрезерования должна быть положительной")
        
        if self.tool_diameter <= 0:
            errors.append("Диаметр инструмента должен быть положительным")
        
        return errors
    
    def generate_strategy(self) -> List[MillingPass]:
        """
        Сгенерировать стратегию для фрезерования.
        
        Returns:
            Список проходов фрезерования
        """
        passes = []
        
        # Рассчитываем количество проходов по глубине
        if self.depth <= self.config.max_ap_rough_mm:
            depth_passes = [self.depth]
        else:
            num_depth_passes = math.ceil(self.depth / self.config.max_ap_rough_mm)
            depth_per_pass = self.depth / num_depth_passes
            depth_passes = [depth_per_pass] * num_depth_passes
        
        # Для каждого слоя генерируем проходы по ширине
        pass_num = 1
        current_depth = 0
        
        for depth_ap in depth_passes:
            # Ширина резания для фрез обычно 0.5-0.8 от диаметра
            ae_per_pass = self.tool_diameter * 0.7
            
            if self.width <= ae_per_pass:
                # Один проход по ширине
                passes.append(MillingPass(
                    number=pass_num,
                    type=PassType.ROUGHING if len(depth_passes) > 1 else PassType.FINISHING,
                    ap_mm=round(depth_ap, 3),
                    diameter_before_mm=0,  # Не используется для фрезерования
                    diameter_after_mm=0,  # Не используется для фрезерования
                    ae_mm=round(self.width, 3),
                    depth_before_mm=round(current_depth, 3),
                    depth_after_mm=round(current_depth + depth_ap, 3)
                ))
                pass_num += 1
            else:
                # Несколько проходов по ширине
                num_width_passes = math.ceil(self.width / ae_per_pass)
                width_per_pass = self.width / num_width_passes
                
                for i in range(num_width_passes):
                    passes.append(MillingPass(
                        number=pass_num,
                        type=PassType.ROUGHING,
                        ap_mm=round(depth_ap, 3),
                        diameter_before_mm=0,
                        diameter_after_mm=0,
                        ae_mm=round(width_per_pass, 3),
                        depth_before_mm=round(current_depth, 3),
                        depth_after_mm=round(current_depth + depth_ap, 3)
                    ))
                    pass_num += 1
            
            current_depth += depth_ap
            
            # Защита от бесконечного цикла
            if pass_num > self.config.max_total_passes:
                raise RuntimeError(f"Превышено максимальное количество проходов ({self.config.max_total_passes})")
        
        return passes


# ============================================================================
# ОБРАТНАЯ СОВМЕСТИМОСТЬ
# ============================================================================

# Для обратной совместимости
PassStrategy = TurningPassStrategy
