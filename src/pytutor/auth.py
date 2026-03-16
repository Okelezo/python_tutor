from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass

import sqlite3


_PBKDF2_ITERS = 200_000


def _hash_password(password: str, *, salt: bytes | None = None) -> str:
    if salt is None:
        salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERS)
    return f"pbkdf2_sha256${_PBKDF2_ITERS}${salt.hex()}${dk.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        alg, iters_s, salt_hex, hash_hex = stored.split("$", 3)
        if alg != "pbkdf2_sha256":
            return False
        iters = int(iters_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except Exception:
        return False

    got = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
    return hmac.compare_digest(got, expected)


@dataclass(frozen=True)
class User:
    id: int
    email: str


def session_cookie_name() -> str:
    return os.environ.get("PYTUTOR_SESSION_COOKIE") or "pytutor_session"


def create_user(conn: sqlite3.Connection, *, email: str, password: str) -> User:
    now = int(time.time())
    pw_hash = _hash_password(password)
    cur = conn.execute(
        "INSERT INTO users(email, password_hash, created_at) VALUES (?, ?, ?)",
        (email.strip().lower(), pw_hash, now),
    )
    conn.commit()
    return User(id=int(cur.lastrowid), email=email.strip().lower())


def authenticate(conn: sqlite3.Connection, *, email: str, password: str) -> User | None:
    row = conn.execute(
        "SELECT id, email, password_hash FROM users WHERE email = ?",
        (email.strip().lower(),),
    ).fetchone()
    if row is None:
        return None
    if not _verify_password(password, str(row["password_hash"])):
        return None
    return User(id=int(row["id"]), email=str(row["email"]))


def create_session(conn: sqlite3.Connection, *, user_id: int, ttl_seconds: int = 60 * 60 * 24 * 30) -> str:
    now = int(time.time())
    token = secrets.token_urlsafe(32)
    expires_at = now + ttl_seconds
    conn.execute(
        "INSERT INTO sessions(token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (token, user_id, expires_at, now),
    )
    conn.commit()
    return token


def get_user_by_session(conn: sqlite3.Connection, *, token: str) -> User | None:
    now = int(time.time())
    row = conn.execute(
        """
        SELECT u.id as user_id, u.email as email
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token = ? AND s.expires_at > ?
        """,
        (token, now),
    ).fetchone()
    if row is None:
        return None
    return User(id=int(row["user_id"]), email=str(row["email"]))


def delete_session(conn: sqlite3.Connection, *, token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()


def mark_completed(conn: sqlite3.Connection, *, user_id: int, exercise_id: str) -> None:
    now = int(time.time())
    conn.execute(
        "INSERT OR REPLACE INTO completed_exercises(user_id, exercise_id, completed_at) VALUES (?, ?, ?)",
        (user_id, exercise_id, now),
    )
    conn.commit()


def get_completed(conn: sqlite3.Connection, *, user_id: int) -> set[str]:
    rows = conn.execute(
        "SELECT exercise_id FROM completed_exercises WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    return {str(r["exercise_id"]) for r in rows}
