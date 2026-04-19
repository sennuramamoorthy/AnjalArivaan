"""Domain-level exceptions — translated into HTTP responses by the exception handler."""
from fastapi import status


class DomainError(Exception):
    """Base class for domain errors."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "domain_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class NotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class AuthenticationError(DomainError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthenticated"


class AuthorizationError(DomainError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"


class ValidationError(DomainError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "validation_error"


class IntegrationError(DomainError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "integration_error"


class RateLimitedError(DomainError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"
