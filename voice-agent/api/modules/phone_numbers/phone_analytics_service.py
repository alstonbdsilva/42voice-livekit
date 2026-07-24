"""
Phone Analytics Service.
Tracks phone number usage and analytics.
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone, timedelta, date
from api import database

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.phone_analytics_service")


class PhoneAnalyticsService:
    """Service for phone analytics."""
    
    @staticmethod
    async def record_call(
        phone_number_id: str,
        call_type: str,
        direction: str,
        status: str,
        duration_seconds: int = 0,
        cost: float = 0.0
    ) -> bool:
        """Record call for analytics."""
        try:
            today = date.today()
            
            # Get or create usage record
            query = """
                INSERT INTO phone_number_usage 
                (phone_number_id, usage_date, inbound_calls, outbound_calls, 
                 missed_calls, failed_calls, busy_calls, total_inbound_minutes, 
                 total_outbound_minutes, inbound_cost, outbound_cost)
                VALUES ($1, $2, 0, 0, 0, 0, 0, 0, 0, 0, 0)
                ON CONFLICT (phone_number_id, usage_date) DO NOTHING
            """
            
            await database.query(query, [UUID(phone_number_id), today])
            
            # Update usage based on call type
            if direction == "inbound":
                if status == "completed":
                    update_query = """
                        UPDATE phone_number_usage
                        SET inbound_calls = inbound_calls + 1,
                            total_inbound_minutes = total_inbound_minutes + $1,
                            inbound_cost = inbound_cost + $2,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE phone_number_id = $3 AND usage_date = $4
                    """
                    
                    minutes = duration_seconds // 60
                    await database.query(
                        update_query,
                        [minutes, cost, UUID(phone_number_id), today]
                    )
                
                elif status == "missed":
                    update_query = """
                        UPDATE phone_number_usage
                        SET missed_calls = missed_calls + 1,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE phone_number_id = $1 AND usage_date = $2
                    """
                    
                    await database.query(update_query, [UUID(phone_number_id), today])
                
                elif status == "failed":
                    update_query = """
                        UPDATE phone_number_usage
                        SET failed_calls = failed_calls + 1,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE phone_number_id = $1 AND usage_date = $2
                    """
                    
                    await database.query(update_query, [UUID(phone_number_id), today])
                
                elif status == "busy":
                    update_query = """
                        UPDATE phone_number_usage
                        SET busy_calls = busy_calls + 1,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE phone_number_id = $1 AND usage_date = $2
                    """
                    
                    await database.query(update_query, [UUID(phone_number_id), today])
            
            elif direction == "outbound":
                if status == "completed":
                    update_query = """
                        UPDATE phone_number_usage
                        SET outbound_calls = outbound_calls + 1,
                            total_outbound_minutes = total_outbound_minutes + $1,
                            outbound_cost = outbound_cost + $2,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE phone_number_id = $3 AND usage_date = $4
                    """
                    
                    minutes = duration_seconds // 60
                    await database.query(
                        update_query,
                        [minutes, cost, UUID(phone_number_id), today]
                    )
                
                elif status == "failed":
                    update_query = """
                        UPDATE phone_number_usage
                        SET failed_calls = failed_calls + 1,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE phone_number_id = $1 AND usage_date = $2
                    """
                    
                    await database.query(update_query, [UUID(phone_number_id), today])
            
            return True
            
        except Exception as e:
            logger.error(f"Error recording call: {e}")
            return False
    
    @staticmethod
    async def get_daily_usage(
        phone_number_id: str,
        usage_date: date
    ) -> Optional[Dict[str, Any]]:
        """Get daily usage for phone number."""
        try:
            query = """
                SELECT phone_number_id, usage_date, inbound_calls, outbound_calls,
                       missed_calls, failed_calls, busy_calls, total_inbound_minutes,
                       total_outbound_minutes, inbound_cost, outbound_cost
                FROM phone_number_usage
                WHERE phone_number_id = $1 AND usage_date = $2
            """
            
            rows = await database.query(query, [UUID(phone_number_id), usage_date])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting daily usage: {e}")
            return None
    
    @staticmethod
    async def get_monthly_usage(
        phone_number_id: str,
        year: int,
        month: int
    ) -> Dict[str, Any]:
        """Get monthly usage for phone number."""
        try:
            query = """
                SELECT 
                    SUM(inbound_calls) as total_inbound_calls,
                    SUM(outbound_calls) as total_outbound_calls,
                    SUM(missed_calls) as total_missed_calls,
                    SUM(failed_calls) as total_failed_calls,
                    SUM(busy_calls) as total_busy_calls,
                    SUM(total_inbound_minutes) as total_inbound_minutes,
                    SUM(total_outbound_minutes) as total_outbound_minutes,
                    SUM(inbound_cost) as total_inbound_cost,
                    SUM(outbound_cost) as total_outbound_cost
                FROM phone_number_usage
                WHERE phone_number_id = $1
                AND EXTRACT(YEAR FROM usage_date) = $2
                AND EXTRACT(MONTH FROM usage_date) = $3
            """
            
            rows = await database.query(query, [UUID(phone_number_id), year, month])
            
            if rows:
                return rows[0]
            
            return {
                "total_inbound_calls": 0,
                "total_outbound_calls": 0,
                "total_missed_calls": 0,
                "total_failed_calls": 0,
                "total_busy_calls": 0,
                "total_inbound_minutes": 0,
                "total_outbound_minutes": 0,
                "total_inbound_cost": 0,
                "total_outbound_cost": 0
            }
            
        except Exception as e:
            logger.error(f"Error getting monthly usage: {e}")
            return {}
    
    @staticmethod
    async def get_tenant_usage(
        tenant_id: str,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Get usage for all numbers in tenant."""
        try:
            query = """
                SELECT 
                    SUM(inbound_calls) as total_inbound_calls,
                    SUM(outbound_calls) as total_outbound_calls,
                    SUM(missed_calls) as total_missed_calls,
                    SUM(failed_calls) as total_failed_calls,
                    SUM(busy_calls) as total_busy_calls,
                    SUM(total_inbound_minutes) as total_inbound_minutes,
                    SUM(total_outbound_minutes) as total_outbound_minutes,
                    SUM(inbound_cost) as total_inbound_cost,
                    SUM(outbound_cost) as total_outbound_cost
                FROM phone_number_usage pnu
                JOIN phone_numbers pn ON pnu.phone_number_id = pn.id
                WHERE pn.tenant_id = $1
                AND pnu.usage_date >= $2
                AND pnu.usage_date <= $3
            """
            
            rows = await database.query(query, [UUID(tenant_id), start_date, end_date])
            
            if rows:
                return rows[0]
            
            return {
                "total_inbound_calls": 0,
                "total_outbound_calls": 0,
                "total_missed_calls": 0,
                "total_failed_calls": 0,
                "total_busy_calls": 0,
                "total_inbound_minutes": 0,
                "total_outbound_minutes": 0,
                "total_inbound_cost": 0,
                "total_outbound_cost": 0
            }
            
        except Exception as e:
            logger.error(f"Error getting tenant usage: {e}")
            return {}
