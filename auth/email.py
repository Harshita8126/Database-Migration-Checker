"""
Email Notification Service & HTML Email Templates.
Sends SMTP emails if configured, otherwise falls back to console logging for seamless dev mode.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from auth.config import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    SMTP_FROM_EMAIL,
    SMTP_FROM_NAME,
    SMTP_USE_TLS,
)


def _send_email(to_email: str, subject: str, html_content: str, text_content: Optional[str] = None) -> bool:
    """Internal mail dispatcher. If SMTP host is empty, prints to console."""
    if not SMTP_HOST:
        print("\n" + "=" * 65)
        print(f"[AUTH DEV EMAIL NOTICE] SMTP Not Configured. Email Simulation:")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print("-" * 65)
        print(text_content or html_content)
        print("=" * 65 + "\n")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
        msg["To"] = to_email

        if text_content:
            msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10.0) as server:
            if SMTP_USE_TLS:
                server.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM_EMAIL, [to_email], msg.as_string())
        return True
    except Exception as e:
        print(f"[AUTH EMAIL ERROR] Failed to send email via SMTP: {e}")
        return False


# -----------------------------------------------------------------------------
# Email Templates (Clean Notion / Stripe Developer Style)
# -----------------------------------------------------------------------------
def _render_layout(title: str, body_html: str) -> str:
    """Standardized clean light HTML email layout."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #F7F6F2; margin: 0; padding: 24px; color: #1C1F23; }}
            .container {{ max-width: 520px; margin: 0 auto; background: #FFFFFF; border: 1px solid #E7E5DF; border-radius: 12px; padding: 32px; }}
            .badge {{ display: inline-block; width: 32px; height: 32px; background: #0F766E; border-radius: 6px; color: #FFFFFF; font-weight: 700; line-height: 32px; text-align: center; margin-bottom: 20px; font-family: monospace; }}
            .h1 {{ font-size: 20px; font-weight: 700; margin-bottom: 12px; color: #1C1F23; }}
            .p {{ font-size: 15px; line-height: 1.6; color: #5B6470; margin-bottom: 20px; }}
            .btn {{ display: inline-block; padding: 10px 22px; background: #0F766E; color: #FFFFFF !important; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 14px; margin: 16px 0; }}
            .box {{ background: #F1EFE9; border: 1px solid #E7E5DF; border-radius: 8px; padding: 14px; font-family: monospace; font-size: 16px; font-weight: 700; text-align: center; letter-spacing: 2px; color: #0F766E; margin: 16px 0; }}
            .footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #E7E5DF; font-size: 12px; color: #8A929C; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="badge">PG</div>
            <div class="h1">{title}</div>
            {body_html}
            <div class="footer">
                PostgreSQL Migration Safety Checker &bull; Zero-Downtime DDL Engine<br>
                This is an automated security notice.
            </div>
        </div>
    </body>
    </html>
    """


def send_welcome_email(to_email: str, name: str, verification_token: Optional[str] = None):
    """Sends welcome email with optional verification instructions."""
    subject = "Welcome to PostgreSQL Migration Safety Checker"
    verify_html = ""
    if verification_token:
        verify_html = f"""
        <p class="p">Please use the verification code below to verify your email address:</p>
        <div class="box">{verification_token}</div>
        """
    body_html = f"""
    <p class="p">Hi {name},</p>
    <p class="p">Welcome to PostgreSQL Migration Safety Checker! Your account is active and you can now inspect migration SQL files before running them on production.</p>
    {verify_html}
    <p class="p">Enjoy zero-downtime database releases.</p>
    """
    _send_email(to_email, subject, _render_layout(subject, body_html), f"Welcome {name}! Your account is ready.")


def send_password_reset_email(to_email: str, token_or_otp: str, is_otp: bool = False):
    """Sends password reset instructions containing either a reset token or 6-digit OTP."""
    subject = "Reset Your Password - PostgreSQL Migration Safety Checker"
    if is_otp:
        body_html = f"""
        <p class="p">We received a request to reset your password. Use the 6-digit verification code below:</p>
        <div class="box">{token_or_otp}</div>
        <p class="p">This code is valid for 15 minutes. If you did not request this, you can safely ignore this email.</p>
        """
    else:
        body_html = f"""
        <p class="p">We received a request to reset your password. Use the secure reset token below in your app:</p>
        <div class="box">{token_or_otp}</div>
        <p class="p">This reset token is single-use and will expire in 15 minutes.</p>
        <p class="p">If you did not request a password reset, please secure your account immediately.</p>
        """
    _send_email(to_email, subject, _render_layout("Password Reset Request", body_html), f"Your reset code is: {token_or_otp}")


def send_password_changed_email(to_email: str, name: str):
    """Sends security confirmation email when password has been modified."""
    subject = "Security Notice: Your Password Has Been Changed"
    body_html = f"""
    <p class="p">Hi {name},</p>
    <p class="p">This is confirmation that the password for your account has been successfully updated.</p>
    <p class="p">All active sessions across other devices have been revoked for your security.</p>
    <p class="p">If you did not perform this change, please contact your security team immediately.</p>
    """
    _send_email(to_email, subject, _render_layout("Password Updated", body_html), "Your password was recently changed.")
