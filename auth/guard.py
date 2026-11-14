"""
Authentication Guard & Cookie Session Manager.
Maintains authentication across browser refreshes and manages token rotation.
"""

import time
from typing import Optional, Dict, Any
import streamlit as st

from auth.security import decode_token
from auth.service import refresh_access_token, logout as service_logout
from auth.exceptions import TokenExpired, TokenInvalid

# Try importing extra_streamlit_components for cookie management
try:
    import extra_streamlit_components as stx
    COOKIE_MANAGER_AVAILABLE = True
except ImportError:
    COOKIE_MANAGER_AVAILABLE = False


COOKIE_REFRESH_KEY = "pg_checker_refresh_token"


def get_cookie_manager():
    """Initializes and caches the CookieManager instance."""
    if not COOKIE_MANAGER_AVAILABLE:
        return None
    if "cookie_manager" not in st.session_state:
        st.session_state.cookie_manager = stx.CookieManager(key="auth_cookie_mgr")
    return st.session_state.cookie_manager


def init_auth_state():
    """Initializes authentication variables in Streamlit session_state."""
    if "auth_user" not in st.session_state:
        st.session_state.auth_user = None
    if "auth_access_token" not in st.session_state:
        st.session_state.auth_access_token = None
    if "auth_refresh_token" not in st.session_state:
        st.session_state.auth_refresh_token = None
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "show_auth_modal" not in st.session_state:
        st.session_state.show_auth_modal = False
    if "auth_step" not in st.session_state:
        st.session_state.auth_step = "email"
    if "auth_email" not in st.session_state:
        st.session_state.auth_email = ""
    if "auth_flash_message" not in st.session_state:
        st.session_state.auth_flash_message = None
    if "auth_flash_type" not in st.session_state:
        st.session_state.auth_flash_type = "info"
    if "intended_destination" not in st.session_state:
        st.session_state.intended_destination = "workspace"


def set_auth_session(auth_response: Dict[str, Any]):
    """Stores tokens in session_state and sets browser cookie."""
    st.session_state.auth_access_token = auth_response.get("access_token")
    st.session_state.auth_refresh_token = auth_response.get("refresh_token")
    st.session_state.auth_user = auth_response.get("user")
    st.session_state.authenticated = True
    st.session_state.show_auth_modal = False

    # Store refresh token in secure cookie
    mgr = get_cookie_manager()
    if mgr and auth_response.get("refresh_token"):
        try:
            # Set cookie for 7 days
            mgr.set(COOKIE_REFRESH_KEY, auth_response["refresh_token"], max_age=7*24*3600)
        except Exception:
            pass


def clear_auth_session():
    """Clears all session variables, cookies, and revokes refresh tokens."""
    refresh_token = st.session_state.get("auth_refresh_token")
    if refresh_token:
        service_logout(refresh_token)

    st.session_state.auth_user = None
    st.session_state.auth_access_token = None
    st.session_state.auth_refresh_token = None
    st.session_state.authenticated = False
    st.session_state.show_auth_modal = False
    st.session_state.auth_step = "email"
    st.session_state.auth_email = ""

    mgr = get_cookie_manager()
    if mgr:
        try:
            mgr.delete(COOKIE_REFRESH_KEY)
        except Exception:
            pass


def check_and_restore_session():
    """
    Checks if a valid session exists in memory or attempts to restore
    from the refresh token stored in browser cookies.
    Also handles silent rotation if access token is near expiry (< 60s).
    """
    init_auth_state()

    # 1. Check current access token in memory
    access_token = st.session_state.get("auth_access_token")
    refresh_token = st.session_state.get("auth_refresh_token")

    if access_token:
        try:
            payload = decode_token(access_token)
            # Check if expiring soon (< 60s)
            exp = payload.get("exp", 0)
            if exp - int(time.time()) < 60:
                if refresh_token:
                    # Silent auto-refresh
                    rotated = refresh_access_token(refresh_token)
                    set_auth_session(rotated)
                    return True
            st.session_state.authenticated = True
            return True
        except TokenExpired:
            if refresh_token:
                try:
                    rotated = refresh_access_token(refresh_token)
                    set_auth_session(rotated)
                    return True
                except Exception:
                    clear_auth_session()
                    return False
        except TokenInvalid:
            clear_auth_session()
            return False

    # 2. Attempt cookie restore if not in memory
    mgr = get_cookie_manager()
    if mgr:
        try:
            cookie_rt = mgr.get(COOKIE_REFRESH_KEY)
            if cookie_rt and not st.session_state.get("auth_refresh_token"):
                rotated = refresh_access_token(cookie_rt)
                set_auth_session(rotated)
                return True
        except Exception:
            pass

    return st.session_state.get("authenticated", False)


def require_auth() -> bool:
    """
    Reusable authentication guard for protected views.
    Returns True if user is authenticated; otherwise triggers the auth view and returns False.
    """
    is_authed = check_and_restore_session()
    if not is_authed:
        st.session_state.authenticated = False
        st.session_state.show_auth_modal = True
        return False
    return True


def get_current_user() -> Optional[Dict[str, Any]]:
    """Returns the currently authenticated user dictionary."""
    return st.session_state.get("auth_user")
