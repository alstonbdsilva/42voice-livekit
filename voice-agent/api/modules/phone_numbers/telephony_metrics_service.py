"""
Telephony Metrics Service.
Tracks call latencies, SIP response codes, and performance metrics.
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone, date
from api import database

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.telephony_metrics_service")


class TelephonyMetricsService:
    """Service for tracking telephony metrics."""
    
    @staticmethod
    async def record_call_setup_latency(
        phone_number_id: str,
        latency_ms: int
    ) -> bool:
        """Record call setup latency."""
        try:
            today = date.today()
            
            query = """
                INSERT INTO telephony_metrics 
                (phone_number_id, metric_date, call_setup_latency_ms)
                VALUES ($1, $2, $3)
                ON CONFLICT (phone_number_id, metric_date) DO UPDATE
                SET call_setup_latency_ms = $3
            """
            
            await database.query(query, [UUID(phone_number_id), today, latency_ms])
            return True
            
        except Exception as e:
            logger.error(f"Error recording call setup latency: {e}")
            return False
    
    @staticmethod
    async def record_ring_duration(
        phone_number_id: str,
        duration_ms: int
    ) -> bool:
        """Record ring duration."""
        try:
            today = date.today()
            
            query = """
                INSERT INTO telephony_metrics 
                (phone_number_id, metric_date, ring_duration_ms)
                VALUES ($1, $2, $3)
                ON CONFLICT (phone_number_id, metric_date) DO UPDATE
                SET ring_duration_ms = $3
            """
            
            await database.query(query, [UUID(phone_number_id), today, duration_ms])
            return True
            
        except Exception as e:
            logger.error(f"Error recording ring duration: {e}")
            return False
    
    @staticmethod
    async def record_talk_duration(
        phone_number_id: str,
        duration_ms: int
    ) -> bool:
        """Record talk duration."""
        try:
            today = date.today()
            
            query = """
                INSERT INTO telephony_metrics 
                (phone_number_id, metric_date, talk_duration_ms)
                VALUES ($1, $2, $3)
                ON CONFLICT (phone_number_id, metric_date) DO UPDATE
                SET talk_duration_ms = $3
            """
            
            await database.query(query, [UUID(phone_number_id), today, duration_ms])
            return True
            
        except Exception as e:
            logger.error(f"Error recording talk duration: {e}")
            return False
    
    @staticmethod
    async def record_post_dial_delay(
        phone_number_id: str,
        delay_ms: int
    ) -> bool:
        """Record post-dial delay."""
        try:
            today = date.today()
            
            query = """
                INSERT INTO telephony_metrics 
                (phone_number_id, metric_date, post_dial_delay_ms)
                VALUES ($1, $2, $3)
                ON CONFLICT (phone_number_id, metric_date) DO UPDATE
                SET post_dial_delay_ms = $3
            """
            
            await database.query(query, [UUID(phone_number_id), today, delay_ms])
            return True
            
        except Exception as e:
            logger.error(f"Error recording post-dial delay: {e}")
            return False
    
    @staticmethod
    async def record_transfer_latency(
        phone_number_id: str,
        latency_ms: int
    ) -> bool:
        """Record transfer latency."""
        try:
            today = date.today()
            
            query = """
                INSERT INTO telephony_metrics 
                (phone_number_id, metric_date, transfer_latency_ms)
                VALUES ($1, $2, $3)
                ON CONFLICT (phone_number_id, metric_date) DO UPDATE
                SET transfer_latency_ms = $3
            """
            
            await database.query(query, [UUID(phone_number_id), today, latency_ms])
            return True
            
        except Exception as e:
            logger.error(f"Error recording transfer latency: {e}")
            return False
    
    @staticmethod
    async def record_webhook_latency(
        phone_number_id: str,
        latency_ms: int
    ) -> bool:
        """Record webhook latency."""
        try:
            today = date.today()
            
            query = """
                INSERT INTO telephony_metrics 
                (phone_number_id, metric_date, webhook_latency_ms)
                VALUES ($1, $2, $3)
                ON CONFLICT (phone_number_id, metric_date) DO UPDATE
                SET webhook_latency_ms = $3
            """
            
            await database.query(query, [UUID(phone_number_id), today, latency_ms])
            return True
            
        except Exception as e:
            logger.error(f"Error recording webhook latency: {e}")
            return False
    
    @staticmethod
    async def record_provider_response_time(
        phone_number_id: str,
        response_time_ms: int
    ) -> bool:
        """Record provider response time."""
        try:
            today = date.today()
            
            query = """
                INSERT INTO telephony_metrics 
                (phone_number_id, metric_date, provider_response_time_ms)
                VALUES ($1, $2, $3)
                ON CONFLICT (phone_number_id, metric_date) DO UPDATE
                SET provider_response_time_ms = $3
            """
            
            await database.query(query, [UUID(phone_number_id), today, response_time_ms])
            return True
            
        except Exception as e:
            logger.error(f"Error recording provider response time: {e}")
            return False
    
    @staticmethod
    async def record_sip_response_code(
        phone_number_id: str,
        response_code: int
    ) -> bool:
        """Record SIP response code."""
        try:
            today = date.today()
            
            # Get existing codes
            query = """
                SELECT sip_response_codes FROM telephony_metrics
                WHERE phone_number_id = $1 AND metric_date = $2
            """
            
            rows = await database.query(query, [UUID(phone_number_id), today])
            
            codes = {}
            if rows and rows[0].get("sip_response_codes"):
                codes = rows[0].get("sip_response_codes")
            
            # Increment code count
            code_str = str(response_code)
            codes[code_str] = codes.get(code_str, 0) + 1
            
            # Update
            update_query = """
                INSERT INTO telephony_metrics 
                (phone_number_id, metric_date, sip_response_codes)
                VALUES ($1, $2, $3)
                ON CONFLICT (phone_number_id, metric_date) DO UPDATE
                SET sip_response_codes = $3
            """
            
            await database.query(update_query, [UUID(phone_number_id), today, codes])
            return True
            
        except Exception as e:
            logger.error(f"Error recording SIP response code: {e}")
            return False
    
    @staticmethod
    async def record_retry_count(
        phone_number_id: str,
        retry_count: int
    ) -> bool:
        """Record retry count."""
        try:
            today = date.today()
            
            query = """
                INSERT INTO telephony_metrics 
                (phone_number_id, metric_date, retry_count)
                VALUES ($1, $2, $3)
                ON CONFLICT (phone_number_id, metric_date) DO UPDATE
                SET retry_count = $3
            """
            
            await database.query(query, [UUID(phone_number_id), today, retry_count])
            return True
            
        except Exception as e:
            logger.error(f"Error recording retry count: {e}")
            return False
    
    @staticmethod
    async def record_failure_count(
        phone_number_id: str,
        failure_count: int
    ) -> bool:
        """Record failure count."""
        try:
            today = date.today()
            
            query = """
                INSERT INTO telephony_metrics 
                (phone_number_id, metric_date, failure_count)
                VALUES ($1, $2, $3)
                ON CONFLICT (phone_number_id, metric_date) DO UPDATE
                SET failure_count = $3
            """
            
            await database.query(query, [UUID(phone_number_id), today, failure_count])
            return True
            
        except Exception as e:
            logger.error(f"Error recording failure count: {e}")
            return False
    
    @staticmethod
    async def get_metrics(
        phone_number_id: str,
        metric_date: Optional[date] = None
    ) -> Optional[Dict[str, Any]]:
        """Get metrics for date."""
        try:
            if not metric_date:
                metric_date = date.today()
            
            query = """
                SELECT phone_number_id, metric_date, call_setup_latency_ms,
                       ring_duration_ms, talk_duration_ms, post_dial_delay_ms,
                       transfer_latency_ms, webhook_latency_ms, provider_response_time_ms,
                       sip_response_codes, retry_count, failure_count, circuit_breaker_state
                FROM telephony_metrics
                WHERE phone_number_id = $1 AND metric_date = $2
            """
            
            rows = await database.query(query, [UUID(phone_number_id), metric_date])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return None
