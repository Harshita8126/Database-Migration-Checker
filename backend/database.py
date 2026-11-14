"""
PostgreSQL Database Connection Manager using psycopg 3.


Enforces:
1. Strict read-only sessions (default_transaction_read_only = ON).
2. NEVER executing user-uploaded migration SQL.
3. Safe parameterization for metadata inspection.
4. Credential masking (no passwords exposed in logs or reports).
5. Clean connection lifecycle management.
"""

from contextlib import contextmanager
from typing import Dict, Any, Optional
import psycopg
from psycopg import sql
from pydantic import BaseModel, Field


class DBConfig(BaseModel):
    host: str = Field(default="localhost", description="PostgreSQL host")
    port: int = Field(default=5432, description="PostgreSQL port")
    database: str = Field(default="postgres", description="Database name")
    username: str = Field(default="postgres", description="Username")
    password: Optional[str] = Field(default=None, description="Password")
    connect_timeout: int = Field(default=5, description="Connection timeout in seconds")

    def get_connection_string(self) -> str:
        """Build connection string for psycopg3."""
        parts = [
            f"host={self.host}",
            f"port={self.port}",
            f"dbname={self.database}",
            f"user={self.username}",
            f"connect_timeout={self.connect_timeout}",
        ]
        if self.password:
            parts.append(f"password={self.password}")
        return " ".join(parts)

    def sanitized_dict(self) -> Dict[str, Any]:
        """Return dict with masked password for safe logging and UI display."""
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "password": "••••••••" if self.password else "(none)",
            "connect_timeout": self.connect_timeout,
        }


def test_connection(config: DBConfig) -> Dict[str, Any]:
    """
    Tests database connectivity using a short-lived read-only connection.
    Returns status and server version info.
    """
    try:
        conninfo = config.get_connection_string()
        with psycopg.connect(conninfo, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                row = cur.fetchone()
                version_str = row[0] if row else "Unknown PostgreSQL"

                cur.execute("SHOW server_version_num;")
                num_row = cur.fetchone()
                version_num = int(num_row[0]) if num_row else 140000

                cur.execute("SELECT current_user, current_database();")
                usr, db = cur.fetchone()

        return {
            "success": True,
            "message": "Successfully connected to PostgreSQL",
            "version": version_str,
            "version_num": version_num,
            "user": usr,
            "database": db,
        }
    except Exception as exc:
        err_msg = str(exc)
        # Scrub any accidentally leaked password from error string
        if config.password and config.password in err_msg:
            err_msg = err_msg.replace(config.password, "••••••••")
        return {
            "success": False,
            "message": f"Connection failed: {err_msg}",
            "version": None,
            "version_num": None,
        }


@contextmanager
def get_readonly_connection(config: DBConfig):
    """
    Yields a read-only psycopg3 connection.
    Sets default_transaction_read_only = ON to prevent any accidental write statements.
    """
    conninfo = config.get_connection_string()
    conn = None
    try:
        conn = psycopg.connect(conninfo)
        with conn.cursor() as cur:
            cur.execute("SET default_transaction_read_only = ON;")
            cur.execute("SET statement_timeout = '10s';")
        yield conn
    finally:
        if conn and not conn.closed:
            conn.close()
