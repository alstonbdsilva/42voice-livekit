"""
Rate Limiter.
Handles provider rate limiting with exponential backoff and circuit breaker.
"""

import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from enum import Enum

logger = logging.getLogger("voice-agent.api.modules.calendar.rate_limiter")


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class ProviderRateLimiter:
    """Rate limiter for calendar providers."""
    
    # Rate limits per provider
    RATE_LIMITS = {
        "google": {
            "requests_per_second": 100,
            "requests_per_day": 1000000,
            "burst_size": 10
        },
        "outlook": {
            "requests_per_second": 50,
            "requests_per_day": 100000,
            "burst_size": 5
        },
        "calendly": {
            "requests_per_second": 10,
            "requests_per_day": 10000,
            "burst_size": 2
        }
    }
    
    # Circuit breaker settings
    CIRCUIT_BREAKER_THRESHOLD = 5  # Failures before opening
    CIRCUIT_BREAKER_TIMEOUT = 300  # 5 minutes
    
    _request_times: Dict[str, list] = {}
    _failure_counts: Dict[str, int] = {}
    _circuit_states: Dict[str, CircuitState] = {}
    _circuit_open_times: Dict[str, datetime] = {}
    
    @staticmethod
    async def check_rate_limit(provider: str) -> bool:
        """Check if request is allowed."""
        try:
            # Check circuit breaker
            if not ProviderRateLimiter._check_circuit_breaker(provider):
                logger.warning(f"Circuit breaker open for {provider}")
                return False
            
            # Check rate limit
            limits = ProviderRateLimiter.RATE_LIMITS.get(provider, {})
            rps = limits.get("requests_per_second", 10)
            
            now = time.time()
            
            # Initialize request times if needed
            if provider not in ProviderRateLimiter._request_times:
                ProviderRateLimiter._request_times[provider] = []
            
            # Remove old requests (older than 1 second)
            ProviderRateLimiter._request_times[provider] = [
                t for t in ProviderRateLimiter._request_times[provider]
                if now - t < 1.0
            ]
            
            # Check if we can make another request
            if len(ProviderRateLimiter._request_times[provider]) >= rps:
                logger.warning(f"Rate limit exceeded for {provider}")
                return False
            
            # Record request
            ProviderRateLimiter._request_times[provider].append(now)
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return False
    
    @staticmethod
    async def record_success(provider: str) -> bool:
        """Record successful request."""
        try:
            # Reset failure count
            ProviderRateLimiter._failure_counts[provider] = 0
            
            # Close circuit if half-open
            if ProviderRateLimiter._circuit_states.get(provider) == CircuitState.HALF_OPEN:
                ProviderRateLimiter._circuit_states[provider] = CircuitState.CLOSED
                logger.info(f"Circuit breaker closed for {provider}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error recording success: {e}")
            return False
    
    @staticmethod
    async def record_failure(provider: str) -> bool:
        """Record failed request."""
        try:
            # Increment failure count
            current = ProviderRateLimiter._failure_counts.get(provider, 0)
            ProviderRateLimiter._failure_counts[provider] = current + 1
            
            # Open circuit if threshold exceeded
            if ProviderRateLimiter._failure_counts[provider] >= ProviderRateLimiter.CIRCUIT_BREAKER_THRESHOLD:
                ProviderRateLimiter._circuit_states[provider] = CircuitState.OPEN
                ProviderRateLimiter._circuit_open_times[provider] = datetime.now(timezone.utc)
                logger.warning(f"Circuit breaker opened for {provider}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error recording failure: {e}")
            return False
    
    @staticmethod
    def _check_circuit_breaker(provider: str) -> bool:
        """Check circuit breaker state."""
        try:
            state = ProviderRateLimiter._circuit_states.get(provider, CircuitState.CLOSED)
            
            if state == CircuitState.CLOSED:
                return True
            
            if state == CircuitState.OPEN:
                # Check if timeout has passed
                open_time = ProviderRateLimiter._circuit_open_times.get(provider)
                if open_time:
                    elapsed = (datetime.now(timezone.utc) - open_time).total_seconds()
                    if elapsed > ProviderRateLimiter.CIRCUIT_BREAKER_TIMEOUT:
                        # Try half-open
                        ProviderRateLimiter._circuit_states[provider] = CircuitState.HALF_OPEN
                        logger.info(f"Circuit breaker half-open for {provider}")
                        return True
                
                return False
            
            if state == CircuitState.HALF_OPEN:
                return True
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking circuit breaker: {e}")
            return True
    
    @staticmethod
    def get_backoff_delay(attempt: int) -> float:
        """Get exponential backoff delay in seconds."""
        try:
            # Exponential backoff: 1, 2, 4, 8, 16, 32, 60 (max)
            delay = min(2 ** attempt, 60)
            return float(delay)
        except Exception as e:
            logger.error(f"Error calculating backoff: {e}")
            return 1.0
    
    @staticmethod
    def get_circuit_state(provider: str) -> str:
        """Get current circuit breaker state."""
        try:
            state = ProviderRateLimiter._circuit_states.get(provider, CircuitState.CLOSED)
            return state.value
        except Exception as e:
            logger.error(f"Error getting circuit state: {e}")
            return "unknown"
    
    @staticmethod
    def get_failure_count(provider: str) -> int:
        """Get current failure count."""
        try:
            return ProviderRateLimiter._failure_counts.get(provider, 0)
        except Exception as e:
            logger.error(f"Error getting failure count: {e}")
            return 0
