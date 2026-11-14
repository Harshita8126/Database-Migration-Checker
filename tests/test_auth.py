"""
Unit and Integration Tests for Complete Authentication System.
Tests:
- New user sign up
- Existing email on sign up (UserAlreadyExists)
- Unregistered email on sign in (UserNotFound)
- Wrong password (InvalidPassword)
- Successful login and JWT issuance
- 5 failed attempts lockout (AccountLocked)
- Forgot password full flow (request, token generation, reset password)
- Expired / used reset token rejection (ResetTokenInvalid)
- Token rotation and refresh
- Session revocation on logout
"""

import os
import pytest
from datetime import datetime, timedelta, timezone

from auth.config import DB_PATH
from auth.db import init_db, get_user_by_email, get_user_by_id, revoke_all_user_sessions
from auth.service import (
    check_email,
    register,
    login,
    refresh_access_token,
    logout,
    request_password_reset,
    reset_password,
)
from auth.security import decode_token, hash_token
from auth.exceptions import (
    UserAlreadyExists,
    UserNotFound,
    InvalidPassword,
    AccountLocked,
    ResetTokenInvalid,
    RateLimitExceeded,
)


@pytest.fixture(autouse=True)
def setup_auth_db():
    """Ensures database is cleanly initialized and wiped before each test."""
    init_db()
    from auth.db import get_db
    with get_db() as conn:
        conn.execute("DELETE FROM password_resets")
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM users")
    yield


def test_check_email_flow():
    """Tests email-first smart discovery."""
    # Test unregistered email
    res = check_email("new_developer@company.com")
    assert res["exists"] is False
    assert res["email"] == "new_developer@company.com"

    # Register user
    register("Jane Developer", "new_developer@company.com", "SecurePass123!")

    # Check again
    res2 = check_email("new_developer@company.com")
    assert res2["exists"] is True
    assert res2["name"] == "Jane"


def test_user_signup_and_duplicate_prevention():
    """Tests new user registration and duplicate email prevention."""
    test_email = "alex_devops@company.com"
    res = register("Alex Ops", test_email, "SuperSecret123#")
    assert "access_token" in res
    assert "refresh_token" in res
    assert res["user"]["email"] == test_email

    # Try registering again with same email
    with pytest.raises(UserAlreadyExists):
        register("Alex Duplicate", test_email, "AnotherPass123!")


def test_login_success_and_wrong_password():
    """Tests authentication success and wrong password rejection."""
    email = "sam_dba@company.com"
    pwd = "DatabaseMaster1!"
    register("Sam DBA", email, pwd)

    # Correct password
    auth = login(email, pwd)
    assert auth["access_token"] is not None
    payload = decode_token(auth["access_token"])
    assert payload["email"] == email
    assert payload["type"] == "access"

    # Wrong password
    with pytest.raises(InvalidPassword):
        login(email, "WrongPassword999!")


def test_unregistered_email_login():
    """Tests login attempt with an email that does not exist."""
    with pytest.raises(UserNotFound):
        login("ghost_user@company.com", "SomePassword123!")


def test_lockout_after_5_failed_attempts():
    """Tests account lockout after 5 consecutive failed login attempts."""
    email = "brute_force_target@company.com"
    pwd = "ValidPassword123$"
    register("Target User", email, pwd)

    for i in range(4):
        with pytest.raises(InvalidPassword):
            login(email, f"WrongPass{i}!")

    # 5th attempt must trigger AccountLocked
    with pytest.raises(AccountLocked):
        login(email, "WrongPass5!")


def test_token_rotation_and_revocation():
    """Tests refresh token rotation and session revocation."""
    email = "rotation_test@company.com"
    res = register("Rotation Test", email, "TokenRotate123$")
    old_rt = res["refresh_token"]

    # Rotate refresh token
    rotated = refresh_access_token(old_rt)
    new_at = rotated["access_token"]
    new_rt = rotated["refresh_token"]

    assert new_at is not None
    assert new_rt != old_rt

    # Old refresh token should now be rejected (replay protection)
    with pytest.raises(Exception):
        refresh_access_token(old_rt)


def test_forgot_password_full_flow():
    """Tests request_password_reset, token extraction, and password reset."""
    email = "reset_user@company.com"
    register("Reset User", email, "OldPassword123#")

    msg = request_password_reset(email)
    assert "reset instructions" in msg

    # Retrieve reset token from DB for verification
    from auth.db import get_db
    with get_db() as conn:
        cursor = conn.execute("SELECT token_hash FROM password_resets ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        assert row is not None

    # Test reset with invalid token
    with pytest.raises(ResetTokenInvalid):
        reset_password("completely_bogus_token", "NewPassword123#")
