"""
Authentication Configuration & Settings.
Loads secrets safely from Streamlit secrets (.streamlit/secrets.toml) or os.environ.
"""

import os
import secrets
from typing import Optional

try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False


def _get_secret(key: str, default: Optional[str] = None) -> str:
    """Retrieve secret from Streamlit secrets, then os.environ, then default."""
    if STREAMLIT_AVAILABLE:
        try:
            if key in st.secrets:
                return str(st.secrets[key])
            if "auth" in st.secrets and key in st.secrets["auth"]:
                return str(st.secrets["auth"][key])
        except Exception:
            pass
    val = os.environ.get(key)
    if val:
        return val
    if default is not None:
        return default
    # If no secret provided, generate a persistent random secret for session safety
    generated = secrets.token_hex(32)
    os.environ[key] = generated
    return generated


# -----------------------------------------------------------------------------
# Security & JWT Lifetimes
# -----------------------------------------------------------------------------
JWT_SECRET_KEY: str = _get_secret("JWT_SECRET_KEY", None)
JWT_ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(_get_secret("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(_get_secret("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
RESET_TOKEN_EXPIRE_MINUTES: int = 15

# -----------------------------------------------------------------------------
# Security Policy & Rate Limiting
# -----------------------------------------------------------------------------
MAX_FAILED_LOGIN_ATTEMPTS: int = 5
LOCKOUT_DURATION_MINUTES: int = 10
MAX_RESET_REQUESTS_PER_HOUR: int = 3
MIN_PASSWORD_LENGTH: int = 8

# -----------------------------------------------------------------------------
# Feature Flags
# -----------------------------------------------------------------------------
REQUIRE_EMAIL_VERIFICATION: bool = _get_secret("REQUIRE_EMAIL_VERIFICATION", "false").lower() in ("true", "1", "yes")
USE_OTP_FOR_RESET: bool = _get_secret("USE_OTP_FOR_RESET", "false").lower() in ("true", "1", "yes")

# -----------------------------------------------------------------------------
# SMTP Email Settings (Optional / Falls back to Console Dev Mode)
# -----------------------------------------------------------------------------
SMTP_HOST: str = _get_secret("SMTP_HOST", "")
SMTP_PORT: int = int(_get_secret("SMTP_PORT", "587"))
SMTP_USER: str = _get_secret("SMTP_USER", "")
SMTP_PASSWORD: str = _get_secret("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL: str = _get_secret("SMTP_FROM_EMAIL", "no-reply@pgsafetymigrations.internal")
SMTP_FROM_NAME: str = _get_secret("SMTP_FROM_NAME", "PostgreSQL Migration Safety Checker")
SMTP_USE_TLS: bool = _get_secret("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")

# Database Path
DB_PATH: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "auth.db"))
