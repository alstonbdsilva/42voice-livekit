"""
Rate Limiting Middleware.
Implements general and auth-specific rate limits using a sliding window.
"""

import time
import asyncio
from typing import Dict, List
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from api.utils.api_response import ApiResponse
from config import get_settings

# Simple in-memory storage for IP request timestamps
# Structure: { ip: [timestamp1, timestamp2, ...] }
general_limit_store: Dict[str, List[float]] = {}
auth_limit_store: Dict[str, List[float]] = {}
lock = asyncio.Lock()


class RateLimiterMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        ip = request.client.host if request.client else "127.0.0.1"
        current_time = time.time()
        
        # Configure thresholds
        window_seconds = settings.rate_limit_window_ms / 1000.0
        general_max = settings.rate_limit_max
        auth_max = 15 # Strict limit of 15 attempts for auth routes
        
        # Determine if target route is a sensitive auth endpoint
        path = request.url.path
        is_auth_route = any(
            p in path for p in [
                "/auth/login", 
                "/auth/register", 
                "/auth/forgot-password", 
                "/auth/reset-password",
                "/auth/resend-verification"
            ]
        )
        
        async with lock:
            # 1. Clean old entries and enforce General Limit
            timestamps = general_limit_store.get(ip, [])
            timestamps = [t for t in timestamps if current_time - t < window_seconds]
            general_limit_store[ip] = timestamps
            
            if len(timestamps) >= general_max:
                return ApiResponse.error(
                    status_code=429,
                    message="Too many requests, please try again later.",
                    code="RATE_LIMIT_EXCEEDED"
                )
            
            # 2. Clean old entries and enforce Auth-specific Limit
            if is_auth_route:
                auth_timestamps = auth_limit_store.get(ip, [])
                auth_timestamps = [t for t in auth_timestamps if current_time - t < 900.0]  # 15 mins window
                auth_limit_store[ip] = auth_timestamps
                
                if len(auth_timestamps) >= auth_max:
                    return ApiResponse.error(
                        status_code=429,
                        message="Too many authentication attempts. Please try again in 15 minutes.",
                        code="AUTH_RATE_LIMIT_EXCEEDED"
                    )
                
                auth_limit_store[ip].append(current_time)
                
            # Log current general request timestamp
            general_limit_store[ip].append(current_time)
            
        return await call_next(request)
