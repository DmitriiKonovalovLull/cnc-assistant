def recommend_rpm(material: str, machine_type: str, diameter: float, operation: str, cut_type: str = "rough") -> dict:
    """
    Возвращает расширенные рекомендации по резанию.
    material: steel, aluminum и тд
    machine_type: cnc/manual
    diameter: мм
    operation: 'turning', 'milling', 'drilling'
    cut_type: 'rough' (черновая) или 'clean' (чистовая)
    """
    # Базовая скорость резания Vc м/мин по материалу
    vc_table = {
        "steel": 120,
        "aluminum": 300,
        "titanium": 50,
        "stainless_steel": 80,
        "cast_iron": 100,
        "brass": 200,
        "copper": 180
    }
    vc = vc_table.get(material, 100)

    # Базовый RPM по формуле n = Vc*1000/(π*D)
    rpm = int((vc * 1000) / (3.14 * diameter))

    # Ограничение по станку
    max_rpm = 2000 if machine_type == "cnc" else 1000
    rpm = min(rpm, max_rpm)

    # Глубина реза и подача по операции и типу обработки
    if operation == "turning":
        depth_of_cut = 2.0 if cut_type == "rough" else 0.5
        feed_per_tooth = 0.2 if cut_type == "rough" else 0.05
        tool_type = "твердосплавная"
    elif operation == "milling":
        depth_of_cut = 5.0 if cut_type == "rough" else 1.0
        feed_per_tooth = 0.1 if cut_type == "rough" else 0.05
        tool_type = "твердосплавная"
    elif operation == "drilling":
        depth_of_cut = diameter / 2
        feed_per_tooth = 0.05
        tool_type = "быстрорежущая сталь"
    else:
        depth_of_cut = 1.0
        feed_per_tooth = 0.1
        tool_type = "универсальная"

    return {
        "rpm": rpm,
        "vc": vc,
        "depth_of_cut": depth_of_cut,
        "feed_per_tooth": feed_per_tooth,
        "operation_type": cut_type,
        "tool_type": tool_type,
        "notes": "Используй охлаждение, проверяй стружку"
    }
