"""Domain error hierarchy.

All custom errors carry a machine-readable `code` and a human message.
The global FastAPI exception handler maps these to HTTP status codes.
"""


class AppError(Exception):
    """Base for all domain errors."""

    code: str = "APP_ERROR"
    status_code: int = 500

    def __init__(self, message: str = "An error occurred"):
        self.message = message
        super().__init__(message)


# ── Identity errors ──────────────────────────────────────────────────────────


class UserAlreadyExistsError(AppError):
    code = "USER_ALREADY_EXISTS"
    status_code = 409

    def __init__(self, message: str = "User already exists"):
        super().__init__(message)


class InvalidCredentialsError(AppError):
    code = "INVALID_CREDENTIALS"
    status_code = 401

    def __init__(self, message: str = "Invalid email or password"):
        super().__init__(message)


class MfaRequiredError(AppError):
    """Special case: returned as success=false with 200 OK (not a real error)."""

    code = "MFA_REQUIRED"
    status_code = 200

    def __init__(self, message: str = "MFA verification required"):
        super().__init__(message)


class InvalidMfaCodeError(AppError):
    code = "INVALID_MFA_CODE"
    status_code = 400

    def __init__(self, message: str = "Invalid MFA code"):
        super().__init__(message)


class MfaDisabledError(AppError):
    code = "MFA_DISABLED"
    status_code = 403

    def __init__(self, message: str = "MFA is globally disabled"):
        super().__init__(message)


class TokenExpiredError(AppError):
    code = "TOKEN_EXPIRED"
    status_code = 401

    def __init__(self, message: str = "Token has expired"):
        super().__init__(message)


class TokenInvalidError(AppError):
    code = "TOKEN_INVALID"
    status_code = 401

    def __init__(self, message: str = "Invalid token"):
        super().__init__(message)


class UnauthorizedError(AppError):
    code = "UNAUTHORIZED"
    status_code = 401

    def __init__(self, message: str = "Not authenticated"):
        super().__init__(message)


class ForbiddenError(AppError):
    code = "FORBIDDEN"
    status_code = 403

    def __init__(self, message: str = "Forbidden"):
        super().__init__(message)


class ValidationError(AppError):
    code = "VALIDATION_ERROR"
    status_code = 400

    def __init__(self, message: str = "Validation failed"):
        super().__init__(message)


class NotFoundError(AppError):
    code = "NOT_FOUND"
    status_code = 404

    def __init__(self, message: str = "Not found"):
        super().__init__(message)
