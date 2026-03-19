import json
import sqlite3


def init_db(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            question TEXT,
            spread TEXT,
            cards_json TEXT,
            reading_text TEXT,
            used_ai INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def save_reading(db_path, session_id, question, spread, cards_json, reading_text, used_ai):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO readings (session_id, question, spread, cards_json, reading_text, used_ai)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (session_id, question, spread, cards_json, reading_text, used_ai))

    conn.commit()
    conn.close()


def save_chat_message(db_path, session_id, role, content):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO chat_messages (session_id, role, content)
        VALUES (?, ?, ?)
    """, (session_id, role, content))

    conn.commit()
    conn.close()


def get_recent_context(db_path, session_id, limit=12):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT question, spread, cards_json, reading_text, used_ai, created_at
        FROM readings
        WHERE session_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (session_id, limit),
    )
    readings = cur.fetchall()

    cur.execute(
        """
        SELECT role, content, created_at
        FROM chat_messages
        WHERE session_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (session_id, limit * 2),
    )
    chats = cur.fetchall()

    conn.close()

    result = []

    for question, spread, cards_json, reading_text, used_ai, created_at in readings:
        cards = []
        if cards_json:
            try:
                cards = json.loads(cards_json)
            except Exception:
                cards = []

        result.append({
            "type": "reading",
            "question": question or "",
            "spread": spread or "",
            "cards": cards,
            "reading": reading_text or "",
            "used_ai": bool(used_ai),
            "created_at": created_at,
        })

    for role, content, created_at in chats:
        result.append({
            "type": "chat",
            "role": role,
            "content": content or "",
            "created_at": created_at,
        })

    return result
