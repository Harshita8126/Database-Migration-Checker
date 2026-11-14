"""
Authentication Package Exports.
"""

from auth.config import (
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from auth.exceptions import (
    AuthException,
    UserAlreadyExists,
    UserNotFound,
    InvalidPassword,
    AccountLocked,
    TokenExpired,
    TokenInvalid,
    ResetTokenInvalid,
    RateLimitExceeded,
)
from auth.guard import (
    init_auth_state,
    check_and_restore_session,
    require_auth,
    get_current_user,
    set_auth_session,
    clear_auth_session,
)
from auth.ui import (
    render_smart_auth_screen,
    render_user_nav_menu,
    render_password_strength_meter,
)

__all__ = [
    "init_auth_state",
    "check_and_restore_session",
    "require_auth",
    "get_current_user",
    "set_auth_session",
    "clear_auth_session",
    "render_smart_auth_screen",
    "render_user_nav_menu",
    "render_password_strength_meter",
    "UserAlreadyExists",
    "UserNotFound",
    "InvalidPassword",
    "AccountLocked",
    "TokenExpired",
    "TokenInvalid",
    "ResetTokenInvalid",
    "RateLimitExceeded",
]
