"""
Calendar Service.
Manages calendar connections and operations.
"""

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone, timedelta
from api import database
from api.modules.calendar.calendar_provider import (
    GoogleCalendarProvider,
    OutlookCalendarProvider,
    CalendlyProvider
)

logger = logging.getLogger("voice-agent.api.modules.calendar.calendar_service")


class CalendarService:
    """Service for managing calendar operations."""
    
    _providers = {
        "google": GoogleCalendarProvider(),
        "outlook": OutlookCalendarProvider(),
        "calendly": CalendlyProvider()
    }
    
    @staticmethod
    async def create_oauth_connection(
        provider: str,
        tenant_id: str,
        user_id: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """Create OAuth connection."""
        try:
            query = """
                INSERT INTO oauth_connections 
                (provider, tenant_id, user_id, access_token, refresh_token, expires_at, status)
                VALUES ($1, $2, $3, $4, $5, $6, 'active')
                ON CONFLICT (provider, tenant_id, user_id) DO UPDATE
                SET access_token = $4, refresh_token = $5, expires_at = $6, 
                    status = 'active', updated_at = CURRENT_TIMESTAMP
                RETURNING id, provider, tenant_id, user_id, status, created_at
            """
            
            rows = await database.query(
                query,
                [provider, UUID(tenant_id), UUID(user_id), access_token, refresh_token, expires_at]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error creating OAuth connection: {e}")
            return None
    
    @staticmethod
    async def get_oauth_connection(connection_id: str) -> Optional[Dict[str, Any]]:
        """Get OAuth connection."""
        try:
            query = """
                SELECT id, provider, tenant_id, user_id, access_token, refresh_token,
                       expires_at, status, created_at, updated_at
                FROM oauth_connections
                WHERE id = $1
            """
            
            rows = await database.query(query, [UUID(connection_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting OAuth connection: {e}")
            return None
    
    @staticmethod
    async def disconnect_oauth(connection_id: str) -> bool:
        """Disconnect OAuth connection."""
        try:
            query = """
                UPDATE oauth_connections
                SET status = 'revoked', updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
            """
            
            await database.query(query, [UUID(connection_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error disconnecting OAuth: {e}")
            return False
    
    @staticmethod
    async def create_calendar_connection(
        oauth_connection_id: str,
        provider: str,
        calendar_id: str,
        calendar_name: str,
        timezone: Optional[str] = None,
        is_primary: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Create calendar connection."""
        try:
            query = """
                INSERT INTO calendar_connections 
                (oauth_connection_id, provider, calendar_id, calendar_name, timezone, is_primary, is_active)
                VALUES ($1, $2, $3, $4, $5, $6, TRUE)
                RETURNING id, oauth_connection_id, provider, calendar_id, calendar_name, timezone, is_primary, is_active, created_at
            """
            
            rows = await database.query(
                query,
                [UUID(oauth_connection_id), provider, calendar_id, calendar_name, timezone, is_primary]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error creating calendar connection: {e}")
            return None
    
    @staticmethod
    async def get_calendar_connection(calendar_connection_id: str) -> Optional[Dict[str, Any]]:
        """Get calendar connection."""
        try:
            query = """
                SELECT id, oauth_connection_id, provider, calendar_id, calendar_name,
                       timezone, is_primary, is_active, created_at, updated_at
                FROM calendar_connections
                WHERE id = $1
            """
            
            rows = await database.query(query, [UUID(calendar_connection_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting calendar connection: {e}")
            return None
    
    @staticmethod
    async def list_calendars_for_oauth(oauth_connection_id: str) -> List[Dict[str, Any]]:
        """List calendars for OAuth connection."""
        try:
            query = """
                SELECT id, provider, calendar_id, calendar_name, timezone, is_primary, is_active
                FROM calendar_connections
                WHERE oauth_connection_id = $1
                ORDER BY is_primary DESC, created_at ASC
            """
            
            rows = await database.query(query, [UUID(oauth_connection_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error listing calendars: {e}")
            return []
    
    @staticmethod
    async def assign_calendar_to_agent(
        agent_id: str,
        calendar_connection_id: str,
        is_primary: bool = False,
        booking_enabled: bool = True,
        meeting_duration_minutes: int = 30,
        buffer_before_minutes: int = 0,
        buffer_after_minutes: int = 0,
        booking_window_days: int = 90,
        minimum_notice_minutes: int = 0,
        maximum_advance_booking_days: int = 365,
        timezone: Optional[str] = None,
        auto_confirm: bool = True,
        auto_cancel: bool = False,
        auto_reschedule: bool = False,
        maximum_meetings_per_day: int = 10
    ) -> Optional[Dict[str, Any]]:
        """Assign calendar to agent."""
        try:
            query = """
                INSERT INTO agent_calendar_connections 
                (agent_id, calendar_connection_id, is_primary, booking_enabled,
                 meeting_duration_minutes, buffer_before_minutes, buffer_after_minutes,
                 booking_window_days, minimum_notice_minutes, maximum_advance_booking_days,
                 timezone, auto_confirm, auto_cancel, auto_reschedule, maximum_meetings_per_day)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                RETURNING id, agent_id, calendar_connection_id, is_primary, booking_enabled,
                         meeting_duration_minutes, buffer_before_minutes, buffer_after_minutes,
                         booking_window_days, minimum_notice_minutes, maximum_advance_booking_days,
                         timezone, auto_confirm, auto_cancel, auto_reschedule, maximum_meetings_per_day, created_at
            """
            
            rows = await database.query(
                query,
                [UUID(agent_id), UUID(calendar_connection_id), is_primary, booking_enabled,
                 meeting_duration_minutes, buffer_before_minutes, buffer_after_minutes,
                 booking_window_days, minimum_notice_minutes, maximum_advance_booking_days,
                 timezone, auto_confirm, auto_cancel, auto_reschedule, maximum_meetings_per_day]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error assigning calendar to agent: {e}")
            return None
    
    @staticmethod
    async def get_agent_calendars(agent_id: str) -> List[Dict[str, Any]]:
        """Get calendars for agent."""
        try:
            query = """
                SELECT acc.id, acc.agent_id, acc.calendar_connection_id, acc.is_primary,
                       acc.booking_enabled, acc.meeting_duration_minutes, acc.buffer_before_minutes,
                       acc.buffer_after_minutes, acc.booking_window_days, acc.minimum_notice_minutes,
                       acc.maximum_advance_booking_days, acc.timezone, acc.auto_confirm,
                       acc.auto_cancel, acc.auto_reschedule, acc.maximum_meetings_per_day,
                       cc.provider, cc.calendar_id, cc.calendar_name, cc.timezone as calendar_timezone
                FROM agent_calendar_connections acc
                JOIN calendar_connections cc ON acc.calendar_connection_id = cc.id
                WHERE acc.agent_id = $1
                ORDER BY acc.is_primary DESC, acc.created_at ASC
            """
            
            rows = await database.query(query, [UUID(agent_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting agent calendars: {e}")
            return []
    
    @staticmethod
    async def get_primary_calendar(agent_id: str) -> Optional[Dict[str, Any]]:
        """Get primary calendar for agent."""
        try:
            query = """
                SELECT acc.id, acc.agent_id, acc.calendar_connection_id, acc.is_primary,
                       acc.booking_enabled, acc.meeting_duration_minutes, acc.buffer_before_minutes,
                       acc.buffer_after_minutes, acc.booking_window_days, acc.minimum_notice_minutes,
                       acc.maximum_advance_booking_days, acc.timezone, acc.auto_confirm,
                       acc.auto_cancel, acc.auto_reschedule, acc.maximum_meetings_per_day,
                       cc.provider, cc.calendar_id, cc.calendar_name, cc.timezone as calendar_timezone
                FROM agent_calendar_connections acc
                JOIN calendar_connections cc ON acc.calendar_connection_id = cc.id
                WHERE acc.agent_id = $1 AND acc.is_primary = TRUE
                LIMIT 1
            """
            
            rows = await database.query(query, [UUID(agent_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting primary calendar: {e}")
            return None
    
    @staticmethod
    async def remove_calendar_from_agent(agent_id: str, calendar_connection_id: str) -> bool:
        """Remove calendar from agent."""
        try:
            query = """
                DELETE FROM agent_calendar_connections
                WHERE agent_id = $1 AND calendar_connection_id = $2
            """
            
            await database.query(query, [UUID(agent_id), UUID(calendar_connection_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error removing calendar from agent: {e}")
            return False
    
    @staticmethod
    async def get_available_slots(
        agent_calendar_connection_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get available slots for agent calendar."""
        try:
            # Get agent calendar configuration
            query = """
                SELECT acc.*, cc.provider, cc.calendar_id, oc.access_token
                FROM agent_calendar_connections acc
                JOIN calendar_connections cc ON acc.calendar_connection_id = cc.id
                JOIN oauth_connections oc ON cc.oauth_connection_id = oc.id
                WHERE acc.id = $1
            """
            
            rows = await database.query(query, [UUID(agent_calendar_connection_id)])
            if not rows:
                return []
            
            config = rows[0]
            provider = CalendarService._providers.get(config["provider"])
            
            if not provider:
                return []
            
            # Get available slots from provider
            slots = await provider.get_available_slots(
                config["access_token"],
                config["calendar_id"],
                start_date,
                end_date,
                config["meeting_duration_minutes"],
                config["buffer_before_minutes"],
                config["buffer_after_minutes"]
            )
            
            return slots
            
        except Exception as e:
            logger.error(f"Error getting available slots: {e}")
            return []
    
    @staticmethod
    async def create_booking(
        session_id: str,
        agent_calendar_connection_id: str,
        customer_name: str,
        customer_email: str,
        start_time: datetime,
        end_time: datetime,
        timezone: str,
        customer_phone: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create calendar booking."""
        try:
            query = """
                INSERT INTO calendar_bookings 
                (session_id, agent_calendar_connection_id, customer_name, customer_email,
                 customer_phone, start_time, end_time, timezone, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending')
                RETURNING id, session_id, agent_calendar_connection_id, customer_name,
                         customer_email, customer_phone, start_time, end_time, timezone, status, created_at
            """
            
            rows = await database.query(
                query,
                [UUID(session_id), UUID(agent_calendar_connection_id), customer_name,
                 customer_email, customer_phone, start_time, end_time, timezone]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error creating booking: {e}")
            return None
    
    @staticmethod
    async def get_booking(booking_id: str) -> Optional[Dict[str, Any]]:
        """Get booking details."""
        try:
            query = """
                SELECT id, session_id, agent_calendar_connection_id, calendar_event_id,
                       customer_name, customer_email, customer_phone, start_time, end_time,
                       timezone, status, confirmation_sent, reminder_sent, created_at, updated_at
                FROM calendar_bookings
                WHERE id = $1
            """
            
            rows = await database.query(query, [UUID(booking_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting booking: {e}")
            return None
    
    @staticmethod
    async def update_booking_status(booking_id: str, status: str) -> bool:
        """Update booking status."""
        try:
            query = """
                UPDATE calendar_bookings
                SET status = $1, updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
            """
            
            await database.query(query, [status, UUID(booking_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error updating booking status: {e}")
            return False
    
    @staticmethod
    async def create_calendar_event(
        agent_calendar_connection_id: str,
        booking_id: str,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: Optional[str] = None,
        attendees: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Create calendar event from booking."""
        try:
            # Get agent calendar config
            query = """
                SELECT acc.*, cc.provider, cc.calendar_id, oc.access_token
                FROM agent_calendar_connections acc
                JOIN calendar_connections cc ON acc.calendar_connection_id = cc.id
                JOIN oauth_connections oc ON cc.oauth_connection_id = oc.id
                WHERE acc.id = $1
            """
            
            rows = await database.query(query, [UUID(agent_calendar_connection_id)])
            if not rows:
                return None
            
            config = rows[0]
            provider = CalendarService._providers.get(config["provider"])
            
            if not provider:
                return None
            
            # Create event via provider
            event = await provider.create_event(
                config["access_token"],
                config["calendar_id"],
                title,
                start_time,
                end_time,
                description,
                attendees
            )
            
            if not event:
                return None
            
            # Store event in database
            event_query = """
                INSERT INTO calendar_events 
                (agent_calendar_connection_id, provider_event_id, provider, title,
                 description, start_time, end_time, timezone, attendees, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'confirmed')
                RETURNING id, provider_event_id, title, start_time, end_time, status
            """
            
            event_rows = await database.query(
                event_query,
                [UUID(agent_calendar_connection_id), event.get("event_id"), config["provider"],
                 title, description, start_time, end_time, config.get("timezone"), attendees]
            )
            
            if event_rows:
                # Link booking to event
                booking_update = """
                    UPDATE calendar_bookings
                    SET calendar_event_id = $1, status = 'confirmed', updated_at = CURRENT_TIMESTAMP
                    WHERE id = $2
                """
                
                await database.query(booking_update, [UUID(event_rows[0]["id"]), UUID(booking_id)])
                
                return event_rows[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error creating calendar event: {e}")
            return None
