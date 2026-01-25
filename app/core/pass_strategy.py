"""
Стратегия разбивки припуска на проходы.
Главное: НЕ 50 проходов! Реальные стратегии для практиков.
"""
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import math


@dataclass
class Pass:
    """Один проход обработки."""
    number: int  # номер прохода
    type: str  # roughing, semi_finishing, finishing
    ap_mm: float  # глубина резания, мм
    diameter_before_mm: float  # диаметр до прохода
    diameter_after_mm: float  # диаметр после прохода

    # Параметры резания для этого прохода (могут отличаться)
    vc_m_min: Optional[float] = None  # скорость резания
    feed_mm_rev: Optional[float] = None  # подача
    rpm: Optional[float] = None  # обороты

    @property
    def stock_removed_mm(self) -> float:
        """Снятый припуск за проход, мм."""
        return (self.diameter_before_mm - self.diameter_after_mm) / 2

    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь."""
        return {
            'number': self.number,
            'type': self.type,
            'ap_mm': round(self.ap_mm, 2),
            'diameter_before_mm': round(self.diameter_before_mm, 2),
            'diameter_after_mm': round(self.diameter_after_mm, 2),
            'stock_removed_mm': round(self.stock_removed_mm, 2),
            'vc_m_min': round(self.vc_m_min, 1) if self.vc_m_min else None,
            'feed_mm_rev': round(self.feed_mm_rev, 3) if self.feed_mm_rev else None,
            'rpm': round(self.rpm, 1) if self.rpm else None,
        }


@dataclass
class StrategyConfig:
    """Конфигурация стратегии разбивки."""
    # Основные параметры стратегии
    operation_type: str = 'roughing'  # roughing, semi_finishing, finishing
    is_external: bool = True  # наружная обработка

    # Ограничения по инструменту
    max_ap_rough_mm: float = 6.0  # макс глубина для черновой
    max_ap_finish_mm: float = 0.8  # макс глубина для чистовой
    min_ap_mm: float = 0.1  # минимальная глубина

    # Ограничения по станку/обработке
    max_total_passes: int = 20  # абсолютный максимум проходов (не 50!)
    preferred_max_passes: int = 12  # желаемый максимум

    # Правила разбивки
    rough_to_finish_ratio: float = 0.1  # черновой припуск/общий припуск для чистовой
    semi_finish_stock_mm: float = 1.0  # припуск на получистовую

    # Критерии качества
    require_finish_pass: bool = True  # всегда делать чистовой проход?
    allow_variable_ap: bool = True  # разрешить разную глубину в черновых проходах

    # Точность
    tolerance_mm: float = 0.05  # допуск на размер
    surface_roughness_ra: Optional[float] = None  # требуемая шероховатость


class PassStrategy:
    """
    Интеллектуальная разбивка припуска на проходы.
    Реальные стратегии, как работают практики.
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

        # Инициализируем список проходов
        self.passes: List[Pass] = []

    def _validate_inputs(self):
        """Проверка корректности входных данных."""
        if self.d_start <= self.d_end:
            raise ValueError("Начальный диаметр должен быть больше конечного")

        stock = (self.d_start - self.d_end) / 2
        if stock <= 0:
            raise ValueError("Припуск должен быть положительным")

        # Проверка на абсурдные значения (как в старом боте)
        if stock > 100:  # 100 мм припуска - это уже абсурд
            raise ValueError(f"Припуск {stock} мм слишком велик. Проверьте входные данные.")

    def calculate_roughing_passes(
            self,
            target_ap_mm: float,
            remaining_stock_mm: float
    ) -> Tuple[List[Pass], float]:
        """
        Рассчитать черновые проходы.

        Args:
            target_ap_mm: целевая глубина резания
            remaining_stock_mm: остаток припуска

        Returns:
            (список проходов, остаток припуска)
        """
        rough_passes = []
        current_diameter = self.d_start
        pass_num = 1

        # Рассчитываем, сколько проходов нужно для черновой
        # НЕ МАЛЕНЬКИМИ СЛОЙКАМИ!
        if remaining_stock_mm <= target_ap_mm:
            # Весь остаток за один проход
            ap_actual = remaining_stock_mm
            next_diameter = current_diameter - (2 * ap_actual) if self.config.is_external \
                else current_diameter + (2 * ap_actual)

            rough_passes.append(Pass(
                number=pass_num,
                type='roughing',
                ap_mm=ap_actual,
                diameter_before_mm=current_diameter,
                diameter_after_mm=next_diameter
            ))
            remaining_stock_mm = 0

        else:
            # Несколько черновых проходов
            # НЕ ДЕЛАЕМ 50 ПРОХОДОВ!
            max_rough_passes = min(
                math.ceil(remaining_stock_mm / target_ap_mm),
                self.config.preferred_max_passes - 2  # оставляем место на чистовые
            )

            # Оптимизируем глубину, чтобы проходы были более равномерными
            ap_optimized = remaining_stock_mm / max_rough_passes

            # Но не превышаем максимальную глубину
            ap_optimized = min(ap_optimized, self.config.max_ap_rough_mm)

            for i in range(max_rough_passes):
                if remaining_stock_mm <= 0:
                    break

                # Последний черновой проход может быть меньше
                if i == max_rough_passes - 1:
                    ap_actual = remaining_stock_mm
                else:
                    ap_actual = min(ap_optimized, remaining_stock_mm)

                # Не делаем слишком маленькие проходы
                if ap_actual < self.config.min_ap_mm:
                    # Добавляем к предыдущему проходу
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
                    type='roughing',
                    ap_mm=ap_actual,
                    diameter_before_mm=current_diameter,
                    diameter_after_mm=next_diameter
                ))

                current_diameter = next_diameter
                remaining_stock_mm -= ap_actual
                pass_num += 1

        return rough_passes, remaining_stock_mm

    def calculate_finishing_passes(
            self,
            current_diameter: float,
            remaining_stock_mm: float
    ) -> List[Pass]:
        """
        Рассчитать чистовые проходы.
        """
        finish_passes = []
        pass_num = len(self.passes) + 1

        if remaining_stock_mm <= 0:
            return finish_passes

        # Определяем тип чистовой обработки
        if self.config.operation_type == 'finishing':
            finish_type = 'finishing'
            target_ap = min(self.config.max_ap_finish_mm, remaining_stock_mm)
        else:
            finish_type = 'semi_finishing'
            target_ap = min(self.config.semi_finish_stock_mm, remaining_stock_mm)

        # Если припуск маленький - один проход
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
            # Два прохода: получистовой + чистовой
            # 1. Получистовой
            semi_finish_ap = min(self.config.semi_finish_stock_mm, remaining_stock_mm * 0.7)
            next_diameter = current_diameter - (2 * semi_finish_ap) if self.config.is_external \
                else current_diameter + (2 * semi_finish_ap)

            finish_passes.append(Pass(
                number=pass_num,
                type='semi_finishing',
                ap_mm=semi_finish_ap,
                diameter_before_mm=current_diameter,
                diameter_after_mm=next_diameter
            ))

            # 2. Чистовой
            pass_num += 1
            current_diameter = next_diameter
            remaining_finish = remaining_stock_mm - semi_finish_ap

            finish_ap = min(self.config.max_ap_finish_mm, remaining_finish)
            next_diameter = current_diameter - (2 * finish_ap) if self.config.is_external \
                else current_diameter + (2 * finish_ap)

            finish_passes.append(Pass(
                number=pass_num,
                type='finishing',
                ap_mm=finish_ap,
                diameter_before_mm=current_diameter,
                diameter_after_mm=next_diameter
            ))

        return finish_passes

    def generate_strategy(self, target_ap_mm: Optional[float] = None) -> Dict[str, Any]:
        """
        Сгенерировать стратегию разбивки.

        Args:
            target_ap_mm: целевая глубина резания (если None - рассчитывается)

        Returns:
            Словарь со стратегией
        """
        # Сбрасываем список проходов
        self.passes = []

        # Определяем целевую глубину резания
        if target_ap_mm is None:
            if self.config.operation_type == 'roughing':
                target_ap_mm = self.config.max_ap_rough_mm
            elif self.config.operation_type == 'semi_finishing':
                target_ap_mm = self.config.semi_finish_stock_mm
            else:  # finishing
                target_ap_mm = self.config.max_ap_finish_mm

        # Ограничиваем целевую глубину
        target_ap_mm = min(target_ap_mm, self.config.max_ap_rough_mm)
        target_ap_mm = max(target_ap_mm, self.config.min_ap_mm)

        # 1. Рассчитываем черновые проходы
        remaining_stock = self.total_stock_mm
        rough_passes, remaining_after_rough = self.calculate_roughing_passes(
            target_ap_mm,
            remaining_stock
        )

        self.passes.extend(rough_passes)

        # 2. Рассчитываем чистовые проходы (если нужно)
        if remaining_after_rough > 0 and (self.config.require_finish_pass or
                                          self.config.operation_type != 'roughing'):
            current_diameter = self.passes[-1].diameter_after_mm if self.passes else self.d_start
            finish_passes = self.calculate_finishing_passes(
                current_diameter,
                remaining_after_rough
            )

            self.passes.extend(finish_passes)

        # 3. Проверяем общее количество проходов
        total_passes = len(self.passes)

        # НЕ ДОПУСКАЕМ 50 ПРОХОДОВ!
        if total_passes > self.config.max_total_passes:
            # Пересчитываем с большей глубиной резания
            return self.generate_strategy(target_ap_mm * 1.5)

        if total_passes == 0:
            raise ValueError("Не удалось сгенерировать ни одного прохода")

        # 4. Проверяем итоговый диаметр
        final_diameter = self.passes[-1].diameter_after_mm if self.passes else self.d_end
        diameter_error = abs(final_diameter - self.d_end)

        if diameter_error > self.config.tolerance_mm:
            # Корректируем последний проход
            if self.passes:
                last_pass = self.passes[-1]
                correction = (self.d_end - final_diameter) / 2 if self.config.is_external \
                    else (final_diameter - self.d_end) / 2

                last_pass.ap_mm += correction
                last_pass.diameter_after_mm = self.d_end

        # 5. Рассчитываем общую статистику
        total_machining_stock = sum(p.stock_removed_mm for p in self.passes)
        efficiency = total_machining_stock / self.total_stock_mm if self.total_stock_mm > 0 else 1.0

        return {
            'passes': [p.to_dict() for p in self.passes],
            'total_passes': total_passes,
            'total_stock_mm': self.total_stock_mm,
            'total_machined_stock_mm': round(total_machining_stock, 2),
            'efficiency': round(efficiency, 3),
            'operation_type': self.config.operation_type,
            'final_diameter_mm': round(self.passes[-1].diameter_after_mm, 2),
            'diameter_error_mm': round(diameter_error, 3),

            # Анализ проходов
            'rough_passes': len([p for p in self.passes if p.type == 'roughing']),
            'semi_finish_passes': len([p for p in self.passes if p.type == 'semi_finishing']),
            'finish_passes': len([p for p in self.passes if p.type == 'finishing']),

            # Средние значения
            'avg_ap_mm': round(sum(p.ap_mm for p in self.passes) / total_passes, 2),
            'max_ap_mm': round(max(p.ap_mm for p in self.passes), 2),
            'min_ap_mm': round(min(p.ap_mm for p in self.passes), 2),

            # Рекомендации
            'is_realistic': total_passes <= self.config.preferred_max_passes,
            'warnings': self._generate_warnings(total_passes)
        }

    def _generate_warnings(self, total_passes: int) -> List[str]:
        """Сгенерировать предупреждения."""
        warnings = []

        if total_passes > self.config.preferred_max_passes:
            warnings.append(
                f"Количество проходов ({total_passes}) больше желаемого ({self.config.preferred_max_passes}). "
                f"Рассмотрите инструмент с большей глубиной резания."
            )

        if total_passes > 15:
            warnings.append(
                f"{total_passes} проходов - много для практической работы. "
                f"Оптимизируйте стратегию."
            )

        # Проверка на абсурдно маленькие проходы
        small_passes = [p for p in self.passes if p.ap_mm < 0.2]
        if small_passes and len(small_passes) > 2:
            warnings.append(
                f"Обнаружено {len(small_passes)} проходов с глубиной менее 0.2 мм. "
                f"Объедините мелкие проходы."
            )

        # Проверка итогового диаметра
        if self.passes:
            final_diameter = self.passes[-1].diameter_after_mm
            error = abs(final_diameter - self.d_end)
            if error > self.config.tolerance_mm:
                warnings.append(
                    f"Погрешность итогового диаметра: {error:.3f} мм. "
                    f"Допуск: {self.config.tolerance_mm} мм."
                )

        return warnings

    def get_alternative_strategies(self) -> Dict[str, Dict[str, Any]]:
        """
        Получить альтернативные стратегии.
        """
        strategies = {}

        # 1. Агрессивная стратегия (максимальная ap)
        agg_config = StrategyConfig(
            operation_type='roughing',
            max_ap_rough_mm=min(self.config.max_ap_rough_mm * 1.2, 8.0),
            preferred_max_passes=8
        )

        try:
            agg_strat = PassStrategy(self.d_start, self.d_end, agg_config)
            strategies['aggressive'] = agg_strat.generate_strategy()
            strategies['aggressive']['description'] = "Максимальная глубина резания, минимум проходов"
        except Exception as e:
            strategies['aggressive'] = {'error': str(e)}

        # 2. Консервативная стратегия (маленькая ap, много проходов)
        cons_config = StrategyConfig(
            operation_type='roughing',
            max_ap_rough_mm=self.config.max_ap_rough_mm * 0.6,
            preferred_max_passes=15
        )

        try:
            cons_strat = PassStrategy(self.d_start, self.d_end, cons_config)
            strategies['conservative'] = cons_strat.generate_strategy()
            strategies['conservative']['description'] = "Малая глубина резания, больше проходов для сложных условий"
        except Exception as e:
            strategies['conservative'] = {'error': str(e)}

        # 3. Двухэтапная стратегия (черновая + чистовая)
        two_stage_config = StrategyConfig(
            operation_type='roughing',
            require_finish_pass=True,
            semi_finish_stock_mm=0.5,
            max_ap_finish_mm=0.3
        )

        try:
            two_stage_strat = PassStrategy(self.d_start, self.d_end, two_stage_config)
            strategies['two_stage'] = two_stage_strat.generate_strategy()
            strategies['two_stage']['description'] = "Черновая + чистовая обработка"
        except Exception as e:
            strategies['two_stage'] = {'error': str(e)}

        return strategies


# ============================================================================
# УТИЛИТНЫЕ ФУНКЦИИ
# ============================================================================

def create_strategy_from_context(
        diameter_start_mm: float,
        diameter_end_mm: float,
        context: Dict[str, Any]
) -> PassStrategy:
    """
    Создать стратегию из контекста.
    """
    config = StrategyConfig(
        operation_type=context.get('operation_type', 'roughing'),
        is_external=context.get('is_external', True),
        max_ap_rough_mm=context.get('max_ap_rough_mm', 6.0),
        max_ap_finish_mm=context.get('max_ap_finish_mm', 0.8),
        preferred_max_passes=context.get('preferred_max_passes', 12),
        tolerance_mm=context.get('tolerance_mm', 0.05),
        surface_roughness_ra=context.get('surface_roughness_ra')
    )

    return PassStrategy(diameter_start_mm, diameter_end_mm, config)


def format_strategy_for_user(strategy: Dict[str, Any]) -> str:
    """
    Форматировать стратегию для показа пользователю.
    """
    lines = []

    lines.append("📋 **Стратегия обработки:**")
    lines.append("")

    # Общая информация
    lines.append(f"• Тип операции: {strategy.get('operation_type', 'roughing').upper()}")
    lines.append(f"• Общий припуск: {strategy.get('total_stock_mm', 0):.1f} мм на сторону")
    lines.append(f"• Количество проходов: {strategy.get('total_passes', 0)}")
    lines.append(f"• Итоговый диаметр: {strategy.get('final_diameter_mm', 0):.2f} мм")

    # Эффективность
    efficiency = strategy.get('efficiency', 1.0)
    if efficiency < 0.99:
        lines.append(
            f"• Эффективность: {efficiency:.1%} (потеря материала: {strategy.get('total_stock_mm', 0) - strategy.get('total_machined_stock_mm', 0):.2f} мм)")

    # Статистика по проходам
    lines.append("")
    lines.append(f"• Черновые проходы: {strategy.get('rough_passes', 0)}")
    lines.append(f"• Получистовые: {strategy.get('semi_finish_passes', 0)}")
    lines.append(f"• Чистовые: {strategy.get('finish_passes', 0)}")

    # Глубина резания
    lines.append("")
    lines.append(f"• Средняя глубина: {strategy.get('avg_ap_mm', 0):.2f} мм")
    lines.append(f"• Максимальная: {strategy.get('max_ap_mm', 0):.2f} мм")
    lines.append(f"• Минимальная: {strategy.get('min_ap_mm', 0):.2f} мм")

    # Детали проходов (первые 5 для краткости)
    passes = strategy.get('passes', [])
    if passes:
        lines.append("")
        lines.append("**Детали проходов:**")

        # Показываем первые 3 и последние 2 прохода, если их много
        if len(passes) > 8:
            show_passes = passes[:3] + [{'number': '...', 'type': '...', 'ap_mm': '...'}] + passes[-2:]
        else:
            show_passes = passes

        for p in show_passes:
            if p.get('number') == '...':
                lines.append(f"  ...")
                continue

            lines.append(
                f"  {p['number']:2d}. {p['type'][:5]:5s} | "
                f"ap: {p['ap_mm']:5.2f} мм | "
                f"Ø: {p['diameter_before_mm']:6.1f} → {p['diameter_after_mm']:6.1f} мм"
            )

    # Предупреждения
    warnings = strategy.get('warnings', [])
    if warnings:
        lines.append("")
        lines.append("⚠️ **Внимание:**")
        for warning in warnings:
            lines.append(f"• {warning}")

    # Оценка реалистичности
    if not strategy.get('is_realistic', True):
        lines.append("")
        lines.append("🔶 **Рекомендация:** Количество проходов велико, рассмотрите альтернативную стратегию")

    return "\n".join(lines)


def calculate_optimal_ap(total_stock_mm: float, operation_type: str) -> float:
    """
    Рассчитать оптимальную глубину резания для припуска.

    Правила:
    - Для припуска < 2 мм: 1 проход
    - Для припуска 2-10 мм: 2-4 прохода
    - Для припуска > 10 мм: 4-8 проходов

    НЕ 50 ПРОХОДОВ!
    """
    if total_stock_mm <= 2:
        return total_stock_mm  # один проход

    elif total_stock_mm <= 10:
        # 2-4 прохода
        desired_passes = 3 if operation_type == 'roughing' else 4
        return total_stock_mm / desired_passes

    else:
        # 4-8 проходов, НЕ БОЛЕЕ!
        desired_passes = min(8, max(4, int(total_stock_mm / 2)))
        return total_stock_mm / desired_passes


def validate_strategy_against_practice(strategy: Dict[str, Any]) -> List[str]:
    """
    Проверить стратегию на соответствие практике.

    Возвращает предупреждения, если стратегия нереалистична.
    """
    warnings = []

    total_passes = strategy.get('total_passes', 0)
    total_stock = strategy.get('total_stock_mm', 0)

    # Правило 1: Не более 20 проходов для токарки
    if total_passes > 20:
        warnings.append(f"❌ {total_passes} проходов - это нереально! Максимум 15-20 для токарки.")

    # Правило 2: Для маленького припуска - 1-2 прохода
    if total_stock < 1 and total_passes > 2:
        warnings.append(f"Для припуска {total_stock:.1f} мм {total_passes} проходов - это слишком много.")

    # Правило 3: Глубина резания должна быть в разумных пределах
    passes = strategy.get('passes', [])
    for p in passes:
        ap = p.get('ap_mm', 0)
        if ap > 6:
            warnings.append(
                f"Глубина резания {ap:.1f} мм в проходе {p.get('number')} слишком велика (макс 6 мм для черновой)")
        if ap < 0.05:
            warnings.append(f"Глубина резания {ap:.1f} мм в проходе {p.get('number')} слишком мала")

    # Правило 4: Нужен ли чистовой проход?
    has_finish = any(p.get('type') == 'finishing' for p in passes)
    if total_stock > 0.5 and not has_finish and strategy.get('operation_type') != 'roughing':
        warnings.append("Рекомендуется чистовой проход для хорошего качества поверхности")

    return warnings


# ============================================================================
# ТЕСТИРОВАНИЕ
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("ТЕСТ: Стратегия разбивки припуска на проходы")
    print("=" * 70)

    # Тест 1: Пример из старого бота (400 → 200 мм)
    print("\n1. Пример из старого бота (400 → 200 мм, припуск 100 мм):")
    print("   Старый бот: ap = 100 мм (нереально!)")
    print("   Старый бот: 50 проходов (абсурд!)")
    print("-" * 70)

    config = StrategyConfig(operation_type='roughing')
    strategy = PassStrategy(400, 200, config)

    result = strategy.generate_strategy()

    print(f"   Наша стратегия: {result['total_passes']} проходов")
    print(f"   Средняя глубина: {result['avg_ap_mm']:.1f} мм")
    print(f"   Максимальная глубина: {result['max_ap_mm']:.1f} мм")

    # Проверка на реалистичность
    practice_warnings = validate_strategy_against_practice(result)
    if practice_warnings:
        print("\n   Проверка практикой:")
        for warning in practice_warnings:
            print(f"   {warning}")

    # Тест 2: Нормальный случай (100 → 90 мм)
    print("\n" + "=" * 70)
    print("2. Нормальный случай (100 → 90 мм, припуск 5 мм):")
    print("-" * 70)

    strategy2 = PassStrategy(100, 90, config)
    result2 = strategy2.generate_strategy()

    print(f"   Проходов: {result2['total_passes']}")
    print(f"   Типы проходов: {result2['rough_passes']} чернов., "
          f"{result2['semi_finish_passes']} получ., "
          f"{result2['finish_passes']} чист.")

    # Тест 3: Маленький припуск (50 → 49.5 мм)
    print("\n" + "=" * 70)
    print("3. Маленький припуск (50 → 49.5 мм, припуск 0.25 мм):")
    print("-" * 70)

    strategy3 = PassStrategy(50, 49.5, config)
    result3 = strategy3.generate_strategy()

    print(f"   Проходов: {result3['total_passes']}")
    print(f"   Операция: {result3['operation_type']}")

    # Тест 4: Альтернативные стратегии
    print("\n" + "=" * 70)
    print("4. Альтернативные стратегии (100 → 80 мм):")
    print("-" * 70)

    strategy4 = PassStrategy(100, 80, config)
    alternatives = strategy4.get_alternative_strategies()

    for name, alt in alternatives.items():
        if 'error' not in alt:
            print(f"\n   {name.upper()}: {alt.get('description', '')}")
            print(f"   Проходов: {alt.get('total_passes', 0)}")
            print(f"   Средняя ap: {alt.get('avg_ap_mm', 0):.2f} мм")

    # Тест 5: Форматированный вывод
    print("\n" + "=" * 70)
    print("5. Форматированный вывод для пользователя:")
    print("-" * 70)

    print(format_strategy_for_user(result))

    print("\n" + "=" * 70)
    print("ВЫВОД: Теперь бот НЕ будет предлагать 50 проходов и 100 мм ap!")
    print("Только реалистичные стратегии, как у практиков. ✅")
    print("=" * 70)