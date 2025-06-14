import os
import sqlite3
import datetime

from backend.utils import UPLOAD_FOLDER

DB_PATH = os.path.join(UPLOAD_FOLDER, 'requests.db')


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            timestamp TEXT,
            ip TEXT,
            prompt TEXT,
            output TEXT
        )"""
    )
    conn.commit()
    conn.close()


def log_request(filename: str, ip: str, prompt: str, output: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO requests (filename, timestamp, ip, prompt, output) VALUES (?, ?, ?, ?, ?)",
        (filename, datetime.datetime.utcnow().isoformat(), ip, prompt, output),
    )
    conn.commit()
    conn.close()
