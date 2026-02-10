"""
Стратегия разбивки припуска на проходы.
ЧИСТЫЙ CORE-МОДУЛЬ: только генерация проходов, без аналитики, UI и проверок.
"""
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import math


class PassType(Enum):
    """Тип прохода обработки."""
    ROUGHING = "roughing"
    SEMI_FINISHING = "semi_finishing"
    FINISHING = "finishing"


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


@dataclass
class StrategyConfig:
    """Конфигурация стратегии разбивки."""
    # Основные параметры стратегии
    operation_type: str = 'roughing'  # TODO: вынести в handler, core не должен знать про операции
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


class PassStrategy:
    """
    Интеллектуальная разбивка припуска на проходы.
    CORE: только генерация проходов, без валидации, аналитики и UI.
    """

    def __init__(
            self,
            diameter_start_mm: float,
            diameter_end_mm: float,
            config: StrategyConfig
    ):
        self.d_start = diameter_start_mm
        self.d_end = diameter_end_mm
        self.config = config

        # Проверка входных данных
        self._validate_inputs()

        # Рассчитываем общий припуск
        self.total_stock_mm = (diameter_start_mm - diameter_end_mm) / 2

    def _validate_inputs(self):
        """Проверка корректности входных данных (только базовые ошибки)."""
        if self.d_start <= self.d_end:
            raise ValueError("Начальный диаметр должен быть больше конечного")

        stock = (self.d_start - self.d_end) / 2
        if stock <= 0:
            raise ValueError("Припуск должен быть положительным")

        if stock > 100:  # 100 мм припуска - это уже абсурд
            raise ValueError(f"Припуск {stock} мм слишком велик. Проверьте входные данные.")

    def _calculate_optimal_ap_for_roughing(self, total_stock_mm: float) -> float:
        """
        Рассчитать оптимальную глубину резания для черновой обработки.
        CORE: чистая логика расчета, без оценок.
        """
        if total_stock_mm <= 2:
            desired_passes = 1 if total_stock_mm < 0.5 else 2
            return total_stock_mm / desired_passes

        elif total_stock_mm <= 10:
            desired_passes = min(4, max(2, int(total_stock_mm / 2.5)))
            return total_stock_mm / desired_passes

        elif total_stock_mm <= 30:
            desired_passes = min(8, max(4, int(total_stock_mm / 5)))
            return total_stock_mm / desired_passes

        else:
            desired_passes = min(12, max(8, int(total_stock_mm / 8)))
            return total_stock_mm / desired_passes

    def _calculate_roughing_passes(
            self,
            target_ap_mm: float,
            remaining_stock_mm: float,
            start_pass_num: int,
            current_diameter: float
    ) -> Tuple[List[Pass], float, int, float]:
        """
        Рассчитать черновые проходы без нумерации.
        Возвращает: (пассы, остаток_припуска, след_номер, текущий_диаметр)
        """
        rough_passes = []
        pass_num = start_pass_num

        if remaining_stock_mm <= target_ap_mm:
            ap_actual = remaining_stock_mm
            next_diameter = current_diameter - (2 * ap_actual) if self.config.is_external \
                else current_diameter + (2 * ap_actual)

            rough_passes.append(Pass(
                number=pass_num,
                type=PassType.ROUGHING,
                ap_mm=ap_actual,
                diameter_before_mm=current_diameter,
                diameter_after_mm=next_diameter
            ))
            remaining_stock_mm = 0
            current_diameter = next_diameter
            pass_num += 1

        else:
            optimal_ap = self._calculate_optimal_ap_for_roughing(remaining_stock_mm)
            optimal_ap = min(optimal_ap, self.config.max_ap_rough_mm)

            calculated_passes = math.ceil(remaining_stock_mm / optimal_ap)
            max_available_passes = self.config.preferred_max_passes - 2
            actual_passes = min(calculated_passes, max_available_passes)

            if actual_passes > 0:
                ap_per_pass = remaining_stock_mm / actual_passes

                for i in range(actual_passes):
                    if remaining_stock_mm <= 0:
                        break

                    if i == actual_passes - 1:
                        ap_actual = remaining_stock_mm
                    else:
                        if i < actual_passes // 2 and self.config.allow_variable_ap:
                            ap_actual = ap_per_pass * 1.2
                            ap_actual = min(ap_actual, self.config.max_ap_rough_mm)
                        else:
                            ap_actual = ap_per_pass

                    if ap_actual < self.config.min_ap_mm:
                        if rough_passes:
                            last_pass = rough_passes[-1]
                            last_pass.ap_mm += ap_actual
                            last_pass.diameter_after_mm = last_pass.diameter_before_mm - \
                                                          (2 * last_pass.ap_mm) if self.config.is_external else \
                                last_pass.diameter_before_mm + (2 * last_pass.ap_mm)
                        remaining_stock_mm = 0
                        break

                    next_diameter = current_diameter - (2 * ap_actual) if self.config.is_external \
                        else current_diameter + (2 * ap_actual)

                    rough_passes.append(Pass(
                        number=pass_num,
                        type=PassType.ROUGHING,
                        ap_mm=ap_actual,
                        diameter_before_mm=current_diameter,
                        diameter_after_mm=next_diameter
                    ))

                    current_diameter = next_diameter
                    remaining_stock_mm -= ap_actual
                    pass_num += 1

        return rough_passes, remaining_stock_mm, pass_num, current_diameter

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

        if remaining_stock_mm <= 0:
            return finish_passes

        # TODO: логика определения типа чистовой обработки должна быть выше
        finish_type = PassType.FINISHING
        target_ap = min(self.config.max_ap_finish_mm, remaining_stock_mm)

        if remaining_stock_mm <= target_ap * 1.5:
            ap_actual = remaining_stock_mm
            next_diameter = current_diameter - (2 * ap_actual) if self.config.is_external \
                else current_diameter + (2 * ap_actual)

            finish_passes.append(Pass(
                number=pass_num,
                type=finish_type,
                ap_mm=ap_actual,
                diameter_before_mm=current_diameter,
                diameter_after_mm=next_diameter
            ))

        else:
            # Получистовой проход
            semi_finish_ap = min(self.config.semi_finish_stock_mm, remaining_stock_mm * 0.7)
            next_diameter = current_diameter - (2 * semi_finish_ap) if self.config.is_external \
                else current_diameter + (2 * semi_finish_ap)

            finish_passes.append(Pass(
                number=pass_num,
                type=PassType.SEMI_FINISHING,
                ap_mm=semi_finish_ap,
                diameter_before_mm=current_diameter,
                diameter_after_mm=next_diameter
            ))

            # Чистовой проход
            pass_num += 1
            remaining_finish = remaining_stock_mm - semi_finish_ap
            current_diameter = next_diameter

            finish_ap = min(self.config.max_ap_finish_mm, remaining_finish)
            next_diameter = current_diameter - (2 * finish_ap) if self.config.is_external \
                else current_diameter + (2 * finish_ap)

            finish_passes.append(Pass(
                number=pass_num,
                type=PassType.FINISHING,
                ap_mm=finish_ap,
                diameter_before_mm=current_diameter,
                diameter_after_mm=next_diameter
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
        # Используем рекурсию с ограничением глубины для защиты от бесконечных циклов
        return self._generate_strategy_recursive(
            target_ap_mm=target_ap_mm,
            current_diameter=self.d_start,
            remaining_stock=self.total_stock_mm,
            start_pass_num=1,
            recursion_depth=0
        )

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
        """
        # Защита от бесконечной рекурсии
        if recursion_depth > 10:
            raise RuntimeError("Превышена глубина рекурсии при генерации стратегии")

        # Определяем целевую глубину резания
        if target_ap_mm is None:
            target_ap_mm = self._calculate_optimal_ap_for_roughing(remaining_stock)

            # TODO: логика определения типа операции должна быть выше
            if self.config.operation_type == 'roughing':
                target_ap_mm = min(target_ap_mm, self.config.max_ap_rough_mm)
            elif self.config.operation_type == 'semi_finishing':
                target_ap_mm = min(target_ap_mm, self.config.semi_finish_stock_mm)
            else:
                target_ap_mm = min(target_ap_mm, self.config.max_ap_finish_mm)

        # Ограничиваем целевую глубину
        target_ap_mm = min(target_ap_mm, self.config.max_ap_rough_mm)
        target_ap_mm = max(target_ap_mm, self.config.min_ap_mm)

        # 1. Рассчитываем черновые проходы
        rough_passes, remaining_after_rough, next_pass_num, current_d_after_rough = \
            self._calculate_roughing_passes(
                target_ap_mm=target_ap_mm,
                remaining_stock_mm=remaining_stock,
                start_pass_num=start_pass_num,
                current_diameter=current_diameter
            )

        all_passes = rough_passes

        # 2. Рассчитываем чистовые проходы (если нужно)
        if remaining_after_rough > 0 and (self.config.require_finish_pass or
                                          self.config.operation_type != 'roughing'):
            finish_passes = self._calculate_finishing_passes(
                current_diameter=current_d_after_rough,
                remaining_stock_mm=remaining_after_rough,
                start_pass_num=next_pass_num
            )

            all_passes.extend(finish_passes)

        # 3. Проверяем общее количество проходов
        total_passes = len(all_passes)

        # НЕ ДОПУСКАЕМ 50 ПРОХОДОВ!
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

        # TODO: коррекция диаметра должна быть в validator, не здесь
        # CORE только генерирует, не исправляет

        return all_passes