def detect_intent(text: str) -> str:
    t = text.lower()

    if "/start" in t or "старт" in t:
        return "start"

    if any(x in t for x in ["алю", "сталь", "титан"]):
        return "cutting_request"

    if t in ["дальше", "далее", "что дальше"]:
        return "next_step"

    return "unknown"
