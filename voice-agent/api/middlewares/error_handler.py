"""
Global FastAPI Exception Handlers.
Intercepts AppError, Pydantic validation, and unhandled system exceptions.
"""

import logging
import traceback
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from api.utils.errors import AppError
from api.utils.api_response import ApiResponse
from config import get_settings

logger = logging.getLogger("voice-agent.api.error_handler")


def register_error_handlers(app: FastAPI) -> None:
    """Register custom exception interceptors for standardized output."""
    
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        req_id = getattr(request.state, "request_id", "unknown")
        logger.warning(
            f"Operational Exception [ReqId: {req_id}]: {exc.message} (code: {exc.code})"
        )
        return ApiResponse.error(
            status_code=exc.status_code,
            message=exc.message,
            code=exc.code,
            errors=exc.errors
        )
        
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        # Format Pydantic errors to match Express validateRequest Zod format:
        # Array of { "field": "body.fieldname", "message": "error msg" }
        error_details = []
        for error in exc.errors():
            loc = error.get("loc", [])
            # Convert loc tuple (e.g. ('body', 'email')) to dot path ('email')
            field = ".".join([str(x) for x in loc if x != "body"])
            error_details.append({
                "field": field,
                "message": error.get("msg", "Validation error")
            })
            
        req_id = getattr(request.state, "request_id", "unknown")
        logger.warning(f"Validation Exception [ReqId: {req_id}]: {error_details}")
        
        return ApiResponse.error(
            status_code=422,
            message="Validation failed",
            code="VALIDATION_ERROR",
            errors=error_details
        )
        
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        req_id = getattr(request.state, "request_id", "unknown")
        logger.exception(f"Critical/Unhandled System Exception [ReqId: {req_id}]: {exc}")
        
        settings = get_settings()
        
        # Hide raw server stacks in production environments
        if settings.log_level == "DEBUG":
            message = str(exc)
            errors = [{"stack": traceback.format_exc()}]
        else:
            message = "An unexpected internal server error occurred."
            errors = []
            
        return ApiResponse.error(
            status_code=500,
            message=message,
            code="INTERNAL_SERVER_ERROR",
            errors=errors
        )
