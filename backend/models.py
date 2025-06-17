import os
import datetime

from backend.utils import UPLOAD_FOLDER, get_db, DB_PATH


def init_db(path: str = DB_PATH):
    """Initialize a ``requests`` table in the SQLite database at ``path``."""
    with get_db(path) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                timestamp TEXT,
                ip TEXT,
                prompt TEXT,
                output TEXT
            )"""
        )


def log_request(filename: str, ip: str, prompt: str, output: str, db_path: str = DB_PATH):
    """Insert a request row into the database at ``db_path``."""
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO requests (filename, timestamp, ip, prompt, output) VALUES (?, ?, ?, ?, ?)",
            (filename, datetime.datetime.utcnow().isoformat(), ip, prompt, output),
        )
