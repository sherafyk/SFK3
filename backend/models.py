import os
import sqlite3
import datetime

from backend.utils import UPLOAD_FOLDER

DB_PATH = os.path.join(UPLOAD_FOLDER, 'requests.db')


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
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
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO requests (filename, timestamp, ip, prompt, output) VALUES (?, ?, ?, ?, ?)",
            (filename, datetime.datetime.utcnow().isoformat(), ip, prompt, output),
        )
