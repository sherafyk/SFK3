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
                json TEXT,
                bdr_json TEXT
            )"""
        )
        # Upgrade schema if ``json`` column is missing (for databases created
        # before this column was introduced).
        cols = [row[1] for row in conn.execute("PRAGMA table_info(requests)")]
        if "json" not in cols:
            conn.execute("ALTER TABLE requests ADD COLUMN json TEXT")
        if "bdr_json" not in cols:
            conn.execute("ALTER TABLE requests ADD COLUMN bdr_json TEXT")
        # Table for storing per-job metadata such as the job name
        conn.execute(
            "CREATE TABLE IF NOT EXISTS jobmeta (name TEXT)"
        )
        row = conn.execute("SELECT name FROM jobmeta").fetchone()
        if row is None:
            conn.execute("INSERT INTO jobmeta (name) VALUES ('')")
        # Table for storing additional documents uploaded for the job
        conn.execute(
            """CREATE TABLE IF NOT EXISTS job_attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                timestamp TEXT
            )"""
        )


def log_request(
    filename: str,
    ip: str,
    prompt: str,
    output: str,
    db_path: str = DB_PATH,
    json_text: str = "",
    bdr_json_text: str = "",
):
    """Insert a request row into the database at ``db_path``."""
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO requests (filename, timestamp, ip, prompt, output, json, bdr_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                filename,
                datetime.datetime.utcnow().isoformat(),
                ip,
                prompt,
                output,
                json_text,
                bdr_json_text,
            ),
        )


def get_job_name(db_path: str = DB_PATH) -> str:
    """Return the stored name for the job database at ``db_path``."""
    with get_db(db_path) as conn:
        row = conn.execute("SELECT name FROM jobmeta").fetchone()
        return row[0] if row else ""


def set_job_name(name: str, db_path: str = DB_PATH) -> None:
    """Update the name for the job database at ``db_path``."""
    with get_db(db_path) as conn:
        row = conn.execute("SELECT name FROM jobmeta").fetchone()
        if row is None:
            conn.execute("INSERT INTO jobmeta (name) VALUES (?)", (name,))
        else:
            conn.execute("UPDATE jobmeta SET name=?", (name,))


def add_attachment(filename: str, db_path: str = DB_PATH) -> None:
    """Insert a record into the ``job_attachments`` table."""
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO job_attachments (filename, timestamp) VALUES (?, ?)",
            (filename, datetime.datetime.utcnow().isoformat()),
        )


def get_attachments(db_path: str = DB_PATH) -> list[dict]:
    """Return a list of attachment dictionaries for the job DB."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT id, filename, timestamp FROM job_attachments ORDER BY id"
        ).fetchall()
    return [
        {"id": r[0], "filename": r[1], "timestamp": r[2]}
        for r in rows
    ]
