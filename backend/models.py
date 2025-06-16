import os
import datetime

from backend.utils import UPLOAD_FOLDER, get_db, DB_PATH


def init_db():
    with get_db() as conn:
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


def log_request(filename: str, ip: str, prompt: str, output: str):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO requests (filename, timestamp, ip, prompt, output) VALUES (?, ?, ?, ?, ?)",
            (filename, datetime.datetime.utcnow().isoformat(), ip, prompt, output),
        )
