from dataclasses import dataclass
from enum import Enum


class ExperienceLevel(Enum):
    TRAINEE = "trainee"          # ученик
    JUNIOR = "junior"            # начинающий
    OPERATOR = "operator"        # уверенный оператор
    SENIOR = "senior"            # опытный
    MASTER = "master"            # технолог / мастер


@dataclass(frozen=True)
class OperatorExperience:
    """
    Доменная модель опыта оператора ЧПУ.
    Никакой логики UI / БД / бота здесь нет.
    """
    level: ExperienceLevel
    years: float                 # лет реальной работы
    machine_family_known: bool   # работал ли с этим типом станков
    material_known: bool         # работал ли с этим материалом
    tool_known: bool             # знаком ли с инструментом


class ExperienceCoefficient:
    """
    Доменные правила перевода опыта в коэффициенты риска.
    """

    BASE_BY_LEVEL = {
        ExperienceLevel.TRAINEE: 0.70,
        ExperienceLevel.JUNIOR: 0.85,
        ExperienceLevel.OPERATOR: 1.00,
        ExperienceLevel.SENIOR: 1.10,
        ExperienceLevel.MASTER: 1.20,
    }

    @classmethod
    def calculate(cls, exp: OperatorExperience) -> float:
        coef = cls.BASE_BY_LEVEL[exp.level]

        # стаж
        if exp.years < 1:
            coef *= 0.9
        elif exp.years > 5:
            coef *= 1.05

        # знание оборудования
        if not exp.machine_family_known:
            coef *= 0.9

        # знание материала
        if not exp.material_known:
            coef *= 0.92

        # знание инструмента
        if not exp.tool_known:
            coef *= 0.95

        # физические границы здравого смысла
        return round(max(0.6, min(coef, 1.25)), 3)
