import os
import datetime

from backend.utils import UPLOAD_FOLDER, get_db, DB_PATH


def init_db(path: str = DB_PATH):
    """Initialize a ``requests`` table in the SQLite database at ``path``.

    If the table already exists but is missing the ``json`` column, it will be
    added automatically so older databases continue to work with newer code.
    """
    with get_db(path) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                timestamp TEXT,
                ip TEXT,
                prompt TEXT,
                output TEXT,
                json TEXT
            )"""
        )
        # Upgrade schema if ``json`` column is missing (for databases created
        # before this column was introduced).
        cols = [row[1] for row in conn.execute("PRAGMA table_info(requests)")]
        if "json" not in cols:
            conn.execute("ALTER TABLE requests ADD COLUMN json TEXT")


def log_request(
    filename: str,
    ip: str,
    prompt: str,
    output: str,
    db_path: str = DB_PATH,
    json_text: str = "",
):
    """Insert a request row into the database at ``db_path``."""
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO requests (filename, timestamp, ip, prompt, output, json) VALUES (?, ?, ?, ?, ?, ?)",
            (
                filename,
                datetime.datetime.utcnow().isoformat(),
                ip,
                prompt,
                output,
                json_text,
            ),
        )
