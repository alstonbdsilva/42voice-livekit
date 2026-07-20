"""
HTTP request logging middleware.
Measures request duration and logs performance/access metrics.
"""

import time
import json
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from api.utils.logger import request_logger


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Process the request
        response = await call_next(request)
        
        # Calculate duration in milliseconds
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Extract metrics
        req_id = getattr(request.state, "request_id", "unknown")
        method = request.method
        url = request.url.path
        if request.url.query:
            url = f"{url}?{request.url.query}"
            
        status_code = response.status_code
        ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")
        
        # Format a JSON-compatible structured log line
        log_data = {
            "requestId": req_id,
            "method": method,
            "url": url,
            "statusCode": status_code,
            "durationMs": duration_ms,
            "ip": ip,
            "userAgent": user_agent
        }
        
        request_logger.info(
            f"{method} {url} {status_code} - {duration_ms}ms - {json.dumps(log_data)}"
        )
        
        return response
