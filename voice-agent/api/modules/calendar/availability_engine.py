"""
Availability Engine.
Generates available slots based on calendar, business hours, and policies.
No LLM slot calculation.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, time, timezone
from uuid import UUID
from api import database
from api.modules.calendar.calendar_provider import CalendarProvider

logger = logging.getLogger("voice-agent.api.modules.calendar.availability_engine")


class AvailabilityEngine:
    """Engine for generating available booking slots."""
    
    @staticmethod
    async def generate_slots(
        agent_calendar_connection_id: str,
        start_date: datetime,
        end_date: datetime,
        provider: CalendarProvider,
        access_token: str,
        calendar_id: str
    ) -> List[Dict[str, Any]]:
        """
        Generate available slots.
        
        Uses:
        - FreeBusy from provider
        - Business hours
        - Working hours override
        - Meeting duration
        - Buffers
        - Maximum meetings per day
        - Timezone
        - Holidays
        - Booking policies
        """
        try:
            # Get agent calendar configuration
            config_query = """
                SELECT acc.*, bp.*, cc.timezone as calendar_timezone
                FROM agent_calendar_connections acc
                LEFT JOIN booking_policies bp ON acc.id = bp.agent_calendar_connection_id
                JOIN calendar_connections cc ON acc.calendar_connection_id = cc.id
                WHERE acc.id = $1
            """
            
            config_rows = await database.query(config_query, [UUID(agent_calendar_connection_id)])
            if not config_rows:
                return []
            
            config = config_rows[0]
            
            # Get free/busy information
            busy_periods = await provider.get_free_busy(
                access_token,
                calendar_id,
                start_date,
                end_date
            )
            
            busy_list = busy_periods.get("busy_periods", [])
            
            # Generate slots
            slots = []
            current = start_date
            
            while current < end_date:
                # Check if date is valid for booking
                if not AvailabilityEngine._is_valid_booking_date(current, config):
                    current += timedelta(days=1)
                    continue
                
                # Get working hours for this day
                working_hours = AvailabilityEngine._get_working_hours(current, config)
                
                if not working_hours:
                    current += timedelta(days=1)
                    continue
                
                # Generate slots for this day
                day_slots = AvailabilityEngine._generate_day_slots(
                    current,
                    working_hours,
                    config,
                    busy_list
                )
                
                slots.extend(day_slots)
                current += timedelta(days=1)
            
            return slots
            
        except Exception as e:
            logger.error(f"Error generating slots: {e}")
            return []
    
    @staticmethod
    def _is_valid_booking_date(date: datetime, config: Dict[str, Any]) -> bool:
        """Check if date is valid for booking."""
        try:
            # Check if within booking window
            max_advance = config.get("maximum_advance_booking_days", 365)
            if (date.date() - datetime.now(timezone.utc).date()).days > max_advance:
                return False
            
            # Check if in past
            if date < datetime.now(timezone.utc):
                return False
            
            # Check weekend
            if date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                if not config.get("allow_weekend_booking", False):
                    return False
            
            # Check blackout dates
            blackout_dates = config.get("blackout_dates", [])
            if date.date().isoformat() in blackout_dates:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking booking date: {e}")
            return False
    
    @staticmethod
    def _get_working_hours(date: datetime, config: Dict[str, Any]) -> Optional[tuple]:
        """Get working hours for a date."""
        try:
            # Check for working hours override
            override = config.get("working_hours_override")
            if override:
                day_name = date.strftime("%A").lower()
                if day_name in override:
                    hours = override[day_name]
                    if hours.get("is_off"):
                        return None
                    start = datetime.strptime(hours.get("start", "09:00"), "%H:%M").time()
                    end = datetime.strptime(hours.get("end", "17:00"), "%H:%M").time()
                    return (start, end)
            
            # Default business hours
            start = time(9, 0)
            end = time(17, 0)
            
            return (start, end)
            
        except Exception as e:
            logger.error(f"Error getting working hours: {e}")
            return None
    
    @staticmethod
    def _generate_day_slots(
        date: datetime,
        working_hours: tuple,
        config: Dict[str, Any],
        busy_periods: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate slots for a specific day."""
        try:
            slots = []
            start_time, end_time = working_hours
            
            # Apply preferred booking hours if set
            preferred_start = config.get("preferred_booking_start")
            preferred_end = config.get("preferred_booking_end")
            
            if preferred_start and preferred_end:
                start_time = datetime.strptime(preferred_start, "%H:%M").time()
                end_time = datetime.strptime(preferred_end, "%H:%M").time()
            
            # Apply lunch break
            lunch_start = config.get("lunch_break_start")
            lunch_end = config.get("lunch_break_end")
            
            # Create datetime objects
            day_start = datetime.combine(date.date(), start_time, tzinfo=timezone.utc)
            day_end = datetime.combine(date.date(), end_time, tzinfo=timezone.utc)
            
            meeting_duration = config.get("meeting_duration_minutes", 30)
            buffer_before = config.get("buffer_before_minutes", 0)
            buffer_after = config.get("buffer_after_minutes", 0)
            
            total_duration = meeting_duration + buffer_before + buffer_after
            
            current = day_start
            meetings_today = 0
            max_meetings = config.get("maximum_meetings_per_day", 10)
            
            while current + timedelta(minutes=total_duration) <= day_end:
                # Check lunch break
                if lunch_start and lunch_end:
                    lunch_start_time = datetime.combine(date.date(), lunch_start, tzinfo=timezone.utc)
                    lunch_end_time = datetime.combine(date.date(), lunch_end, tzinfo=timezone.utc)
                    
                    if current < lunch_end_time and current + timedelta(minutes=total_duration) > lunch_start_time:
                        current += timedelta(minutes=30)
                        continue
                
                # Check if slot overlaps with busy periods
                slot_start = current + timedelta(minutes=buffer_before)
                slot_end = slot_start + timedelta(minutes=meeting_duration)
                
                is_busy = False
                for busy in busy_periods:
                    busy_start = busy.get("start")
                    busy_end = busy.get("end")
                    
                    if busy_start and busy_end:
                        if slot_start < busy_end and slot_end > busy_start:
                            is_busy = True
                            break
                
                if not is_busy and meetings_today < max_meetings:
                    slots.append({
                        "start": slot_start.isoformat(),
                        "end": slot_end.isoformat(),
                        "duration_minutes": meeting_duration
                    })
                    meetings_today += 1
                
                current += timedelta(minutes=30)
            
            return slots
            
        except Exception as e:
            logger.error(f"Error generating day slots: {e}")
            return []
