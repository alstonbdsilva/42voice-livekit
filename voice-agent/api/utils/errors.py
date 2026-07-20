"""
API Exception Definitions.
Standardizes domain and operational errors.
"""

from typing import List, Any, Optional


class AppError(Exception):
    """Base application exception for operational errors."""
    def __init__(self, message: str, status_code: int, code: str, errors: Optional[List[Any]] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.errors = errors or []


class BadRequestError(AppError):
    def __init__(self, message: str = "Bad request", code: str = "BAD_REQUEST"):
        super().__init__(message, 400, code)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Unauthorized access", code: str = "UNAUTHORIZED"):
        super().__init__(message, 401, code)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Access forbidden", code: str = "FORBIDDEN"):
        super().__init__(message, 403, code)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", code: str = "NOT_FOUND"):
        super().__init__(message, 404, code)


class ConflictError(AppError):
    def __init__(self, message: str = "Resource conflict", code: str = "CONFLICT"):
        super().__init__(message, 409, code)


class ValidationError(AppError):
    def __init__(self, errors: List[Any], message: str = "Validation failed"):
        super().__init__(message, 422, "VALIDATION_ERROR", errors)


class TooManyRequestsError(AppError):
    def __init__(self, message: str = "Too many requests, please try again later", code: str = "TOO_MANY_REQUESTS"):
        super().__init__(message, 429, code)


class InternalServerError(AppError):
    def __init__(self, message: str = "Internal server error", code: str = "INTERNAL_SERVER_ERROR"):
        super().__init__(message, 500, code)
