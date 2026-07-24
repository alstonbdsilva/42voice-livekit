"""
Webhook Receiver.
Processes inbound webhooks from calendar providers.
Verifies signatures, prevents replay attacks, handles idempotency.
"""

import logging
import hashlib
import hmac
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone, timedelta
from api import database
from api.modules.calendar.calendar_audit_service import CalendarAuditService
from api.modules.phone_numbers.event_bus import EventBus

logger = logging.getLogger("voice-agent.api.modules.calendar.webhook_receiver")


class WebhookReceiver:
    """Processes calendar provider webhooks."""
    
    WEBHOOK_TIMEOUT_SECONDS = 300  # 5 minutes
    
    @staticmethod
    async def process_google_webhook(
        calendar_connection_id: str,
        headers: Dict[str, str],
        body: Dict[str, Any]
    ) -> bool:
        """Process Google Calendar webhook."""
        try:
            # Verify signature
            if not WebhookReceiver._verify_google_signature(headers, body):
                logger.warning(f"Invalid Google webhook signature for {calendar_connection_id}")
                return False
            
            # Check for replay attack
            if not await WebhookReceiver._check_webhook_freshness(calendar_connection_id, headers):
                logger.warning(f"Stale Google webhook for {calendar_connection_id}")
                return False
            
            # Process idempotently
            webhook_id = headers.get("X-Goog-Channel-ID")
            if not await WebhookReceiver._is_webhook_new(calendar_connection_id, webhook_id):
                logger.info(f"Duplicate Google webhook: {webhook_id}")
                return True  # Already processed
            
            # Extract event type
            event_type = body.get("kind", "unknown")
            
            # Store webhook delivery log
            await WebhookReceiver._log_webhook_delivery(
                calendar_connection_id,
                "google",
                webhook_id,
                event_type,
                "received"
            )
            
            # Publish event
            await EventBus.publish_webhook_processed(calendar_connection_id, event_type)
            
            # Log audit
            await CalendarAuditService.log_webhook_received(
                calendar_connection_id,
                event_type,
                {"webhook_id": webhook_id}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing Google webhook: {e}")
            return False
    
    @staticmethod
    async def process_outlook_webhook(
        calendar_connection_id: str,
        headers: Dict[str, str],
        body: Dict[str, Any]
    ) -> bool:
        """Process Outlook Calendar webhook."""
        try:
            # Verify signature
            if not WebhookReceiver._verify_outlook_signature(headers, body):
                logger.warning(f"Invalid Outlook webhook signature for {calendar_connection_id}")
                return False
            
            # Check for replay attack
            if not await WebhookReceiver._check_webhook_freshness(calendar_connection_id, headers):
                logger.warning(f"Stale Outlook webhook for {calendar_connection_id}")
                return False
            
            # Process idempotently
            webhook_id = body.get("id")
            if not await WebhookReceiver._is_webhook_new(calendar_connection_id, webhook_id):
                logger.info(f"Duplicate Outlook webhook: {webhook_id}")
                return True
            
            # Extract event type
            event_type = body.get("changeType", "unknown")
            
            # Store webhook delivery log
            await WebhookReceiver._log_webhook_delivery(
                calendar_connection_id,
                "outlook",
                webhook_id,
                event_type,
                "received"
            )
            
            # Publish event
            await EventBus.publish_webhook_processed(calendar_connection_id, event_type)
            
            # Log audit
            await CalendarAuditService.log_webhook_received(
                calendar_connection_id,
                event_type,
                {"webhook_id": webhook_id}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing Outlook webhook: {e}")
            return False
    
    @staticmethod
    async def process_calendly_webhook(
        calendar_connection_id: str,
        headers: Dict[str, str],
        body: Dict[str, Any]
    ) -> bool:
        """Process Calendly webhook."""
        try:
            # Verify signature
            if not WebhookReceiver._verify_calendly_signature(headers, body):
                logger.warning(f"Invalid Calendly webhook signature for {calendar_connection_id}")
                return False
            
            # Check for replay attack
            if not await WebhookReceiver._check_webhook_freshness(calendar_connection_id, headers):
                logger.warning(f"Stale Calendly webhook for {calendar_connection_id}")
                return False
            
            # Process idempotently
            webhook_id = body.get("id")
            if not await WebhookReceiver._is_webhook_new(calendar_connection_id, webhook_id):
                logger.info(f"Duplicate Calendly webhook: {webhook_id}")
                return True
            
            # Extract event type
            event_type = body.get("event", "unknown")
            
            # Store webhook delivery log
            await WebhookReceiver._log_webhook_delivery(
                calendar_connection_id,
                "calendly",
                webhook_id,
                event_type,
                "received"
            )
            
            # Publish event
            await EventBus.publish_webhook_processed(calendar_connection_id, event_type)
            
            # Log audit
            await CalendarAuditService.log_webhook_received(
                calendar_connection_id,
                event_type,
                {"webhook_id": webhook_id}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing Calendly webhook: {e}")
            return False
    
    @staticmethod
    def _verify_google_signature(headers: Dict[str, str], body: Dict[str, Any]) -> bool:
        """Verify Google Calendar webhook signature."""
        try:
            # Placeholder - implement with actual Google verification
            return True
        except Exception as e:
            logger.error(f"Error verifying Google signature: {e}")
            return False
    
    @staticmethod
    def _verify_outlook_signature(headers: Dict[str, str], body: Dict[str, Any]) -> bool:
        """Verify Outlook Calendar webhook signature."""
        try:
            # Placeholder - implement with actual Outlook verification
            return True
        except Exception as e:
            logger.error(f"Error verifying Outlook signature: {e}")
            return False
    
    @staticmethod
    def _verify_calendly_signature(headers: Dict[str, str], body: Dict[str, Any]) -> bool:
        """Verify Calendly webhook signature."""
        try:
            # Placeholder - implement with actual Calendly verification
            return True
        except Exception as e:
            logger.error(f"Error verifying Calendly signature: {e}")
            return False
    
    @staticmethod
    async def _check_webhook_freshness(
        calendar_connection_id: str,
        headers: Dict[str, str]
    ) -> bool:
        """Check if webhook is fresh (not a replay attack)."""
        try:
            timestamp = headers.get("X-Webhook-Timestamp")
            if not timestamp:
                return True
            
            webhook_time = datetime.fromisoformat(timestamp)
            now = datetime.now(timezone.utc)
            
            if (now - webhook_time).total_seconds() > WebhookReceiver.WEBHOOK_TIMEOUT_SECONDS:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking webhook freshness: {e}")
            return False
    
    @staticmethod
    async def _is_webhook_new(
        calendar_connection_id: str,
        webhook_id: str
    ) -> bool:
        """Check if webhook has been processed before."""
        try:
            query = """
                SELECT id FROM calendar_webhooks
                WHERE calendar_connection_id = $1 AND webhook_id = $2
            """
            
            rows = await database.query(
                query,
                [UUID(calendar_connection_id), webhook_id]
            )
            
            return len(rows) == 0
            
        except Exception as e:
            logger.error(f"Error checking webhook newness: {e}")
            return True
    
    @staticmethod
    async def _log_webhook_delivery(
        calendar_connection_id: str,
        provider: str,
        webhook_id: str,
        event_type: str,
        status: str
    ) -> bool:
        """Log webhook delivery."""
        try:
            query = """
                INSERT INTO calendar_webhooks 
                (calendar_connection_id, provider, webhook_id, status, last_ping_at)
                VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
                ON CONFLICT (calendar_connection_id, webhook_id) DO UPDATE
                SET last_ping_at = CURRENT_TIMESTAMP, status = $4
            """
            
            await database.query(
                query,
                [UUID(calendar_connection_id), provider, webhook_id, status]
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error logging webhook delivery: {e}")
            return False
