from storage.sqlite import conn

def get_or_create_user(user_id: int) -> dict:
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    if not row:
        cur.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        return {"user_id": user_id, "experience": 0.0}
    return {"user_id": row[0], "experience": row[1]}

def save_history(user_id: int, text: str):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO history (user_id, raw_text) VALUES (?, ?)",
        (user_id, text)
    )
    conn.commit()
