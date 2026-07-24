"""
Event Bus.
Internal event architecture for workflow automation.
Decouples workflow nodes from service calls.
"""

import logging
from typing import Optional, Dict, Any, Callable, List
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.event_bus")


class EventType(Enum):
    """Supported event types."""
    CALL_STARTED = "call_started"
    CALL_ENDED = "call_ended"
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    AGENT_ASSIGNED = "agent_assigned"
    AGENT_TRANSFERRED = "agent_transferred"
    CONVERSATION_HANDOFF = "conversation_handoff"
    PLUGIN_EXECUTED = "plugin_executed"
    CUSTOMER_VERIFIED = "customer_verified"
    SUPERVISOR_NOTIFIED = "supervisor_notified"
    SUPERVISOR_ESCALATED = "supervisor_escalated"
    CAPABILITY_ASSIGNED = "capability_assigned"
    CONTEXT_UPDATED = "context_updated"
    STEP_EXECUTED = "step_executed"
    CONDITION_EVALUATED = "condition_evaluated"
    ACTION_EXECUTED = "action_executed"
    CALENDAR_CONNECTED = "calendar_connected"
    CALENDAR_DISCONNECTED = "calendar_disconnected"
    AVAILABILITY_CHECKED = "availability_checked"
    SLOTS_GENERATED = "slots_generated"
    MEETING_BOOKED = "meeting_booked"
    MEETING_UPDATED = "meeting_updated"
    MEETING_CANCELLED = "meeting_cancelled"
    MEETING_RESCHEDULED = "meeting_rescheduled"
    SLOT_RESERVED = "slot_reserved"
    SLOT_RELEASED = "slot_released"
    BOOKING_CONFLICT_DETECTED = "booking_conflict_detected"
    CALENDAR_SYNCED = "calendar_synced"
    WEBHOOK_PROCESSED = "webhook_processed"
    TOKEN_REFRESHED = "token_refreshed"
    AVAILABILITY_GENERATED = "availability_generated"
    HEALTH_STATUS_CHANGED = "health_status_changed"


class WorkflowEvent:
    """Represents a workflow event."""
    
    def __init__(
        self,
        event_type: EventType,
        execution_id: str,
        data: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ):
        self.event_type = event_type
        self.execution_id = execution_id
        self.data = data or {}
        self.timestamp = timestamp or datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_type": self.event_type.value,
            "execution_id": self.execution_id,
            "data": self.data,
            "timestamp": self.timestamp.isoformat()
        }


class EventHandler:
    """Handler for workflow events."""
    
    def __init__(self, event_type: EventType, handler_func: Callable):
        self.event_type = event_type
        self.handler_func = handler_func
    
    async def handle(self, event: WorkflowEvent) -> bool:
        """Handle an event."""
        try:
            await self.handler_func(event)
            return True
        except Exception as e:
            logger.error(f"Error handling event {self.event_type.value}: {e}")
            return False


class EventBus:
    """Central event bus for workflow automation."""
    
    _handlers: Dict[EventType, List[EventHandler]] = {
        event_type: [] for event_type in EventType
    }
    
    _event_history: List[WorkflowEvent] = []
    
    @staticmethod
    def subscribe(event_type: EventType, handler_func: Callable) -> EventHandler:
        """Subscribe to an event type."""
        try:
            handler = EventHandler(event_type, handler_func)
            EventBus._handlers[event_type].append(handler)
            logger.info(f"Subscribed to event: {event_type.value}")
            return handler
        except Exception as e:
            logger.error(f"Error subscribing to event: {e}")
            return None
    
    @staticmethod
    def unsubscribe(event_type: EventType, handler: EventHandler) -> bool:
        """Unsubscribe from an event type."""
        try:
            EventBus._handlers[event_type].remove(handler)
            logger.info(f"Unsubscribed from event: {event_type.value}")
            return True
        except Exception as e:
            logger.error(f"Error unsubscribing from event: {e}")
            return False
    
    @staticmethod
    async def publish(event: WorkflowEvent) -> bool:
        """Publish an event to all subscribers."""
        try:
            # Store in history
            EventBus._event_history.append(event)
            
            # Get handlers for this event type
            handlers = EventBus._handlers.get(event.event_type, [])
            
            # Execute all handlers
            for handler in handlers:
                await handler.handle(event)
            
            logger.info(f"Published event: {event.event_type.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error publishing event: {e}")
            return False
    
    @staticmethod
    async def publish_call_started(execution_id: str, phone_number: str) -> bool:
        """Publish call started event."""
        event = WorkflowEvent(
            EventType.CALL_STARTED,
            execution_id,
            {"phone_number": phone_number}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    async def publish_workflow_started(execution_id: str, workflow_id: str) -> bool:
        """Publish workflow started event."""
        event = WorkflowEvent(
            EventType.WORKFLOW_STARTED,
            execution_id,
            {"workflow_id": workflow_id}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    async def publish_workflow_completed(execution_id: str, workflow_id: str, duration_ms: int) -> bool:
        """Publish workflow completed event."""
        event = WorkflowEvent(
            EventType.WORKFLOW_COMPLETED,
            execution_id,
            {"workflow_id": workflow_id, "duration_ms": duration_ms}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    async def publish_workflow_failed(execution_id: str, workflow_id: str, error: str) -> bool:
        """Publish workflow failed event."""
        event = WorkflowEvent(
            EventType.WORKFLOW_FAILED,
            execution_id,
            {"workflow_id": workflow_id, "error": error}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    async def publish_agent_assigned(execution_id: str, agent_id: str) -> bool:
        """Publish agent assigned event."""
        event = WorkflowEvent(
            EventType.AGENT_ASSIGNED,
            execution_id,
            {"agent_id": agent_id}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    async def publish_agent_transferred(execution_id: str, from_agent_id: str, to_agent_id: str) -> bool:
        """Publish agent transferred event."""
        event = WorkflowEvent(
            EventType.AGENT_TRANSFERRED,
            execution_id,
            {"from_agent_id": from_agent_id, "to_agent_id": to_agent_id}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    async def publish_plugin_executed(execution_id: str, plugin_type: str, status: str) -> bool:
        """Publish plugin executed event."""
        event = WorkflowEvent(
            EventType.PLUGIN_EXECUTED,
            execution_id,
            {"plugin_type": plugin_type, "status": status}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    async def publish_supervisor_notified(execution_id: str, alert_type: str, message: str) -> bool:
        """Publish supervisor notified event."""
        event = WorkflowEvent(
            EventType.SUPERVISOR_NOTIFIED,
            execution_id,
            {"alert_type": alert_type, "message": message}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    async def publish_supervisor_escalated(execution_id: str, reason: str) -> bool:
        """Publish supervisor escalated event."""
        event = WorkflowEvent(
            EventType.SUPERVISOR_ESCALATED,
            execution_id,
            {"reason": reason}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    async def publish_calendar_connected(execution_id: str, provider: str) -> bool:
        """Publish calendar connected event."""
        event = WorkflowEvent(
            EventType.CALENDAR_CONNECTED,
            execution_id,
            {"provider": provider}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    async def publish_calendar_disconnected(execution_id: str, provider: str) -> bool:
        """Publish calendar disconnected event."""
        event = WorkflowEvent(
            EventType.CALENDAR_DISCONNECTED,
            execution_id,
            {"provider": provider}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    async def publish_availability_checked(execution_id: str, slots_count: int) -> bool:
        """Publish availability checked event."""
        event = WorkflowEvent(
            EventType.AVAILABILITY_CHECKED,
            execution_id,
            {"slots_count": slots_count}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    async def publish_slots_generated(execution_id: str, slots_count: int) -> bool:
        """Publish slots generated event."""
        event = WorkflowEvent(
            EventType.SLOTS_GENERATED,
            execution_id,
            {"slots_count": slots_count}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    async def publish_meeting_booked(execution_id: str, booking_id: str) -> bool:
        """Publish meeting booked event."""
        event = WorkflowEvent(
            EventType.MEETING_BOOKED,
            execution_id,
            {"booking_id": booking_id}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    async def publish_meeting_updated(execution_id: str, booking_id: str) -> bool:
        """Publish meeting updated event."""
        event = WorkflowEvent(
            EventType.MEETING_UPDATED,
            execution_id,
            {"booking_id": booking_id}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    async def publish_meeting_cancelled(execution_id: str, booking_id: str) -> bool:
        """Publish meeting cancelled event."""
        event = WorkflowEvent(
            EventType.MEETING_CANCELLED,
            execution_id,
            {"booking_id": booking_id}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    async def publish_meeting_rescheduled(execution_id: str, booking_id: str) -> bool:
        """Publish meeting rescheduled event."""
        event = WorkflowEvent(
            EventType.MEETING_RESCHEDULED,
            execution_id,
            {"booking_id": booking_id}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    async def publish_slot_reserved(execution_id: str, slot_id: str) -> bool:
        """Publish slot reserved event."""
        event = WorkflowEvent(
            EventType.SLOT_RESERVED,
            execution_id,
            {"slot_id": slot_id}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    async def publish_slot_released(execution_id: str, slot_id: str) -> bool:
        """Publish slot released event."""
        event = WorkflowEvent(
            EventType.SLOT_RELEASED,
            execution_id,
            {"slot_id": slot_id}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    async def publish_booking_conflict_detected(execution_id: str, conflict_type: str) -> bool:
        """Publish booking conflict detected event."""
        event = WorkflowEvent(
            EventType.BOOKING_CONFLICT_DETECTED,
            execution_id,
            {"conflict_type": conflict_type}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    async def publish_calendar_synced(execution_id: str, events_synced: int) -> bool:
        """Publish calendar synced event."""
        event = WorkflowEvent(
            EventType.CALENDAR_SYNCED,
            execution_id,
            {"events_synced": events_synced}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    async def publish_webhook_processed(execution_id: str, webhook_type: str) -> bool:
        """Publish webhook processed event."""
        event = WorkflowEvent(
            EventType.WEBHOOK_PROCESSED,
            execution_id,
            {"webhook_type": webhook_type}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    async def publish_token_refreshed(execution_id: str, provider: str) -> bool:
        """Publish token refreshed event."""
        event = WorkflowEvent(
            EventType.TOKEN_REFRESHED,
            execution_id,
            {"provider": provider}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    async def publish_availability_generated(execution_id: str, slots_count: int) -> bool:
        """Publish availability generated event."""
        event = WorkflowEvent(
            EventType.AVAILABILITY_GENERATED,
            execution_id,
            {"slots_count": slots_count}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    async def publish_health_status_changed(execution_id: str, status: str) -> bool:
        """Publish health status changed event."""
        event = WorkflowEvent(
            EventType.HEALTH_STATUS_CHANGED,
            execution_id,
            {"status": status}
        )
        return await EventBus.publish(event)
    
    @staticmethod
    def get_event_history(execution_id: str) -> List[Dict[str, Any]]:
        """Get event history for an execution."""
        try:
            events = [
                event.to_dict() for event in EventBus._event_history
                if event.execution_id == execution_id
            ]
            return events
        except Exception as e:
            logger.error(f"Error getting event history: {e}")
            return []
    
    @staticmethod
    def clear_history() -> bool:
        """Clear event history (for testing)."""
        try:
            EventBus._event_history.clear()
            return True
        except Exception as e:
            logger.error(f"Error clearing history: {e}")
            return False
