"""
Mock Calendar Provider.
Implements CalendarProvider interface for testing.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from api.modules.calendar.calendar_provider import CalendarProvider

logger = logging.getLogger("voice-agent.api.modules.calendar.mock_provider")


class MockCalendarProvider(CalendarProvider):
    """Mock calendar provider for testing."""
    
    def __init__(self):
        """Initialize mock provider."""
        self.events = {}
        self.calendars = {
            "primary": {
                "calendar_id": "primary",
                "calendar_name": "Primary Calendar",
                "timezone": "UTC",
                "is_primary": True
            }
        }
    
    async def connect(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Connect to mock calendar."""
        try:
            return {
                "status": "success",
                "access_token": "mock_token_" + str(uuid4()),
                "refresh_token": "mock_refresh_" + str(uuid4()),
                "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                "error": None
            }
        except Exception as e:
            return {
                "status": "failed",
                "access_token": None,
                "refresh_token": None,
                "expires_at": None,
                "error": str(e)
            }
    
    async def disconnect(self, access_token: str) -> bool:
        """Disconnect from mock calendar."""
        return True
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh mock token."""
        try:
            return {
                "status": "success",
                "access_token": "mock_token_" + str(uuid4()),
                "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                "error": None
            }
        except Exception as e:
            return {
                "status": "failed",
                "access_token": None,
                "expires_at": None,
                "error": str(e)
            }
    
    async def list_calendars(self, access_token: str) -> List[Dict[str, Any]]:
        """List mock calendars."""
        try:
            return list(self.calendars.values())
        except Exception as e:
            logger.error(f"Error listing calendars: {e}")
            return []
    
    async def get_calendar(self, access_token: str, calendar_id: str) -> Optional[Dict[str, Any]]:
        """Get mock calendar."""
        try:
            return self.calendars.get(calendar_id)
        except Exception as e:
            logger.error(f"Error getting calendar: {e}")
            return None
    
    async def get_free_busy(
        self,
        access_token: str,
        calendar_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """Get mock free/busy."""
        try:
            busy_periods = []
            
            # Return any events in the time range
            for event_id, event in self.events.items():
                event_start = datetime.fromisoformat(event.get("start_time"))
                event_end = datetime.fromisoformat(event.get("end_time"))
                
                if event_start < end_time and event_end > start_time:
                    busy_periods.append({
                        "start": event_start.isoformat(),
                        "end": event_end.isoformat()
                    })
            
            return {"busy_periods": busy_periods}
            
        except Exception as e:
            logger.error(f"Error getting free/busy: {e}")
            return {"busy_periods": []}
    
    async def get_available_slots(
        self,
        access_token: str,
        calendar_id: str,
        start_time: datetime,
        end_time: datetime,
        duration_minutes: int,
        buffer_before_minutes: int = 0,
        buffer_after_minutes: int = 0
    ) -> List[Dict[str, Any]]:
        """Get mock available slots."""
        try:
            slots = []
            current = start_time
            
            while current + timedelta(minutes=duration_minutes) <= end_time:
                # Check if slot is free
                slot_end = current + timedelta(minutes=duration_minutes)
                is_busy = False
                
                for event_id, event in self.events.items():
                    event_start = datetime.fromisoformat(event.get("start_time"))
                    event_end = datetime.fromisoformat(event.get("end_time"))
                    
                    if current < event_end and slot_end > event_start:
                        is_busy = True
                        break
                
                if not is_busy:
                    slots.append({
                        "start": current.isoformat(),
                        "end": slot_end.isoformat(),
                        "duration_minutes": duration_minutes
                    })
                
                current += timedelta(minutes=30)
            
            return slots
            
        except Exception as e:
            logger.error(f"Error getting available slots: {e}")
            return []
    
    async def create_event(
        self,
        access_token: str,
        calendar_id: str,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: Optional[str] = None,
        attendees: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Create mock event."""
        try:
            event_id = str(uuid4())
            event = {
                "event_id": event_id,
                "title": title,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "description": description,
                "attendees": attendees or [],
                "status": "confirmed"
            }
            
            self.events[event_id] = event
            return event
            
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            return None
    
    async def update_event(
        self,
        access_token: str,
        calendar_id: str,
        event_id: str,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Update mock event."""
        try:
            if event_id not in self.events:
                return None
            
            event = self.events[event_id]
            event.update(kwargs)
            return event
            
        except Exception as e:
            logger.error(f"Error updating event: {e}")
            return None
    
    async def cancel_event(
        self,
        access_token: str,
        calendar_id: str,
        event_id: str
    ) -> bool:
        """Cancel mock event."""
        try:
            if event_id in self.events:
                self.events[event_id]["status"] = "cancelled"
            return True
        except Exception as e:
            logger.error(f"Error cancelling event: {e}")
            return False
    
    async def delete_event(
        self,
        access_token: str,
        calendar_id: str,
        event_id: str
    ) -> bool:
        """Delete mock event."""
        try:
            if event_id in self.events:
                del self.events[event_id]
            return True
        except Exception as e:
            logger.error(f"Error deleting event: {e}")
            return False
    
    async def get_event(
        self,
        access_token: str,
        calendar_id: str,
        event_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get mock event."""
        try:
            return self.events.get(event_id)
        except Exception as e:
            logger.error(f"Error getting event: {e}")
            return None
    
    async def list_events(
        self,
        access_token: str,
        calendar_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """List mock events."""
        try:
            events = []
            
            for event_id, event in self.events.items():
                event_start = datetime.fromisoformat(event.get("start_time"))
                event_end = datetime.fromisoformat(event.get("end_time"))
                
                if event_start < end_time and event_end > start_time:
                    events.append(event)
            
            return events
            
        except Exception as e:
            logger.error(f"Error listing events: {e}")
            return []
    
    async def watch_calendar(
        self,
        access_token: str,
        calendar_id: str,
        webhook_url: str
    ) -> Optional[Dict[str, Any]]:
        """Set up mock watch."""
        try:
            return {
                "webhook_id": str(uuid4()),
                "webhook_url": webhook_url,
                "status": "active"
            }
        except Exception as e:
            logger.error(f"Error setting up watch: {e}")
            return None
