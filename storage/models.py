"""
models.py
SQLite schema for CNC Assistant (Day 3)
"""

# =========================
# USERS
# =========================

USER_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


# =========================
# HISTORY (FACTS, NOT CHAT)
# =========================

HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,

    material TEXT,
    operation TEXT,
    tool TEXT,
    diameter REAL,

    machine_type TEXT,
    rpm_mode TEXT,

    recommended_params TEXT,
    user_params TEXT,

    physics_valid INTEGER DEFAULT 1,

    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(user_id) REFERENCES users(user_id)
);
"""


# =========================
# DECISIONS (DATA EVALUATION)
# =========================

DECISIONS_TABLE = """
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    history_id INTEGER,

    metric TEXT,              -- rpm / feed / depth
    delta REAL,               -- deviation from reference (0.0 = ideal)
    direction TEXT,           -- higher / lower

    machine_limit_hit INTEGER DEFAULT 0,
    physics_valid INTEGER DEFAULT 1,

    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(history_id) REFERENCES history(id)
);
"""


# =========================
# USER PROFILE (AGGREGATED)
# =========================

PROFILE_TABLE = """
CREATE TABLE IF NOT EXISTS profiles (
    user_id INTEGER PRIMARY KEY,

    samples INTEGER DEFAULT 0,

    avg_delta REAL DEFAULT 0.0,
    stability REAL DEFAULT 0.0,
    physics_valid_ratio REAL DEFAULT 1.0,

    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(user_id) REFERENCES users(user_id)
);
"""
