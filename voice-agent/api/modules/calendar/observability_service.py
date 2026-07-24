"""
Observability Service.
Tracks metrics and latencies for calendar operations.
"""

import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from contextlib import asynccontextmanager

logger = logging.getLogger("voice-agent.api.modules.calendar.observability_service")


class ObservabilityService:
    """Service for tracking calendar metrics."""
    
    _metrics = {
        "provider_latency": {},
        "booking_latency": {},
        "availability_latency": {},
        "webhook_latency": {},
        "sync_latency": {},
        "oauth_refresh_latency": {},
        "retry_count": {},
        "failure_count": {},
        "circuit_breaker_state": {}
    }
    
    @staticmethod
    @asynccontextmanager
    async def track_operation(operation_name: str, provider: Optional[str] = None):
        """Context manager for tracking operation latency."""
        try:
            start_time = time.time()
            
            yield
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            # Record metric
            metric_key = f"{operation_name}:{provider}" if provider else operation_name
            
            if metric_key not in ObservabilityService._metrics["provider_latency"]:
                ObservabilityService._metrics["provider_latency"][metric_key] = []
            
            ObservabilityService._metrics["provider_latency"][metric_key].append(elapsed_ms)
            
            # Keep only last 100 measurements
            if len(ObservabilityService._metrics["provider_latency"][metric_key]) > 100:
                ObservabilityService._metrics["provider_latency"][metric_key].pop(0)
            
            logger.debug(f"{operation_name} took {elapsed_ms:.2f}ms")
            
        except Exception as e:
            logger.error(f"Error tracking operation: {e}")
    
    @staticmethod
    def record_retry(operation_name: str, attempt: int) -> None:
        """Record retry attempt."""
        try:
            if operation_name not in ObservabilityService._metrics["retry_count"]:
                ObservabilityService._metrics["retry_count"][operation_name] = 0
            
            ObservabilityService._metrics["retry_count"][operation_name] += 1
            logger.info(f"Retry {attempt} for {operation_name}")
            
        except Exception as e:
            logger.error(f"Error recording retry: {e}")
    
    @staticmethod
    def record_failure(operation_name: str, error: str) -> None:
        """Record operation failure."""
        try:
            if operation_name not in ObservabilityService._metrics["failure_count"]:
                ObservabilityService._metrics["failure_count"][operation_name] = 0
            
            ObservabilityService._metrics["failure_count"][operation_name] += 1
            logger.warning(f"Failure in {operation_name}: {error}")
            
        except Exception as e:
            logger.error(f"Error recording failure: {e}")
    
    @staticmethod
    def record_circuit_breaker_state(provider: str, state: str) -> None:
        """Record circuit breaker state change."""
        try:
            ObservabilityService._metrics["circuit_breaker_state"][provider] = {
                "state": state,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            logger.warning(f"Circuit breaker {provider}: {state}")
            
        except Exception as e:
            logger.error(f"Error recording circuit breaker state: {e}")
    
    @staticmethod
    def get_metrics() -> Dict[str, Any]:
        """Get current metrics."""
        try:
            metrics = {
                "provider_latency": {},
                "retry_count": ObservabilityService._metrics["retry_count"],
                "failure_count": ObservabilityService._metrics["failure_count"],
                "circuit_breaker_state": ObservabilityService._metrics["circuit_breaker_state"]
            }
            
            # Calculate averages for latencies
            for key, values in ObservabilityService._metrics["provider_latency"].items():
                if values:
                    metrics["provider_latency"][key] = {
                        "average_ms": sum(values) / len(values),
                        "min_ms": min(values),
                        "max_ms": max(values),
                        "count": len(values)
                    }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return {}
    
    @staticmethod
    def reset_metrics() -> None:
        """Reset all metrics."""
        try:
            ObservabilityService._metrics = {
                "provider_latency": {},
                "booking_latency": {},
                "availability_latency": {},
                "webhook_latency": {},
                "sync_latency": {},
                "oauth_refresh_latency": {},
                "retry_count": {},
                "failure_count": {},
                "circuit_breaker_state": {}
            }
            logger.info("Metrics reset")
            
        except Exception as e:
            logger.error(f"Error resetting metrics: {e}")
