import re

# таблица скоростей резания (м/мин)
speed_table = {
    "алюминий": 200,
    "сталь": 100,
    "титан": 60
}

def extract_material(text: str):
    t = text.lower()
    if "алю" in t:
        return "алюминий"
    if "сталь" in t:
        return "сталь"
    if "титан" in t:
        return "титан"
    return None

def extract_diameter(text: str):
    match = re.search(r'\d+(\.\d+)?', text)
    if match:
        return float(match.group())
    return None
