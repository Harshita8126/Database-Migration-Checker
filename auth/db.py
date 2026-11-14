"""
Database Access Layer (DAL) for Authentication.
Uses SQLite (auth.db) with parameterized queries, designed to be easily swappable to PostgreSQL.
"""

import sqlite3
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from contextlib import contextmanager
from auth.config import DB_PATH


def _get_connection() -> sqlite3.Connection:
    """Creates a SQLite connection with row factories enabled."""
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def get_db():
    """Context manager for safe database transaction handling."""
    conn = _get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initializes tables and indexes for users, sessions, and password resets."""
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            email_verified INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            last_login TEXT,
            failed_attempts INTEGER DEFAULT 0,
            locked_until TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jti_hash TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            revoked INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_sessions_jti_hash ON sessions(jti_hash);
        CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);

        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_hash TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_resets_token_hash ON password_resets(token_hash);
        CREATE INDEX IF NOT EXISTS idx_resets_user_id ON password_resets(user_id);
        """)


# Ensure database is initialized on import
init_db()


# -----------------------------------------------------------------------------
# User Repository
# -----------------------------------------------------------------------------
def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Fetches user record by email (case-insensitive)."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM users WHERE email = ? COLLATE NOCASE",
            (email.strip().lower(),)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Fetches user record by primary key."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def create_user(full_name: str, email: str, password_hash: str, email_verified: bool = False) -> Dict[str, Any]:
    """Creates a new user with UTC timestamp."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (full_name, email, password_hash, email_verified, created_at, last_login, failed_attempts, locked_until)
            VALUES (?, ?, ?, ?, ?, NULL, 0, NULL)
            """,
            (full_name.strip(), email.strip().lower(), password_hash, 1 if email_verified else 0, now_iso)
        )
        user_id = cursor.lastrowid
        cursor_sel = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor_sel.fetchone()
        return dict(row) if row else None


def update_user_login(user_id: int):
    """Updates last login timestamp and resets failed attempts and lockouts."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            """
            UPDATE users
            SET last_login = ?, failed_attempts = 0, locked_until = NULL
            WHERE id = ?
            """,
            (now_iso, user_id)
        )


def increment_failed_attempts(user_id: int, lock_until: Optional[str] = None):
    """Increments failed login counter and optionally sets lockout timestamp."""
    with get_db() as conn:
        if lock_until:
            conn.execute(
                "UPDATE users SET failed_attempts = failed_attempts + 1, locked_until = ? WHERE id = ?",
                (lock_until, user_id)
            )
        else:
            conn.execute(
                "UPDATE users SET failed_attempts = failed_attempts + 1 WHERE id = ?",
                (user_id,)
            )


def update_password(user_id: int, new_password_hash: str):
    """Updates user password hash and clears any lockouts."""
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, failed_attempts = 0, locked_until = NULL WHERE id = ?",
            (new_password_hash, user_id)
        )


def verify_user_email(user_id: int):
    """Sets email_verified flag to 1."""
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET email_verified = 1 WHERE id = ?",
            (user_id,)
        )


# -----------------------------------------------------------------------------
# Session / Refresh Token Repository
# -----------------------------------------------------------------------------
def store_session(jti_hash: str, user_id: int, expires_at: str):
    """Stores hashed jti for a refresh token."""
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO sessions (jti_hash, user_id, expires_at, revoked)
            VALUES (?, ?, ?, 0)
            """,
            (jti_hash, user_id, expires_at)
        )


def get_session(jti_hash: str) -> Optional[Dict[str, Any]]:
    """Retrieves session by jti hash."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM sessions WHERE jti_hash = ?",
            (jti_hash,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def revoke_session(jti_hash: str):
    """Revokes a single session."""
    with get_db() as conn:
        conn.execute(
            "UPDATE sessions SET revoked = 1 WHERE jti_hash = ?",
            (jti_hash,)
        )


def revoke_all_user_sessions(user_id: int):
    """Revokes all active refresh tokens for a user (called after password reset)."""
    with get_db() as conn:
        conn.execute(
            "UPDATE sessions SET revoked = 1 WHERE user_id = ?",
            (user_id,)
        )


# -----------------------------------------------------------------------------
# Password Reset Repository
# -----------------------------------------------------------------------------
def store_password_reset(token_hash: str, user_id: int, expires_at: str):
    """Stores hashed reset token."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO password_resets (token_hash, user_id, created_at, expires_at, used)
            VALUES (?, ?, ?, ?, 0)
            """,
            (token_hash, user_id, now_iso, expires_at)
        )


def get_password_reset(token_hash: str) -> Optional[Dict[str, Any]]:
    """Retrieves password reset record by token hash."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM password_resets WHERE token_hash = ?",
            (token_hash,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def mark_password_reset_used(token_hash: str):
    """Marks a reset token as consumed."""
    with get_db() as conn:
        conn.execute(
            "UPDATE password_resets SET used = 1 WHERE token_hash = ?",
            (token_hash,)
        )


def count_recent_resets(user_id: int, since_iso: str) -> int:
    """Counts reset requests created for a user since a given UTC timestamp."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM password_resets WHERE user_id = ? AND created_at >= ?",
            (user_id, since_iso)
        )
        return cursor.fetchone()[0]
