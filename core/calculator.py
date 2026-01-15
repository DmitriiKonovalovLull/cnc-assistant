"""
Инженерный калькулятор для реальных расчётов обработки.
Основан на формулах резания и практическом опыте.
С поддержкой мультиязычности.
"""

import math


class CuttingCalculator:
    """Калькулятор для расчётов обработки с переводом."""

    def __init__(self, translator=None):
        self.translator = translator

    def _translate_note(self, note):
        """Переводит примечание если есть переводчик."""
        if not self.translator:
            return note

        # Словарь стандартных примечаний для перевода
        note_mapping = {
            # Русские примечания → ключи для перевода
            "Титан требует низких скоростей и малых подач.": "titanium_low_speed_feed",
            "Обязательно охлаждение!": "cooling_required",
            "Жёсткая система крепления.": "rigid_fixturing",
            "Можно работать на высоких оборотах.": "high_rpm_possible",
            "Острый инструмент с положительными углами.": "sharp_tool_positive_angles",
            "Титан - самый сложный для расточки": "titanium_most_difficult_boring",
            "Низкие скорости обязательны": "low_speeds_required",
            "Обильное охлаждение": "abundant_cooling",
            "Минимальный вылет (идеально < 5xD)": "minimal_overhang",
            "Умеренные параметры": "moderate_parameters",
            "СОЖ для отвода тепла": "coolant_heat_removal",
            "Контроль вибраций": "vibration_control",
            "Высокие скорости возможны": "high_speeds_possible",
            "Воздух для отвода стружки": "air_chip_removal",
            f"⚠️ Вылет {{}} мм слишком большой!": "overhang_too_large_warning",
            "Риск вибрации и поломки инструмента": "vibration_tool_break_risk",
            "Рекомендуется: уменьшить вылет или диаметр": "reduce_overhang_or_diameter",
            f"Глубина {{}} мм требует осторожности": "depth_requires_caution",
            "Стружкоотвод критически важен": "chip_removal_critical",
            "Сталь требует умеренных параметров": "steel_moderate_parameters",
            "Используйте СОЖ для охлаждения": "use_coolant_cooling",
            "Следить за стружкообразованием": "monitor_chip_formation",
            "Более высокие скорости для чистоты поверхности": "higher_speeds_surface_finish",
            "Острые пластины обязательны": "sharp_inserts_required",
            "Контроль налипания стружки": "control_chip_buildup",
            "Большие подачи и глубины": "large_feeds_depths",
            "Максимальные скорости для блеска": "max_speeds_for_shine",
        }

        # Ищем примечание в словаре
        for ru_note, key in note_mapping.items():
            if ru_note in note or note in ru_note:
                # Заменяем параметры в примечании
                if "{}" in ru_note:
                    # Извлекаем число из примечания
                    import re
                    number_match = re.search(r'\b(\d+)\b', note)
                    if number_match:
                        return self.translator.translate(key).format(number_match.group(1))
                return self.translator.translate(key)

        return note  # Возвращаем как есть если нет перевода

    def calculate_for_turning(self, context):
        """Рассчитывает параметры для токарной обработки."""
        if not context.material or not context.operation:
            return None

        material = context.material.lower()
        operation = context.operation.lower()
        mode = context.active_mode.lower() if context.active_mode else ""
        diameter = context.diameter

        # Расширенные коэффициенты для материалов (20+ материалов)
        material_coeffs = {
            # Стали
            'сталь': {'vc_rough': 100, 'vc_finish': 180, 'feed_rough': 0.3, 'feed_finish': 0.15},
            'сталь 20': {'vc_rough': 120, 'vc_finish': 200, 'feed_rough': 0.35, 'feed_finish': 0.15},
            'сталь 30': {'vc_rough': 110, 'vc_finish': 190, 'feed_rough': 0.32, 'feed_finish': 0.14},
            'сталь 45': {'vc_rough': 100, 'vc_finish': 180, 'feed_rough': 0.3, 'feed_finish': 0.12},
            'сталь 40х': {'vc_rough': 90, 'vc_finish': 160, 'feed_rough': 0.25, 'feed_finish': 0.1},
            'сталь 40хн': {'vc_rough': 80, 'vc_finish': 150, 'feed_rough': 0.22, 'feed_finish': 0.09},

            # Цветные металлы
            'алюминий': {'vc_rough': 300, 'vc_finish': 600, 'feed_rough': 0.5, 'feed_finish': 0.2},
            'алюминий д16т': {'vc_rough': 250, 'vc_finish': 500, 'feed_rough': 0.45, 'feed_finish': 0.18},

            # Титановые сплавы
            'титан': {'vc_rough': 40, 'vc_finish': 80, 'feed_rough': 0.15, 'feed_finish': 0.08},
            'титан вт6': {'vc_rough': 35, 'vc_finish': 70, 'feed_rough': 0.12, 'feed_finish': 0.06},
            'титан вт3': {'vc_rough': 38, 'vc_finish': 75, 'feed_rough': 0.14, 'feed_finish': 0.07},

            # Нержавеющие стали
            'нержавейка': {'vc_rough': 60, 'vc_finish': 100, 'feed_rough': 0.2, 'feed_finish': 0.1},
            'нержавеющая сталь': {'vc_rough': 60, 'vc_finish': 100, 'feed_rough': 0.2, 'feed_finish': 0.1},
            'нержавейка 304': {'vc_rough': 55, 'vc_finish': 90, 'feed_rough': 0.18, 'feed_finish': 0.09},
            'нержавейка 316': {'vc_rough': 50, 'vc_finish': 85, 'feed_rough': 0.16, 'feed_finish': 0.08},

            # Медь и сплавы
            'медь': {'vc_rough': 150, 'vc_finish': 300, 'feed_rough': 0.4, 'feed_finish': 0.15},
            'латунь': {'vc_rough': 200, 'vc_finish': 400, 'feed_rough': 0.45, 'feed_finish': 0.18},
            'бронза': {'vc_rough': 120, 'vc_finish': 250, 'feed_rough': 0.35, 'feed_finish': 0.14},

            # Чугуны
            'чугун': {'vc_rough': 80, 'vc_finish': 140, 'feed_rough': 0.25, 'feed_finish': 0.1},
            'чугун серый': {'vc_rough': 85, 'vc_finish': 150, 'feed_rough': 0.28, 'feed_finish': 0.12},
            'чугун ковкий': {'vc_rough': 90, 'vc_finish': 160, 'feed_rough': 0.3, 'feed_finish': 0.13},

            # Инструментальные стали
            'инструментальная сталь': {'vc_rough': 70, 'vc_finish': 120, 'feed_rough': 0.2, 'feed_finish': 0.08},
            'быстрорежущая сталь': {'vc_rough': 65, 'vc_finish': 110, 'feed_rough': 0.18, 'feed_finish': 0.07},

            # Пластики и другие
            'пластик': {'vc_rough': 200, 'vc_finish': 400, 'feed_rough': 0.3, 'feed_finish': 0.1},
            'дерево': {'vc_rough': 400, 'vc_finish': 800, 'feed_rough': 0.6, 'feed_finish': 0.25},
        }

        # Определяем материал
        coeff = None
        material_key = None

        for mat_key, mat_coeff in material_coeffs.items():
            if mat_key in material:
                coeff = mat_coeff
                material_key = mat_key
                break

        # Если не нашли точное совпадение, ищем частичное
        if not coeff:
            for mat_key, mat_coeff in material_coeffs.items():
                # Ищем вхождение ключа в название материала
                if any(part in material for part in mat_key.split()):
                    coeff = mat_coeff
                    material_key = mat_key
                    break

        # Если всё равно не нашли, используем стандартную сталь
        if not coeff:
            coeff = material_coeffs['сталь']
            material_key = 'сталь'

        # Определяем режим
        if 'чернов' in mode:
            vc_base = coeff['vc_rough']
            feed_base = coeff['feed_rough']
            ap_max = self._get_max_depth_of_cut(material_key, 'roughing')
        elif 'чистов' in mode:
            vc_base = coeff['vc_finish']
            feed_base = coeff['feed_finish']
            ap_max = self._get_max_depth_of_cut(material_key, 'finishing')
        else:
            vc_base = (coeff['vc_rough'] + coeff['vc_finish']) / 2
            feed_base = (coeff['feed_rough'] + coeff['feed_finish']) / 2
            ap_max = self._get_max_depth_of_cut(material_key, 'general')

        # Корректировка по диаметру
        vc_adjusted = vc_base
        feed_adjusted = feed_base

        if diameter:
            try:
                dia = float(str(diameter).replace(',', '.'))
                if dia < 20:
                    # Маленький диаметр - увеличиваем обороты
                    vc_adjusted = vc_base * 1.3
                    feed_adjusted = feed_base * 0.7
                elif dia > 100:
                    # Большой диаметр - уменьшаем обороты
                    vc_adjusted = vc_base * 0.7
                    feed_adjusted = feed_base * 0.8

                # Дополнительная коррекция для очень больших диаметров
                if dia > 200:
                    vc_adjusted = vc_adjusted * 0.8
                    feed_adjusted = feed_adjusted * 0.7
            except:
                pass

        # Расчёт оборотов (n = 1000 * Vc / (π * D))
        rpm = None
        if diameter:
            try:
                dia = float(str(diameter).replace(',', '.'))
                if dia > 0:
                    rpm = (1000 * vc_adjusted) / (math.pi * dia)
            except:
                pass

        # Дополнительные корректировки по материалу
        if 'титан' in material_key:
            feed_adjusted = feed_adjusted * 0.7  # уменьшаем подачу
        elif 'алюмин' in material_key:
            feed_adjusted = feed_adjusted * 1.2  # увеличиваем подачу
        elif 'нержавей' in material_key:
            vc_adjusted = vc_adjusted * 0.9  # немного уменьшаем скорость

        # Форматируем результат
        result = {
            'material': context.material,
            'operation': 'токарная обработка',
            'mode': mode,
            'diameter': str(diameter) if diameter else None,
            'cutting_speed': f"{vc_adjusted:.0f}",
            'feed_rate': f"{feed_adjusted:.3f}",
            'depth_of_cut': f"{ap_max:.1f}",
            'spindle_speed': f"{rpm:.0f}" if rpm else None,
            'notes': self._get_material_notes(material_key, mode, diameter)
        }

        # Переводим примечания если есть переводчик
        if self.translator:
            result['notes'] = [self._translate_note(note) for note in result['notes']]
            # Переводим название материала
            result['material'] = self.translator.translate_material(context.material)

        return result

    def calculate_for_boring(self, diameter, overhang, width, depth, material="сталь"):
        """
        Расчёт для расточки с большой длиной вылета.
        """

        # Нормализуем материал
        material_lower = material.lower()

        # Расширенные параметры материалов для расточки
        material_params = {
            # Стали
            'сталь': {
                'vc': 80, 'feed': 0.15, 'ap_max': 2.0,
                'notes': [
                    "Умеренные параметры",
                    "СОЖ для отвода тепла",
                    "Контроль вибраций"
                ]
            },
            'сталь 30': {
                'vc': 85, 'feed': 0.16, 'ap_max': 2.2,
                'notes': [
                    "Умеренные параметры",
                    "СОЖ для отвода тепла",
                    "Контроль вибраций"
                ]
            },
            'сталь 45': {
                'vc': 80, 'feed': 0.15, 'ap_max': 2.0,
                'notes': [
                    "Умеренные параметры",
                    "СОЖ для отвода тепла",
                    "Контроль вибраций"
                ]
            },

            # Алюминий
            'алюминий': {
                'vc': 200, 'feed': 0.3, 'ap_max': 3.0,
                'notes': [
                    "Высокие скорости возможны",
                    "Острый инструмент",
                    "Воздух для отвода стружки"
                ]
            },

            # Титан
            'титан': {
                'vc': 30, 'feed': 0.1, 'ap_max': 1.0,
                'notes': [
                    "Титан - самый сложный для расточки",
                    "Низкие скорости обязательны",
                    "Обильное охлаждение",
                    "Минимальный вылет (идеально < 5xD)"
                ]
            },

            # Нержавейка
            'нержавейка': {
                'vc': 50, 'feed': 0.12, 'ap_max': 1.5,
                'notes': [
                    "Низкие скорости",
                    "Обильное охлаждение",
                    "Контроль наростообразования"
                ]
            },

            # Медь и сплавы
            'медь': {
                'vc': 100, 'feed': 0.25, 'ap_max': 2.5,
                'notes': [
                    "Умеренные скорости",
                    "Хороший стружкоотвод",
                    "Острый инструмент"
                ]
            },
            'латунь': {
                'vc': 150, 'feed': 0.35, 'ap_max': 3.0,
                'notes': [
                    "Высокие скорости",
                    "Хорошая обрабатываемость",
                    "Минимальные усилия"
                ]
            },

            # Чугун
            'чугун': {
                'vc': 70, 'feed': 0.2, 'ap_max': 2.0,
                'notes': [
                    "Работа на сухую",
                    "Контроль пыли",
                    "Твёрдосплавный инструмент"
                ]
            },
        }

        # Получаем параметры материала
        params = None
        for mat_key, mat_params in material_params.items():
            if mat_key in material_lower:
                params = mat_params
                break

        # Если не нашли, используем сталь
        if not params:
            params = material_params['сталь']

        # Коэффициенты для расточки
        boring_coeff = 0.6  # расточка менее жёсткая

        # Корректировка по вылету
        overhang_factor = 1.0
        if overhang > 0:
            # Норма: вылет ≤ 4×диаметр инструмента
            tool_dia_approx = width / 2 if width > 0 else 10
            recommended_overhang = tool_dia_approx * 4

            if overhang > recommended_overhang:
                # Сильное уменьшение параметров при большом вылете
                reduction = (overhang / recommended_overhang) ** 2
                overhang_factor = 1 / min(reduction, 4)

        # Корректировка по глубине
        depth_factor = 1.0
        if depth > 50:
            depth_factor = 0.8
        if depth > 100:
            depth_factor = 0.6
        if depth > 200:
            depth_factor = 0.4

        # Корректировка по диаметру
        diameter_factor = 1.0
        if diameter > 100:
            diameter_factor = 0.9
        if diameter > 200:
            diameter_factor = 0.8

        # Расчёт итоговых параметров
        vc_final = params['vc'] * boring_coeff * overhang_factor * depth_factor * diameter_factor
        feed_final = params['feed'] * boring_coeff * overhang_factor * depth_factor * diameter_factor
        ap_final = params['ap_max'] * overhang_factor * depth_factor * diameter_factor

        # Расчёт оборотов
        rpm = (1000 * vc_final) / (math.pi * diameter) if diameter > 0 else 0

        # Расчёт машинного времени
        time_min = None
        if feed_final > 0 and rpm > 0:
            length = depth + 5  # +5 мм на подход/выход
            revs = length / feed_final
            time_min = revs / rpm

        # Определение жёсткости системы
        rigidity = "высокая"
        if overhang > 100:
            rigidity = "низкая (проблемы с вибрацией)"
        elif overhang > 50:
            rigidity = "средняя"

        # Расчёт количества проходов
        passes = math.ceil(depth / ap_final) if ap_final > 0 and depth > 0 else 1

        # Форматируем результат
        result = {
            'operation': 'расточка',
            'diameter': f"{diameter}",
            'overhang': f"{overhang}",
            'width': f"{width}",
            'depth': f"{depth}",
            'material': material,
            'cutting_speed': f"{vc_final:.0f}",
            'feed_rate': f"{feed_final:.3f}",
            'depth_per_pass': f"{ap_final:.2f}",
            'spindle_speed': f"{rpm:.0f}",
            'passes': passes,
            'rigidity': rigidity,
            'estimated_time': f"{time_min:.1f}" if time_min else None,
            'notes': params['notes'].copy()
        }

        # Дополнительные предупреждения
        if overhang > 100:
            result['notes'].append(f"⚠️ Вылет {overhang} мм слишком большой!")
            result['notes'].append("Риск вибрации и поломки инструмента")
            result['notes'].append("Рекомендуется: уменьшить вылет или диаметр")

        if depth > 50:
            result['notes'].append(f"Глубина {depth} мм требует осторожности")
            result['notes'].append("Стружкоотвод критически важен")

        if diameter > 150:
            result['notes'].append(f"Большой диаметр {diameter} мм - контроль биения")

        # Переводим примечания если есть переводчик
        if self.translator:
            result['notes'] = [self._translate_note(note) for note in result['notes']]
            # Переводим материал
            result['material'] = self.translator.translate_material(material)
            # Переводим жёсткость
            if rigidity == "высокая":
                result['rigidity'] = self.translator.translate("high_rigidity")
            elif rigidity == "средняя":
                result['rigidity'] = self.translator.translate("medium_rigidity")
            else:
                result['rigidity'] = self.translator.translate("low_rigidity")

        return result

    def _get_max_depth_of_cut(self, material, mode):
        """Возвращает максимальную глубину резания для материала и режима."""
        depth_data = {
            # Материал: [черновая, чистовая, общая]
            'сталь': [5.0, 0.5, 2.0],
            'сталь 45': [4.0, 0.4, 1.8],
            'сталь 30': [4.5, 0.45, 1.9],
            'алюминий': [8.0, 1.0, 3.0],
            'титан': [2.0, 0.3, 0.8],
            'нержавейка': [3.0, 0.4, 1.2],
            'медь': [6.0, 0.8, 2.5],
            'латунь': [7.0, 1.0, 3.0],
            'чугун': [4.0, 0.5, 1.5],
        }

        # Ищем материал
        for mat_key, depths in depth_data.items():
            if mat_key in material:
                if mode == 'roughing':
                    return depths[0]
                elif mode == 'finishing':
                    return depths[1]
                else:
                    return depths[2]

        # По умолчанию
        return 2.0

    def _get_material_notes(self, material, mode, diameter=None):
        """Возвращает примечания для материала."""
        notes = []

        # Общие примечания по материалам
        if 'титан' in material:
            notes.append("Титан требует низких скоростей и малых подач.")
            notes.append("Обязательно охлаждение!")
            notes.append("Жёсткая система крепления.")

        elif 'алюмин' in material:
            notes.append("Можно работать на высоких оборотах.")
            notes.append("Острый инструмент с положительными углами.")

            if diameter:
                try:
                    dia = float(str(diameter).replace(',', '.'))
                    if dia < 10:
                        notes.append("Маленький диаметр - высокие обороты, осторожность с вибрациями.")
                except:
                    pass

        elif 'сталь' in material:
            notes.append("Сталь требует умеренных параметров.")
            notes.append("Используйте СОЖ для охлаждения.")
            notes.append("Следить за стружкообразованием.")

        elif 'нержавей' in material:
            notes.append("Нержавеющая сталь склонна к наростообразованию.")
            notes.append("Низкие скорости, хорошее охлаждение.")

        elif 'медь' in material or 'латунь' in material:
            notes.append("Хорошая обрабатываемость.")
            notes.append("Контроль налипания стружки.")

        elif 'чугун' in material:
            notes.append("Можно работать на сухую.")
            notes.append("Твёрдосплавный инструмент.")

        # Примечания по режиму
        if 'чернов' in mode:
            notes.append("Черновая обработка - максимальный съём материала.")

        elif 'чистов' in mode:
            notes.append("Чистовая обработка - высокая точность и качество поверхности.")
            notes.append("Минимальная подача на последнем проходе.")

        return notes

    def format_calculation(self, result, translator=None):
        """Форматирует результат расчёта с переводом."""
        if not result:
            return translator.translate("calculation_failed",
                                        "Не удалось выполнить расчёт.") if translator else "Не удалось выполнить расчёт."

        # Используем переданный переводчик или свой
        trans = translator or self.translator

        lines = []
        lines.append("🔢 **" + (trans.translate("calculation_results") if trans else "Результаты расчёта") + ":**")
        lines.append("")

        # Исходные данные
        lines.append("📊 **" + (trans.translate("input_data") if trans else "Исходные данные") + ":**")

        display_order = ['material', 'operation', 'mode', 'diameter', 'overhang', 'width', 'depth']

        for key in display_order:
            if key in result and result[key]:
                label = trans.translate(key) if trans else key.replace('_', ' ').title()
                lines.append(f"• {label}: {result[key]}")

        lines.append("")

        # Режимы обработки
        lines.append("⚙️ **" + (trans.translate("processing_parameters") if trans else "Режимы обработки") + ":**")

        cutting_params = [
            ('cutting_speed', 'м/мин'),
            ('feed_rate', 'мм/об'),
            ('depth_per_pass', 'мм'),
            ('depth_of_cut', 'мм'),
            ('spindle_speed', 'об/мин'),
            ('passes', ''),
            ('rigidity', ''),
            ('estimated_time', 'мин')
        ]

        for param, unit in cutting_params:
            if param in result and result[param]:
                label = trans.translate(param) if trans else param.replace('_', ' ').title()
                value = result[param]

                # Добавляем единицы измерения если их нет
                if unit and not any(unit_part in str(value) for unit_part in ['мм', 'м/мин', 'об/мин', 'мин']):
                    value = f"{value} {unit}"

                lines.append(f"• {label}: {value}")

        lines.append("")

        # Примечания
        if 'notes' in result and result['notes']:
            lines.append("💡 **" + (trans.translate("important_notes") if trans else "Важные замечания") + ":**")
            for note in result['notes']:
                lines.append(f"• {note}")

        lines.append("")
        warning = trans.translate(
            "calculated_values_note") if trans else "Это расчётные значения. Корректируй по результатам пробного прохода."
        lines.append("⚠️ **" + (trans.translate("remember") if trans else "Помни") + ":** " + warning)

        return "\n".join(lines)