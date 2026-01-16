import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path("data/users")
BASE_DIR.mkdir(parents=True, exist_ok=True)

def _file(user_id: int) -> Path:
    return BASE_DIR / f"{user_id}.json"

def load(user_id: int) -> dict:
    file = _file(user_id)
    if file.exists():
        return json.loads(file.read_text(encoding="utf-8"))
    return {
        "created_at": datetime.now().isoformat(),
        "stats": {
            "materials": {},
            "operations": {},
            "modes": {}
        },
        "jobs": []
    }

def save(user_id: int, data: dict):
    _file(user_id).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

def register_job(user_id: int, job: dict):
    data = load(user_id)

    # статистика
    for key in ("material", "operation", "mode"):
        value = job.get(key)
        if value:
            data["stats"][key + "s"][value] = \
                data["stats"][key + "s"].get(value, 0) + 1

    # история работ
    data["jobs"].append({
        **job,
        "timestamp": datetime.now().isoformat()
    })

    data["jobs"] = data["jobs"][-50:]  # храним последние 50
    save(user_id, data)