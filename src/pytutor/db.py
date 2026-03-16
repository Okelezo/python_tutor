from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def db_path() -> Path:
    raw = os.environ.get("PYTUTOR_DB_PATH") or "pytutor.db"
    return Path(raw).expanduser().resolve()


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          email TEXT NOT NULL UNIQUE,
          password_hash TEXT NOT NULL,
          created_at INTEGER NOT NULL
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
          token TEXT PRIMARY KEY,
          user_id INTEGER NOT NULL,
          expires_at INTEGER NOT NULL,
          created_at INTEGER NOT NULL,
          FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS completed_exercises (
          user_id INTEGER NOT NULL,
          exercise_id TEXT NOT NULL,
          completed_at INTEGER NOT NULL,
          PRIMARY KEY(user_id, exercise_id),
          FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
    )

    conn.commit()
