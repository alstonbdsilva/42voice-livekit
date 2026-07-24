"""
Business Hours Service.
Manages business hours profiles and scheduling.
"""

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone
from api import database

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.business_hours_service")


class BusinessHoursService:
    """Service for managing business hours profiles."""
    
    @staticmethod
    async def create_profile(
        name: str,
        timezone: str,
        user_id: str,
        client_id: Optional[str] = None,
        monday: Optional[Dict] = None,
        tuesday: Optional[Dict] = None,
        wednesday: Optional[Dict] = None,
        thursday: Optional[Dict] = None,
        friday: Optional[Dict] = None,
        saturday: Optional[Dict] = None,
        sunday: Optional[Dict] = None,
        holiday_calendar: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new business hours profile."""
        try:
            query = """
                INSERT INTO business_hours_profiles 
                (name, timezone, monday, tuesday, wednesday, thursday, friday, saturday, sunday, holiday_calendar, user_id, client_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                RETURNING id, name, timezone, monday, tuesday, wednesday, thursday, friday, saturday, sunday, holiday_calendar, created_at
            """
            
            rows = await database.query(
                query,
                [name, timezone, monday, tuesday, wednesday, thursday, friday, saturday, sunday, 
                 holiday_calendar, UUID(user_id), UUID(client_id) if client_id else None]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error creating business hours profile: {e}")
            return None
    
    @staticmethod
    async def get_profile(profile_id: str) -> Optional[Dict[str, Any]]:
        """Get business hours profile."""
        try:
            query = """
                SELECT id, name, timezone, monday, tuesday, wednesday, thursday, friday, saturday, sunday, 
                       holiday_calendar, user_id, client_id, created_at, updated_at
                FROM business_hours_profiles
                WHERE id = $1
            """
            
            rows = await database.query(query, [UUID(profile_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting business hours profile: {e}")
            return None
    
    @staticmethod
    async def get_user_profiles(user_id: str) -> List[Dict[str, Any]]:
        """Get all business hours profiles for a user."""
        try:
            query = """
                SELECT id, name, timezone, user_id, client_id, created_at, updated_at
                FROM business_hours_profiles
                WHERE user_id = $1
                ORDER BY created_at DESC
            """
            
            rows = await database.query(query, [UUID(user_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting user profiles: {e}")
            return []
    
    @staticmethod
    async def get_client_profiles(client_id: str) -> List[Dict[str, Any]]:
        """Get all business hours profiles for a client."""
        try:
            query = """
                SELECT id, name, timezone, user_id, client_id, created_at, updated_at
                FROM business_hours_profiles
                WHERE client_id = $1
                ORDER BY created_at DESC
            """
            
            rows = await database.query(query, [UUID(client_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting client profiles: {e}")
            return []
    
    @staticmethod
    async def update_profile(
        profile_id: str,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Update business hours profile."""
        try:
            allowed_fields = ["name", "timezone", "monday", "tuesday", "wednesday", "thursday", 
                            "friday", "saturday", "sunday", "holiday_calendar"]
            updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
            
            if not updates:
                return await BusinessHoursService.get_profile(profile_id)
            
            set_clause = ", ".join([f"{k} = ${i+1}" for i, k in enumerate(updates.keys())])
            values = list(updates.values()) + [UUID(profile_id)]
            
            query = f"""
                UPDATE business_hours_profiles
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ${len(values)}
                RETURNING id, name, timezone, monday, tuesday, wednesday, thursday, friday, saturday, sunday, holiday_calendar, created_at, updated_at
            """
            
            rows = await database.query(query, values)
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error updating business hours profile: {e}")
            return None
    
    @staticmethod
    async def delete_profile(profile_id: str) -> bool:
        """Delete a business hours profile."""
        try:
            query = "DELETE FROM business_hours_profiles WHERE id = $1"
            await database.query(query, [UUID(profile_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error deleting business hours profile: {e}")
            return False
    
    @staticmethod
    async def is_business_hours(
        profile_id: str,
        check_time: Optional[datetime] = None
    ) -> bool:
        """
        Check if current time is within business hours.
        Extension point for future implementation.
        """
        try:
            if not check_time:
                check_time = datetime.now(timezone.utc)
            
            profile = await BusinessHoursService.get_profile(profile_id)
            if not profile:
                return True  # Default to business hours if profile not found
            
            # Future implementation: parse day/time from profile
            # For now, return True (always business hours)
            return True
            
        except Exception as e:
            logger.error(f"Error checking business hours: {e}")
            return True
    
    @staticmethod
    async def get_after_hours_agent(
        phone_number_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get after-hours agent for a phone number.
        Extension point for future implementation.
        """
        try:
            query = """
                SELECT pn.after_hours_agent_id, a.id, a.name, a.type, a.status
                FROM phone_numbers pn
                LEFT JOIN agents a ON pn.after_hours_agent_id = a.id
                WHERE pn.id = $1
            """
            
            rows = await database.query(query, [UUID(phone_number_id)])
            if rows and rows[0].get("after_hours_agent_id"):
                return {
                    "agent_id": rows[0]["after_hours_agent_id"],
                    "name": rows[0]["name"],
                    "type": rows[0]["type"],
                    "status": rows[0]["status"]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting after-hours agent: {e}")
            return None
