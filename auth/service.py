"""
Authentication Service Layer.
Encapsulates all auth business logic: check_email, register, login, refresh, logout, reset.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Tuple, Optional

from auth.config import (
    MAX_FAILED_LOGIN_ATTEMPTS,
    LOCKOUT_DURATION_MINUTES,
    MAX_RESET_REQUESTS_PER_HOUR,
    RESET_TOKEN_EXPIRE_MINUTES,
    REQUIRE_EMAIL_VERIFICATION,
    USE_OTP_FOR_RESET,
)
from auth.exceptions import (
    UserAlreadyExists,
    UserNotFound,
    InvalidPassword,
    AccountLocked,
    EmailNotVerified,
    TokenExpired,
    TokenInvalid,
    ResetTokenInvalid,
    RateLimitExceeded,
)
from auth.db import (
    get_user_by_email,
    get_user_by_id,
    create_user,
    update_user_login,
    increment_failed_attempts,
    update_password,
    store_session,
    get_session,
    revoke_session,
    revoke_all_user_sessions,
    store_password_reset,
    get_password_reset,
    mark_password_reset_used,
    count_recent_resets,
)
from auth.security import (
    hash_password,
    verify_password,
    validate_password_strength,
    validate_email_address,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token,
)
from auth.email import (
    send_welcome_email,
    send_password_reset_email,
    send_password_changed_email,
)


def check_email(email: str) -> Dict[str, Any]:
    """
    Checks if an email exists and returns guidance for the smart auth screen.
    Returns: {"exists": bool, "email": str, "name": Optional[str]}
    """
    valid, norm_email = validate_email_address(email)
    if not valid:
        raise ValueError(norm_email)

    user = get_user_by_email(norm_email)
    if user:
        first_name = user["full_name"].split()[0] if user.get("full_name") else "Engineer"
        return {"exists": True, "email": norm_email, "name": first_name}
    return {"exists": False, "email": norm_email, "name": None}


def register(full_name: str, email: str, password: str, terms_accepted: bool = True) -> Dict[str, Any]:
    """
    Registers a new user account with security checks and password policies.
    Returns auth tokens dict.
    """
    if not terms_accepted:
        raise ValueError("You must accept the terms of service to continue.")

    valid, norm_email = validate_email_address(email)
    if not valid:
        raise ValueError(norm_email)

    if not full_name or len(full_name.strip()) < 2:
        raise ValueError("Please provide your full name.")

    # Check for existing user
    existing = get_user_by_email(norm_email)
    if existing:
        raise UserAlreadyExists()

    # Validate password rules
    p_valid, p_msg = validate_password_strength(password)
    if not p_valid:
        raise InvalidPassword(p_msg)

    # Hash password and persist user
    pwd_hash = hash_password(password)
    email_verified = not REQUIRE_EMAIL_VERIFICATION
    user = create_user(full_name, norm_email, pwd_hash, email_verified=email_verified)

    # Send welcome email
    send_welcome_email(norm_email, full_name)

    if REQUIRE_EMAIL_VERIFICATION:
        return {
            "email_verified": False,
            "message": "Account created! Please check your email to verify before signing in.",
            "user": user,
        }

    # Auto sign in
    access_token = create_access_token(user["id"], user["email"], user["full_name"])
    refresh_token, jti_hash, exp_iso = create_refresh_token(user["id"], user["email"], user["full_name"])
    store_session(jti_hash, user["id"], exp_iso)
    update_user_login(user["id"])

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }


def login(email: str, password: str) -> Dict[str, Any]:
    """
    Authenticates an existing user with rate limiting and lockout protection.
    Returns auth tokens dict.
    """
    valid, norm_email = validate_email_address(email)
    if not valid:
        raise ValueError(norm_email)

    user = get_user_by_email(norm_email)
    if not user:
        raise UserNotFound()

    # Check lockout status
    if user.get("locked_until"):
        lock_until = datetime.fromisoformat(user["locked_until"])
        now = datetime.now(timezone.utc)
        if now < lock_until:
            diff_min = max(1, int((lock_until - now).total_seconds() / 60))
            raise AccountLocked(f"Account temporarily locked due to multiple failed attempts. Try again in {diff_min} min.")

    # Verify password
    if not verify_password(password, user["password_hash"]):
        new_attempts = (user.get("failed_attempts") or 0) + 1
        lock_until_str = None
        if new_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
            lock_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            lock_until_str = lock_until.isoformat()
            increment_failed_attempts(user["id"], lock_until_str)
            raise AccountLocked()
        else:
            increment_failed_attempts(user["id"])
            raise InvalidPassword()

    # Check email verification if required
    if REQUIRE_EMAIL_VERIFICATION and not user.get("email_verified"):
        raise EmailNotVerified()

    # Issue tokens
    access_token = create_access_token(user["id"], user["email"], user["full_name"])
    refresh_token, jti_hash, exp_iso = create_refresh_token(user["id"], user["email"], user["full_name"])
    store_session(jti_hash, user["id"], exp_iso)
    update_user_login(user["id"])

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }


def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """
    Rotates a refresh token: issues a new access token and a new refresh token,
    while revoking the used refresh token.
    """
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise TokenInvalid("Supplied token is not a refresh token.")

    jti = payload.get("jti")
    user_id = int(payload.get("sub"))
    jti_hash = hash_token(jti)

    # Check session in DB
    session = get_session(jti_hash)
    if not session or session.get("revoked"):
        # Possible token reuse/replay attack: revoke all user sessions
        revoke_all_user_sessions(user_id)
        raise TokenInvalid("Session revoked. Please sign in again.")

    # Check expiration in session record
    exp_dt = datetime.fromisoformat(session["expires_at"])
    if datetime.now(timezone.utc) > exp_dt:
        revoke_session(jti_hash)
        raise TokenExpired("Refresh session expired.")

    # Revoke old refresh token
    revoke_session(jti_hash)

    # Fetch user details
    user = get_user_by_id(user_id)
    if not user:
        raise UserNotFound()

    # Issue new pair
    new_access_token = create_access_token(user["id"], user["email"], user["full_name"])
    new_refresh_token, new_jti_hash, new_exp_iso = create_refresh_token(user["id"], user["email"], user["full_name"])
    store_session(new_jti_hash, user["id"], new_exp_iso)

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "user": user,
    }


def logout(refresh_token: Optional[str] = None):
    """Revokes the given refresh token on logout."""
    if refresh_token:
        try:
            payload = decode_token(refresh_token)
            jti = payload.get("jti")
            if jti:
                revoke_session(hash_token(jti))
        except Exception:
            pass


def request_password_reset(email: str) -> str:
    """
    Initiates password reset with rate limiting (max 3/hr per email).
    Always returns a neutral confirmation message to prevent user enumeration.
    """
    neutral_msg = "If an account exists for this email, we have sent reset instructions."
    valid, norm_email = validate_email_address(email)
    if not valid:
        return neutral_msg

    user = get_user_by_email(norm_email)
    if not user:
        return neutral_msg

    # Check rate limit (max 3 per hour)
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    if count_recent_resets(user["id"], one_hour_ago) >= MAX_RESET_REQUESTS_PER_HOUR:
        raise RateLimitExceeded()

    # Generate token or 6-digit OTP
    if USE_OTP_FOR_RESET:
        token = f"{secrets.randbelow(900000) + 100000:06d}"
    else:
        token = secrets.token_urlsafe(32)

    token_hash = hash_token(token)
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)).isoformat()

    store_password_reset(token_hash, user["id"], expires_at)
    send_password_reset_email(norm_email, token, is_otp=USE_OTP_FOR_RESET)

    return neutral_msg


def reset_password(token: str, new_password: str):
    """
    Completes password reset: validates token, enforces password strength,
    updates password hash, marks token as used, and revokes all active sessions.
    """
    token_hash = hash_token(token.strip())
    reset_rec = get_password_reset(token_hash)

    if not reset_rec or reset_rec.get("used"):
        raise ResetTokenInvalid()

    # Check expiry
    exp_dt = datetime.fromisoformat(reset_rec["expires_at"])
    if datetime.now(timezone.utc) > exp_dt:
        raise ResetTokenInvalid()

    # Validate password rules
    p_valid, p_msg = validate_password_strength(new_password)
    if not p_valid:
        raise InvalidPassword(p_msg)

    user_id = reset_rec["user_id"]
    new_hash = hash_password(new_password)

    # Update password and consume token
    update_password(user_id, new_hash)
    mark_password_reset_used(token_hash)

    # Revoke all existing sessions for this user
    revoke_all_user_sessions(user_id)

    # Send confirmation email
    user = get_user_by_id(user_id)
    if user:
        send_password_changed_email(user["email"], user["full_name"])
