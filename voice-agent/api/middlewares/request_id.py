"""
Request ID tracing middleware.
Generates or forwards unique request tracing headers.
"""

import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Capture request ID from header or generate a fresh UUID
        req_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        
        # 2. Bind tracing state to the request object
        request.state.request_id = req_id
        
        # 3. Proceed down the middleware chain
        response = await call_next(request)
        
        # 4. Inject tracking header into response
        response.headers["X-Request-ID"] = req_id
        return response
