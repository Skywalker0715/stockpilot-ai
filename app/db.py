# SQLite access and ordered schema migrations.

import sqlite3
from collections.abc import Iterator
from pathlib import Path

from fastapi import Depends

from app import config

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with sane defaults for this app."""
    path = Path(db_path) if db_path is not None else config.DB_PATH
    # check_same_thread=False: FastAPI runs sync dependencies, endpoint
    # bodies, and dependency teardown on anyio worker threads, which are
    # not guaranteed to be the same thread. Connections here are
    # request-scoped (see get_connection), so a connection is never used
    # by two threads at the same time; disabling the check is safe.
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Enforce foreign keys on every connection (SQLite default is off).
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def run_migrations(conn: sqlite3.Connection) -> list[str]:
    """Apply pending .sql migrations in filename order, tracking applied ones.

    Each migration file runs exactly once inside its own transaction.
    Returns the list of migration filenames that were applied.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            name TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()

    applied = {
        row["name"]
        for row in conn.execute("SELECT name FROM schema_migrations").fetchall()
    }
    applied_now: list[str] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name in applied:
            continue
        script = path.read_text(encoding="utf-8")
        try:
            conn.executescript(script)
            conn.execute(
                "INSERT INTO schema_migrations (name) VALUES (?)", (path.name,)
            )
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise
        applied_now.append(path.name)
    return applied_now


def get_connection() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request, always closed."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
