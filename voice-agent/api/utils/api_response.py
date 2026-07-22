"""
Standard API Response Formatter.
Ensures identical JSON structures for React frontend consumption.
"""

from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from typing import Any, Optional


class ApiResponse:
    @staticmethod
    def success(status_code: int = 200, message: str = "Success", data: Any = None, meta: Any = None) -> JSONResponse:
        """Standardized successful endpoint response."""
        payload = {
            "success": True,
            "message": message,
            "data": data if data is not None else {},
            "meta": meta if meta is not None else {}
        }
        return JSONResponse(status_code=status_code, content=jsonable_encoder(payload))

    @staticmethod
    def error(status_code: int, message: str, code: str, errors: Optional[Any] = None) -> JSONResponse:
        """Standardized error response."""
        payload = {
            "success": False,
            "message": message,
            "code": code,
            "errors": errors if errors is not None else []
        }
        return JSONResponse(status_code=status_code, content=jsonable_encoder(payload))

