"""
Мультиязычная поддержка для бота.
Поддерживает русский, английский, китайский.
"""


class Translator:
    """Переводчик параметров обработки."""

    # Словари перевода
    TRANSLATIONS = {
        'ru': {  # Русский (по умолчанию)
            'material': 'Материал',
            'operation': 'Операция',
            'mode': 'Режим',
            'diameter': 'Диаметр',
            'overhang': 'Вылет',
            'width': 'Ширина',
            'depth': 'Глубина',
            'cutting_speed': 'Скорость резания',
            'feed_rate': 'Подача',
            'depth_of_cut': 'Глубина резания',
            'depth_per_pass': 'Глубина за проход',
            'spindle_speed': 'Обороты шпинделя',
            'passes': 'Количество проходов',
            'rigidity': 'Жёсткость системы',
            'estimated_time': 'Примерное время',
            'notes': 'Примечания',
            'mm': 'мм',
            'min': 'мин',
            'm_min': 'м/мин',
            'mm_rev': 'мм/об',

            # Режимы
            'roughing': 'Черновая обработка',
            'finishing': 'Чистовая обработка',

            # Материалы (RU названия)
            'steel': 'Сталь',
            'steel_45': 'Сталь 45',
            'steel_30': 'Сталь 30',
            'aluminum': 'Алюминий',
            'titanium': 'Титан',
            'stainless_steel': 'Нержавеющая сталь',
            'brass': 'Латунь',
            'copper': 'Медь',
            'bronze': 'Бронза',
            'cast_iron': 'Чугун',
            'tool_steel': 'Инструментальная сталь',

            # Операции
            'turning': 'Токарная обработка',
            'milling': 'Фрезерование',
            'drilling': 'Сверление',
            'boring': 'Расточка',
            'threading': 'Нарезание резьбы',
        },

        'en': {  # Английский
            'material': 'Material',
            'operation': 'Operation',
            'mode': 'Mode',
            'diameter': 'Diameter',
            'overhang': 'Overhang',
            'width': 'Width',
            'depth': 'Depth',
            'cutting_speed': 'Cutting speed',
            'feed_rate': 'Feed rate',
            'depth_of_cut': 'Depth of cut',
            'depth_per_pass': 'Depth per pass',
            'spindle_speed': 'Spindle speed',
            'passes': 'Number of passes',
            'rigidity': 'System rigidity',
            'estimated_time': 'Estimated time',
            'notes': 'Notes',
            'mm': 'mm',
            'min': 'min',
            'm_min': 'm/min',
            'mm_rev': 'mm/rev',

            # Режимы
            'roughing': 'Roughing',
            'finishing': 'Finishing',

            # Материалы (EN названия)
            'steel': 'Steel',
            'steel_45': 'Steel 45',
            'steel_30': 'Steel 30',
            'aluminum': 'Aluminum',
            'titanium': 'Titanium',
            'stainless_steel': 'Stainless steel',
            'brass': 'Brass',
            'copper': 'Copper',
            'bronze': 'Bronze',
            'cast_iron': 'Cast iron',
            'tool_steel': 'Tool steel',

            # Операции
            'turning': 'Turning',
            'milling': 'Milling',
            'drilling': 'Drilling',
            'boring': 'Boring',
            'threading': 'Threading',
        },

        'zh': {  # Китайский
            'material': '材料',
            'operation': '操作',
            'mode': '模式',
            'diameter': '直径',
            'overhang': '悬伸',
            'width': '宽度',
            'depth': '深度',
            'cutting_speed': '切削速度',
            'feed_rate': '进给率',
            'depth_of_cut': '切削深度',
            'depth_per_pass': '每道次深度',
            'spindle_speed': '主轴转速',
            'passes': '道次数量',
            'rigidity': '系统刚性',
            'estimated_time': '预计时间',
            'notes': '注意事项',
            'mm': '毫米',
            'min': '分钟',
            'm_min': '米/分钟',
            'mm_rev': '毫米/转',

            # Режимы
            'roughing': '粗加工',
            'finishing': '精加工',

            # Материалы (ZH названия)
            'steel': '钢',
            'steel_45': '45号钢',
            'steel_30': '30号钢',
            'aluminum': '铝',
            'titanium': '钛',
            'stainless_steel': '不锈钢',
            'brass': '黄铜',
            'copper': '铜',
            'bronze': '青铜',
            'cast_iron': '铸铁',
            'tool_steel': '工具钢',

            # Операции
            'turning': '车削',
            'milling': '铣削',
            'drilling': '钻孔',
            'boring': '镗孔',
            'threading': '螺纹加工',
        }
    }

    # Соответствие материалов (RU → EN ключ)
    MATERIAL_MAPPING = {
        # Русский → English key
        'сталь': 'steel',
        'сталь 45': 'steel_45',
        'сталь45': 'steel_45',
        'сталь 30': 'steel_30',
        'сталь30': 'steel_30',
        'алюминий': 'aluminum',
        'титан': 'titanium',
        'нержавейка': 'stainless_steel',
        'нержавеющая сталь': 'stainless_steel',
        'латунь': 'brass',
        'медь': 'copper',
        'бронза': 'bronze',
        'чугун': 'cast_iron',
        'инструментальная сталь': 'tool_steel',

        # English → English key
        'steel': 'steel',
        'steel 45': 'steel_45',
        'aluminum': 'aluminum',
        'titanium': 'titanium',
        'stainless steel': 'stainless_steel',
        'brass': 'brass',
        'copper': 'copper',
        'bronze': 'bronze',
        'cast iron': 'cast_iron',
        'tool steel': 'tool_steel',

        # Китайский → English key
        '钢': 'steel',
        '45号钢': 'steel_45',
        '30号钢': 'steel_30',
        '铝': 'aluminum',
        '钛': 'titanium',
        '不锈钢': 'stainless_steel',
        '黄铜': 'brass',
        '铜': 'copper',
        '青铜': 'bronze',
        '铸铁': 'cast_iron',
        '工具钢': 'tool_steel',
    }

    def __init__(self, lang='ru'):
        self.lang = lang
        self.dictionary = self.TRANSLATIONS.get(lang, self.TRANSLATIONS['ru'])

    def set_language(self, lang):
        """Устанавливает язык."""
        if lang in self.TRANSLATIONS:
            self.lang = lang
            self.dictionary = self.TRANSLATIONS[lang]

    def translate(self, key, default=None):
        """Переводит ключ."""
        return self.dictionary.get(key, default or key)

    def translate_material(self, material_name):
        """Переводит название материала."""
        material_lower = material_name.lower().strip()

        # Сначала ищем точное соответствие
        for ru_name, en_key in self.MATERIAL_MAPPING.items():
            if ru_name.lower() == material_lower:
                return self.translate(en_key)

        # Ищем частичное соответствие
        for ru_name, en_key in self.MATERIAL_MAPPING.items():
            if ru_name.lower() in material_lower:
                return self.translate(en_key)

        return material_name  # Возвращаем как есть если не нашли

    def translate_parameter(self, param_name, value=None):
        """Переводит параметр с единицами измерения."""
        translated = self.translate(param_name)

        if value is not None:
            # Добавляем единицы измерения
            if param_name in ['diameter', 'overhang', 'width', 'depth']:
                return f"{value} {self.translate('mm')}"
            elif param_name == 'cutting_speed':
                return f"{value} {self.translate('m_min')}"
            elif param_name == 'feed_rate':
                return f"{value} {self.translate('mm_rev')}"
            elif param_name == 'spindle_speed':
                return f"{value} RPM"
            elif param_name == 'estimated_time':
                return f"{value} {self.translate('min')}"

        return translated

    def format_calculation(self, result):
        """Форматирует результат расчёта на выбранном языке."""
        if not result:
            return self.translate("calculation_failed", "Не удалось выполнить расчёт.")

        lines = []
        lines.append("🔢 **" + self.translate("calculation_results", "Результаты расчёта") + ":**")
        lines.append("")

        # Исходные данные
        lines.append("📊 **" + self.translate("input_data", "Исходные данные") + ":**")

        # Определяем порядок отображения
        display_order = ['material', 'operation', 'mode', 'diameter', 'overhang', 'width', 'depth']

        for key in display_order:
            if key in result and result[key]:
                if key == 'material':
                    # Переводим материал
                    translated_material = self.translate_material(result[key])
                    lines.append(f"• {self.translate(key)}: {translated_material}")
                else:
                    lines.append(f"• {self.translate(key)}: {result[key]}")

        lines.append("")

        # Параметры обработки
        lines.append("⚙️ **" + self.translate("processing_parameters", "Режимы обработки") + ":**")

        cutting_params = [
            'cutting_speed', 'feed_rate', 'depth_per_pass', 'depth_of_cut',
            'spindle_speed', 'passes', 'rigidity', 'estimated_time'
        ]

        for param in cutting_params:
            if param in result and result[param]:
                if param in ['rigidity', 'estimated_time']:
                    lines.append(f"• {self.translate(param)}: {result[param]}")
                else:
                    # Переводим параметр с единицами
                    lines.append(f"• {self.translate(param)}: {self.translate_parameter(param, result[param])}")

        lines.append("")

        # Примечания
        if 'notes' in result and result['notes']:
            lines.append("💡 **" + self.translate("important_notes", "Важные замечания") + ":**")
            for note in result['notes']:
                # Пытаемся перевести примечание если оно стандартное
                translated_note = self.translate(note.lower().replace(' ', '_'), note)
                lines.append(f"• {translated_note}")

        lines.append("")
        lines.append("⚠️ **" + self.translate("remember", "Помни") + ":** " +
                     self.translate("calculated_values_note",
                                    "Это расчётные значения. Корректируй по результатам пробного прохода."))

        return "\n".join(lines)


# Глобальный переводчик
translator = Translator()


def set_language(lang):
    """Устанавливает глобальный язык."""
    translator.set_language(lang)


def get_translator():
    """Возвращает глобальный переводчик."""
    return translator