"""
Supervisor Engine.
AI Supervisor for monitoring conversations and workflows.
Detects issues and takes corrective actions.
"""

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone
from api import database
from api.modules.phone_numbers.event_bus import EventBus, EventType

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.supervisor_engine")


class SupervisorEngine:
    """AI Supervisor for workflow monitoring."""
    
    # Alert thresholds
    LOW_CONFIDENCE_THRESHOLD = 0.5
    REPEATED_FAILURE_THRESHOLD = 3
    LONG_SILENCE_THRESHOLD_SECONDS = 300  # 5 minutes
    REPEATED_TRANSFERS_THRESHOLD = 3
    
    @staticmethod
    async def monitor_execution(
        execution_id: str,
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Monitor a workflow execution for issues.
        
        Returns alert if issue detected, None otherwise.
        """
        try:
            # Check for low confidence
            if context.get("intent_confidence", 1.0) < SupervisorEngine.LOW_CONFIDENCE_THRESHOLD:
                return await SupervisorEngine.create_alert(
                    execution_id,
                    "low_confidence",
                    "warning",
                    f"Intent confidence {context.get('intent_confidence')} below threshold",
                    context
                )
            
            # Check for repeated failures
            failure_count = context.get("failure_count", 0)
            if failure_count >= SupervisorEngine.REPEATED_FAILURE_THRESHOLD:
                return await SupervisorEngine.create_alert(
                    execution_id,
                    "repeated_failure",
                    "critical",
                    f"Workflow failed {failure_count} times",
                    context
                )
            
            # Check for negative sentiment
            sentiment = context.get("sentiment", "neutral")
            if sentiment == "negative":
                return await SupervisorEngine.create_alert(
                    execution_id,
                    "negative_sentiment",
                    "warning",
                    "Customer expressing negative sentiment",
                    context
                )
            
            # Check for repeated transfers
            transfer_count = context.get("transfer_count", 0)
            if transfer_count >= SupervisorEngine.REPEATED_TRANSFERS_THRESHOLD:
                return await SupervisorEngine.create_alert(
                    execution_id,
                    "repeated_transfers",
                    "critical",
                    f"Customer transferred {transfer_count} times",
                    context
                )
            
            # Check for long silence
            last_activity = context.get("last_activity_timestamp")
            if last_activity:
                silence_duration = (datetime.now(timezone.utc) - last_activity).total_seconds()
                if silence_duration > SupervisorEngine.LONG_SILENCE_THRESHOLD_SECONDS:
                    return await SupervisorEngine.create_alert(
                        execution_id,
                        "long_silence",
                        "warning",
                        f"No activity for {silence_duration} seconds",
                        context
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Error monitoring execution: {e}")
            return None
    
    @staticmethod
    async def create_alert(
        execution_id: str,
        alert_type: str,
        severity: str,
        message: str,
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Create a supervisor alert."""
        try:
            query = """
                INSERT INTO supervisor_alerts 
                (execution_id, alert_type, severity, message, context)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id, execution_id, alert_type, severity, message, created_at
            """
            
            rows = await database.query(
                query,
                [UUID(execution_id), alert_type, severity, message, context]
            )
            
            if rows:
                alert = rows[0]
                
                # Publish event
                await EventBus.publish_supervisor_notified(
                    execution_id,
                    alert_type,
                    message
                )
                
                return alert
            
            return None
            
        except Exception as e:
            logger.error(f"Error creating alert: {e}")
            return None
    
    @staticmethod
    async def get_alert(alert_id: str) -> Optional[Dict[str, Any]]:
        """Get alert details."""
        try:
            query = """
                SELECT id, execution_id, alert_type, severity, message, context,
                       action_taken, resolved, resolved_at, created_at
                FROM supervisor_alerts
                WHERE id = $1
            """
            
            rows = await database.query(query, [UUID(alert_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting alert: {e}")
            return None
    
    @staticmethod
    async def get_execution_alerts(execution_id: str) -> List[Dict[str, Any]]:
        """Get all alerts for an execution."""
        try:
            query = """
                SELECT id, execution_id, alert_type, severity, message,
                       action_taken, resolved, created_at
                FROM supervisor_alerts
                WHERE execution_id = $1
                ORDER BY created_at DESC
            """
            
            rows = await database.query(query, [UUID(execution_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting execution alerts: {e}")
            return []
    
    @staticmethod
    async def take_action(
        alert_id: str,
        action: str,
        reason: Optional[str] = None
    ) -> bool:
        """Take action on an alert."""
        try:
            if action not in ["notify", "takeover", "escalate", "terminate", "restart"]:
                logger.error(f"Invalid action: {action}")
                return False
            
            query = """
                UPDATE supervisor_alerts
                SET action_taken = $1, resolved = TRUE, resolved_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
            """
            
            await database.query(query, [action, UUID(alert_id)])
            
            # Get alert for event publishing
            alert = await SupervisorEngine.get_alert(alert_id)
            if alert:
                if action == "escalate":
                    await EventBus.publish_supervisor_escalated(
                        str(alert["execution_id"]),
                        reason or "Supervisor escalation"
                    )
            
            return True
            
        except Exception as e:
            logger.error(f"Error taking action: {e}")
            return False
    
    @staticmethod
    async def get_unresolved_alerts() -> List[Dict[str, Any]]:
        """Get all unresolved alerts."""
        try:
            query = """
                SELECT id, execution_id, alert_type, severity, message,
                       context, created_at
                FROM supervisor_alerts
                WHERE resolved = FALSE
                ORDER BY severity DESC, created_at DESC
            """
            
            rows = await database.query(query)
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting unresolved alerts: {e}")
            return []
    
    @staticmethod
    async def get_critical_alerts() -> List[Dict[str, Any]]:
        """Get all critical alerts."""
        try:
            query = """
                SELECT id, execution_id, alert_type, severity, message,
                       context, created_at
                FROM supervisor_alerts
                WHERE severity = 'critical' AND resolved = FALSE
                ORDER BY created_at DESC
            """
            
            rows = await database.query(query)
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting critical alerts: {e}")
            return []
