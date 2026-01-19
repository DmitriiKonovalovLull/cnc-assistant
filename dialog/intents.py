def detect_intent(text: str) -> str:
    t = text.lower()
    if any(x in t for x in ["алю", "сталь", "титан"]):
        return "cutting_request"
    if t in ["/start", "старт"]:
        return "start"
    return "unknown"
