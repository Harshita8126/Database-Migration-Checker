"""
Security & Cryptography Utilities.
Provides bcrypt password hashing, JWT creation/decoding, and SHA-256 token hashing.
"""

import re
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple

import bcrypt
import jwt
from email_validator import validate_email, EmailNotValidError

from auth.config import (
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    MIN_PASSWORD_LENGTH,
)
from auth.exceptions import TokenExpired, TokenInvalid


# -----------------------------------------------------------------------------
# Password Hashing & Strength
# -----------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Hashes a raw password string using bcrypt with salt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validates password strength according to security policy:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must include at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must include at least one lowercase letter."
    if not re.search(r"[0-9]", password):
        return False, "Password must include at least one number."
    return True, "Strong password."


def calculate_password_score(password: str) -> Tuple[int, str]:
    """
    Calculates a 0-4 password score for the live UI strength meter.
    Returns: (score, label)
    """
    if not password:
        return 0, "Empty"
    score = 0
    if len(password) >= 8:
        score += 1
    if len(password) >= 12:
        score += 1
    if re.search(r"[A-Z]", password) and re.search(r"[a-z]", password):
        score += 1
    if re.search(r"[0-9]", password):
        score += 1
    if re.search(r"[\W_]", password):
        score += 1

    score = min(score, 4)
    labels = {
        0: "Very Weak",
        1: "Weak",
        2: "Fair",
        3: "Good",
        4: "Strong",
    }
    return score, labels[score]


# -----------------------------------------------------------------------------
# Email Validation
# -----------------------------------------------------------------------------
def validate_email_address(email: str) -> Tuple[bool, str]:
    """Validates and normalizes email format server-side."""
    try:
        validated = validate_email(email.strip(), check_deliverability=False)
        return True, validated.normalized.lower()
    except EmailNotValidError as e:
        return False, str(e)


# -----------------------------------------------------------------------------
# SHA-256 Token Hashing (for Refresh Tokens and Reset Links)
# -----------------------------------------------------------------------------
def hash_token(raw_token: str) -> str:
    """Hashes a raw token with SHA-256 for safe database storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


# -----------------------------------------------------------------------------
# JWT Generation & Decoding
# -----------------------------------------------------------------------------
def create_access_token(user_id: int, email: str, name: str) -> str:
    """Creates a short-lived access JWT token (15 mins)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "email": email.lower(),
        "name": name,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: int, email: str, name: str) -> Tuple[str, str, str]:
    """
    Creates a long-lived refresh JWT token (7 days).
    Returns: (raw_refresh_token, jti_hash, expires_at_iso)
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    jti = str(uuid.uuid4())
    payload = {
        "sub": str(user_id),
        "email": email.lower(),
        "name": name,
        "type": "refresh",
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    jti_hash = hash_token(jti)
    return token, jti_hash, expire.isoformat()


def decode_token(token: str) -> Dict[str, Any]:
    """Decodes and validates a JWT token. Raises TokenExpired or TokenInvalid."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise TokenExpired()
    except Exception:
        raise TokenInvalid()
