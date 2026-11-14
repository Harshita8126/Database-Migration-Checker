"""
Custom Authentication Exceptions.
Mapped directly to user-facing error and notification messages.
"""

class AuthException(Exception):
    """Base exception for authentication system."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class UserAlreadyExists(AuthException):
    """Raised when registering an email that already exists."""
    def __init__(self, message: str = "This email is already registered. Please sign in."):
        super().__init__(message)


class UserNotFound(AuthException):
    """Raised when an action is attempted on an unregistered email."""
    def __init__(self, message: str = "No account found. Please sign up first."):
        super().__init__(message)


class InvalidPassword(AuthException):
    """Raised when the submitted password does not match or meet policy."""
    def __init__(self, message: str = "Incorrect password. Please try again."):
        super().__init__(message)


class AccountLocked(AuthException):
    """Raised when account is locked due to excessive failed attempts."""
    def __init__(self, message: str = "Account temporarily locked due to multiple failed attempts. Please try again in 10 minutes."):
        super().__init__(message)


class EmailNotVerified(AuthException):
    """Raised when email verification is required but not yet completed."""
    def __init__(self, message: str = "Please verify your email before signing in."):
        super().__init__(message)


class TokenExpired(AuthException):
    """Raised when access token or refresh token has expired."""
    def __init__(self, message: str = "Your session has expired. Please sign in again."):
        super().__init__(message)


class TokenInvalid(AuthException):
    """Raised when a token signature or format is invalid."""
    def __init__(self, message: str = "Invalid authentication token. Please sign in again."):
        super().__init__(message)


class ResetTokenInvalid(AuthException):
    """Raised when password reset token or OTP is expired, invalid, or already used."""
    def __init__(self, message: str = "This reset link is invalid or has expired."):
        super().__init__(message)


class RateLimitExceeded(AuthException):
    """Raised when rate limits for password reset requests are exceeded."""
    def __init__(self, message: str = "Too many password reset requests. Please try again later."):
        super().__init__(message)
