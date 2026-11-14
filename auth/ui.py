"""
Authentication UI Components.
Implements the Notion / Stripe style email-first smart auth screens, password strength meters,
inline field validation, and top navigation user menu.
"""

import streamlit as st
from auth.service import (
    check_email,
    login,
    register,
    request_password_reset,
    reset_password,
)
from auth.security import calculate_password_score
from auth.guard import set_auth_session, clear_auth_session
from auth.exceptions import (
    UserAlreadyExists,
    UserNotFound,
    InvalidPassword,
    AccountLocked,
    EmailNotVerified,
    ResetTokenInvalid,
    RateLimitExceeded,
)


def render_password_strength_meter(password: str):
    """Renders a real-time 4-stage color-coded password strength meter."""
    score, label = calculate_password_score(password)
    colors = {
        0: "#E7E5DF",
        1: "#B91C1C",  # Red
        2: "#B45309",  # Amber
        3: "#0F766E",  # Teal
        4: "#15803D",  # Green
    }
    meter_color = colors[score]

    bars_html = ""
    for i in range(1, 5):
        bg = meter_color if i <= score else "#E7E5DF"
        bars_html += f'<div style="flex: 1; height: 4px; background: {bg}; border-radius: 2px;"></div>'

    st.markdown(f"""
    <div style="margin: 6px 0 14px 0;">
        <div style="display: flex; gap: 4px;">{bars_html}</div>
        <div style="display: flex; justify-content: space-between; font-size: 0.72rem; color: #8A929C; margin-top: 4px;">
            <span>Strength: <strong style="color: {meter_color};">{label}</strong></span>
            <span>Min 8 chars, 1 uppercase, 1 number</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_auth_header(show_back: bool = True, back_step: str = "email"):
    """Renders the top branding and optional back button inside the auth card."""
    col_back, col_badge = st.columns([1, 4])
    with col_back:
        if show_back:
            if st.button("← Back", key=f"auth_back_{back_step}"):
                st.session_state.auth_step = back_step
                st.session_state.auth_flash_message = None
                st.rerun()
    with col_badge:
        st.markdown("""
        <div style="text-align: right;">
            <span style="display: inline-block; width: 28px; height: 28px; background: var(--primary); border-radius: 6px; color: #FFF; font-weight: 700; text-align: center; line-height: 28px; font-family: monospace;">PG</span>
        </div>
        """, unsafe_allow_html=True)


def render_flash_banner():
    """Renders persistent flash notices or alert banners inside the auth card."""
    msg = st.session_state.get("auth_flash_message")
    ftype = st.session_state.get("auth_flash_type", "info")
    if msg:
        if ftype == "error":
            st.error(msg)
        elif ftype == "success":
            st.success(msg)
        elif ftype == "warning":
            st.warning(msg)
        else:
            st.info(msg)


def render_smart_auth_screen():
    """
    Renders the centered Notion / Stripe style Smart Auth screen.
    Steps:
      - 'email': User enters email, clicks Continue.
      - 'signin': Password input + Forgot Password link for existing users.
      - 'signup': Full name, password, confirm, terms for new users.
      - 'forgot': Request password reset token or OTP.
      - 'reset': Enter token and new password.
    """
    st.markdown("""
    <div style="max-width: 440px; margin: 40px auto 20px auto; background: var(--surface-card); border: 1px solid var(--border-subtle); border-radius: 12px; padding: 32px; box-shadow: var(--shadow-md);">
    """, unsafe_allow_html=True)

    current_step = st.session_state.get("auth_step", "email")

    # =========================================================================
    # STEP 1: EMAIL-FIRST DISCOVERY
    # =========================================================================
    if current_step == "email":
        render_auth_header(show_back=False)
        st.markdown("""
        <h2 style="font-size: 1.6rem; font-weight: 800; color: var(--text-primary); margin: 8px 0 4px 0;">Sign in to your account</h2>
        <div style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 20px;">
            Enter your work email to access the safety workspace.
        </div>
        """, unsafe_allow_html=True)

        render_flash_banner()

        with st.form("form_email_first", clear_on_submit=False):
            email_val = st.text_input(
                "Email address",
                value=st.session_state.get("auth_email", ""),
                placeholder="name@company.com"
            )
            submit = st.form_submit_button("Continue with Email →", use_container_width=True, type="primary")

        if submit:
            st.session_state.auth_flash_message = None
            if not email_val or not email_val.strip():
                st.session_state.auth_flash_message = "Please enter an email address."
                st.session_state.auth_flash_type = "error"
                st.rerun()
            else:
                try:
                    res = check_email(email_val)
                    st.session_state.auth_email = res["email"]
                    if res["exists"]:
                        st.session_state.auth_name = res["name"]
                        st.session_state.auth_step = "signin"
                    else:
                        st.session_state.auth_step = "signup"
                    st.rerun()
                except Exception as e:
                    st.session_state.auth_flash_message = str(e)
                    st.session_state.auth_flash_type = "error"
                    st.rerun()

        st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            if st.button("Create new account", use_container_width=True):
                st.session_state.auth_step = "signup"
                st.session_state.auth_flash_message = None
                st.rerun()
        with col_c2:
            if st.button("Direct sign in", use_container_width=True):
                st.session_state.auth_step = "signin"
                st.session_state.auth_flash_message = None
                st.rerun()

    # =========================================================================
    # STEP 2: SIGN IN (PASSWORD INPUT)
    # =========================================================================
    elif current_step == "signin":
        render_auth_header(show_back=True, back_step="email")
        name_str = st.session_state.get("auth_name")
        heading = f"Welcome back, {name_str}" if name_str else "Welcome back"

        st.markdown(f"""
        <h2 style="font-size: 1.55rem; font-weight: 800; color: var(--text-primary); margin: 8px 0 4px 0;">{heading}</h2>
        <div style="font-size: 0.88rem; color: var(--text-secondary); margin-bottom: 18px;">
            Signing in as <strong>{st.session_state.get('auth_email')}</strong>
        </div>
        """, unsafe_allow_html=True)

        render_flash_banner()

        with st.form("form_signin", clear_on_submit=False):
            pwd = st.text_input("Password", type="password", placeholder="Enter your password")
            submit = st.form_submit_button("Sign In", use_container_width=True, type="primary")

        if submit:
            email_target = st.session_state.get("auth_email")
            try:
                tokens = login(email_target, pwd)
                set_auth_session(tokens)
                st.session_state.auth_flash_message = None
                st.rerun()
            except UserNotFound:
                st.session_state.auth_flash_message = "No account found. Please sign up first."
                st.session_state.auth_flash_type = "error"
                st.session_state.auth_step = "signup"
                st.rerun()
            except AccountLocked as e:
                st.session_state.auth_flash_message = str(e)
                st.session_state.auth_flash_type = "error"
                st.rerun()
            except InvalidPassword:
                st.session_state.auth_flash_message = "Incorrect password. Please try again."
                st.session_state.auth_flash_type = "error"
                st.rerun()
            except Exception as e:
                st.session_state.auth_flash_message = str(e)
                st.session_state.auth_flash_type = "error"
                st.rerun()

        col_opts1, col_opts2 = st.columns([1, 1])
        with col_opts1:
            if st.button("Forgot password?", key="btn_to_forgot"):
                st.session_state.auth_step = "forgot"
                st.session_state.auth_flash_message = None
                st.rerun()
        with col_opts2:
            if st.button("New here? Create account", key="btn_to_signup"):
                st.session_state.auth_step = "signup"
                st.session_state.auth_flash_message = None
                st.rerun()

    # =========================================================================
    # STEP 3: SIGN UP (CREATE ACCOUNT)
    # =========================================================================
    elif current_step == "signup":
        render_auth_header(show_back=True, back_step="email")
        st.markdown(f"""
        <h2 style="font-size: 1.55rem; font-weight: 800; color: var(--text-primary); margin: 8px 0 4px 0;">Create your account</h2>
        <div style="font-size: 0.88rem; color: var(--text-secondary); margin-bottom: 18px;">
            No account found for <strong>{st.session_state.get('auth_email', 'this email')}</strong>. Let's create one.
        </div>
        """, unsafe_allow_html=True)

        render_flash_banner()

        with st.form("form_signup", clear_on_submit=False):
            name_val = st.text_input("Full name", placeholder="e.g. Jane Doe")
            email_val = st.text_input(
                "Email address",
                value=st.session_state.get("auth_email", ""),
                placeholder="name@company.com"
            )
            pwd_val = st.text_input("Password", type="password", placeholder="At least 8 characters")
            pwd_confirm = st.text_input("Confirm password", type="password", placeholder="Repeat your password")
            terms = st.checkbox("I agree to the Terms of Service & Privacy Policy", value=True)
            submit = st.form_submit_button("Create Account", use_container_width=True, type="primary")

        if pwd_val:
            render_password_strength_meter(pwd_val)

        if submit:
            if pwd_val != pwd_confirm:
                st.session_state.auth_flash_message = "Passwords do not match."
                st.session_state.auth_flash_type = "error"
                st.rerun()
            elif not terms:
                st.session_state.auth_flash_message = "You must agree to the Terms to create an account."
                st.session_state.auth_flash_type = "error"
                st.rerun()
            else:
                try:
                    res = register(name_val, email_val, pwd_val, terms_accepted=terms)
                    if res.get("email_verified") is False:
                        st.session_state.auth_flash_message = res.get("message")
                        st.session_state.auth_flash_type = "warning"
                        st.session_state.auth_step = "signin"
                    else:
                        set_auth_session(res)
                    st.rerun()
                except UserAlreadyExists:
                    st.session_state.auth_flash_message = "This email is already registered. Please sign in."
                    st.session_state.auth_flash_type = "warning"
                    st.session_state.auth_email = email_val
                    st.session_state.auth_step = "signin"
                    st.rerun()
                except Exception as e:
                    st.session_state.auth_flash_message = str(e)
                    st.session_state.auth_flash_type = "error"
                    st.rerun()

        if st.button("Already have an account? Sign in", key="btn_to_signin_from_su"):
            st.session_state.auth_step = "signin"
            st.session_state.auth_flash_message = None
            st.rerun()

    # =========================================================================
    # STEP 4: FORGOT PASSWORD REQUEST
    # =========================================================================
    elif current_step == "forgot":
        render_auth_header(show_back=True, back_step="signin")
        st.markdown("""
        <h2 style="font-size: 1.55rem; font-weight: 800; color: var(--text-primary); margin: 8px 0 4px 0;">Reset your password</h2>
        <div style="font-size: 0.88rem; color: var(--text-secondary); margin-bottom: 18px;">
            Enter your email and we'll send you instructions to reset your password.
        </div>
        """, unsafe_allow_html=True)

        render_flash_banner()

        with st.form("form_forgot", clear_on_submit=False):
            f_email = st.text_input("Account email", value=st.session_state.get("auth_email", ""))
            submit = st.form_submit_button("Send Reset Instructions", use_container_width=True, type="primary")

        if submit:
            try:
                msg = request_password_reset(f_email)
                st.session_state.auth_flash_message = msg
                st.session_state.auth_flash_type = "success"
                st.session_state.auth_step = "reset"
                st.rerun()
            except RateLimitExceeded as e:
                st.session_state.auth_flash_message = str(e)
                st.session_state.auth_flash_type = "error"
                st.rerun()
            except Exception as e:
                st.session_state.auth_flash_message = str(e)
                st.session_state.auth_flash_type = "error"
                st.rerun()

        if st.button("I already have a reset code", key="btn_already_have_code"):
            st.session_state.auth_step = "reset"
            st.session_state.auth_flash_message = None
            st.rerun()

    # =========================================================================
    # STEP 5: ENTER RESET TOKEN & NEW PASSWORD
    # =========================================================================
    elif current_step == "reset":
        render_auth_header(show_back=True, back_step="forgot")
        st.markdown("""
        <h2 style="font-size: 1.55rem; font-weight: 800; color: var(--text-primary); margin: 8px 0 4px 0;">Enter new password</h2>
        <div style="font-size: 0.88rem; color: var(--text-secondary); margin-bottom: 18px;">
            Paste the reset token or OTP code sent to your email.
        </div>
        """, unsafe_allow_html=True)

        render_flash_banner()

        with st.form("form_reset", clear_on_submit=False):
            r_token = st.text_input("Reset token / 6-digit code", placeholder="Paste reset token here")
            new_p1 = st.text_input("New password", type="password", placeholder="At least 8 characters")
            new_p2 = st.text_input("Confirm new password", type="password", placeholder="Repeat new password")
            submit = st.form_submit_button("Update Password", use_container_width=True, type="primary")

        if new_p1:
            render_password_strength_meter(new_p1)

        if submit:
            if new_p1 != new_p2:
                st.session_state.auth_flash_message = "Passwords do not match."
                st.session_state.auth_flash_type = "error"
                st.rerun()
            else:
                try:
                    reset_password(r_token, new_p1)
                    st.session_state.auth_flash_message = "Password updated successfully! Please sign in with your new password."
                    st.session_state.auth_flash_type = "success"
                    st.session_state.auth_step = "signin"
                    st.rerun()
                except ResetTokenInvalid:
                    st.session_state.auth_flash_message = "This reset link is invalid or has expired."
                    st.session_state.auth_flash_type = "error"
                    st.rerun()
                except Exception as e:
                    st.session_state.auth_flash_message = str(e)
                    st.session_state.auth_flash_type = "error"
                    st.rerun()

        if st.button("Request a new link", key="btn_request_new_link"):
            st.session_state.auth_step = "forgot"
            st.session_state.auth_flash_message = None
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def render_user_nav_menu():
    """
    Renders top-right navigation state:
    - Guests: 'Sign In' and 'Sign Up' action buttons.
    - Logged-in: Avatar initials badge with functional Profile/Logout popover.
    """
    user = st.session_state.get("auth_user")

    if not user:
        c1, c2 = st.columns([1, 1.2])
        with c1:
            if st.button("Sign In", key="nav_btn_signin"):
                st.session_state.auth_step = "signin"
                st.session_state.show_auth_modal = True
                st.session_state.auth_flash_message = None
                st.rerun()
        with c2:
            if st.button("Sign Up", key="nav_btn_signup", type="primary"):
                st.session_state.auth_step = "signup"
                st.session_state.show_auth_modal = True
                st.session_state.auth_flash_message = None
                st.rerun()
    else:
        # Generate initials
        full_name = user.get("full_name", "User")
        parts = full_name.strip().split()
        initials = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()

        with st.popover(f"👤 {initials} • {full_name.split()[0]}"):
            st.markdown(f"""
            <div style="padding: 4px 0 10px 0; border-bottom: 1px solid var(--border-subtle); margin-bottom: 10px;">
                <div style="font-weight: 700; color: var(--text-primary); font-size: 0.95rem;">{full_name}</div>
                <div style="font-size: 0.8rem; color: var(--text-secondary);">{user.get('email')}</div>
            </div>
            """, unsafe_allow_html=True)

            st.caption("Active Session (JWT HS256)")
            st.caption(f"Role: {st.session_state.get('user_role', 'Database Engineer')}")

            if st.button("Sign Out / Logout", key="popover_logout_btn", use_container_width=True):
                clear_auth_session()
                st.rerun()
