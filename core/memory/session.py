from datetime import datetime

_sessions = {}

def get(user_id: int) -> dict:
    return _sessions.setdefault(user_id, {})

def update(user_id: int, **kwargs):
    session = get(user_id)
    session.update(kwargs)
    session["updated_at"] = datetime.now().isoformat()

def reset(user_id: int):
    _sessions.pop(user_id, None)