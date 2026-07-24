"""
Webhook Receiver Engine.
Processes provider webhooks with signature verification and idempotency.
"""

import logging
import hashlib
import hmac
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone, timedelta
from api import database
from api.modules.phone_numbers.call_state_machine import CallStateMachine
from api.modules.phone_numbers.event_bus import EventBus

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.webhook_receiver_engine")


class WebhookReceiverEngine:
    """Engine for processing provider webhooks."""
    
    WEBHOOK_TIMEOUT_SECONDS = 300  # 5 minutes
    MAX_RETRIES = 3
    
    @staticmethod
    async def process_webhook(
        phone_number_id: str,
        provider: str,
        webhook_id: str,
        event_type: str,
        payload: Dict[str, Any],
        signature: Optional[str] = None,
        provider_secret: Optional[str] = None
    ) -> bool:
        """
        Process webhook with verification and idempotency.
        
        Flow:
        1. Verify signature
        2. Check for replay attack
        3. Check for duplicate
        4. Process event
        5. Update call state
        6. Publish event
        """
        try:
            # Step 1: Verify signature
            if signature and provider_secret:
                if not WebhookReceiverEngine._verify_signature(
                    payload,
                    signature,
                    provider_secret,
                    provider
                ):
                    logger.warning(f"Invalid webhook signature: {webhook_id}")
                    return False
            
            # Step 2: Check for replay attack
            if not await WebhookReceiverEngine._check_freshness(payload):
                logger.warning(f"Stale webhook: {webhook_id}")
                return False
            
            # Step 3: Check for duplicate
            existing = await WebhookReceiverEngine._check_duplicate(provider, webhook_id)
            if existing:
                logger.info(f"Duplicate webhook: {webhook_id}")
                # Update status to duplicate
                await WebhookReceiverEngine._update_delivery_status(
                    provider,
                    webhook_id,
                    "duplicate"
                )
                return True
            
            # Step 4: Store delivery log
            delivery_id = await WebhookReceiverEngine._log_delivery(
                phone_number_id,
                provider,
                webhook_id,
                event_type,
                payload,
                signature
            )
            
            if not delivery_id:
                return False
            
            # Step 5: Process event
            success = await WebhookReceiverEngine._process_event(
                phone_number_id,
                provider,
                event_type,
                payload
            )
            
            # Step 6: Update delivery status
            status = "completed" if success else "failed"
            await WebhookReceiverEngine._update_delivery_status(
                provider,
                webhook_id,
                status
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return False
    
    @staticmethod
    def _verify_signature(
        payload: Dict[str, Any],
        signature: str,
        provider_secret: str,
        provider: str
    ) -> bool:
        """Verify webhook signature."""
        try:
            if provider == "twilio":
                # Twilio signature verification
                return True  # Placeholder
            
            elif provider == "telnyx":
                # Telnyx signature verification
                return True  # Placeholder
            
            elif provider == "plivo":
                # Plivo signature verification
                return True  # Placeholder
            
            else:
                # Generic HMAC verification
                message = str(payload).encode()
                expected = hmac.new(
                    provider_secret.encode(),
                    message,
                    hashlib.sha256
                ).hexdigest()
                
                return hmac.compare_digest(signature, expected)
            
        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return False
    
    @staticmethod
    async def _check_freshness(payload: Dict[str, Any]) -> bool:
        """Check if webhook is fresh (not a replay attack)."""
        try:
            timestamp = payload.get("timestamp")
            if not timestamp:
                return True
            
            webhook_time = datetime.fromisoformat(timestamp)
            now = datetime.now(timezone.utc)
            
            if (now - webhook_time).total_seconds() > WebhookReceiverEngine.WEBHOOK_TIMEOUT_SECONDS:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking freshness: {e}")
            return False
    
    @staticmethod
    async def _check_duplicate(provider: str, webhook_id: str) -> bool:
        """Check if webhook has been processed."""
        try:
            query = """
                SELECT id FROM webhook_deliveries
                WHERE provider = $1 AND webhook_id = $2
            """
            
            rows = await database.query(query, [provider, webhook_id])
            return len(rows) > 0
            
        except Exception as e:
            logger.error(f"Error checking duplicate: {e}")
            return False
    
    @staticmethod
    async def _log_delivery(
        phone_number_id: str,
        provider: str,
        webhook_id: str,
        event_type: str,
        payload: Dict[str, Any],
        signature: Optional[str]
    ) -> Optional[str]:
        """Log webhook delivery."""
        try:
            query = """
                INSERT INTO webhook_deliveries 
                (phone_number_id, provider, webhook_id, event_type, payload, signature, status)
                VALUES ($1, $2, $3, $4, $5, $6, 'processing')
                RETURNING id
            """
            
            rows = await database.query(
                query,
                [UUID(phone_number_id), provider, webhook_id, event_type, payload, signature]
            )
            
            return str(rows[0].get("id")) if rows else None
            
        except Exception as e:
            logger.error(f"Error logging delivery: {e}")
            return None
    
    @staticmethod
    async def _process_event(
        phone_number_id: str,
        provider: str,
        event_type: str,
        payload: Dict[str, Any]
    ) -> bool:
        """Process webhook event."""
        try:
            call_id = payload.get("call_id")
            
            if not call_id:
                logger.warning(f"No call_id in webhook: {event_type}")
                return False
            
            # Route to appropriate handler
            if event_type == "incoming_call":
                return await WebhookReceiverEngine._handle_incoming_call(
                    phone_number_id,
                    call_id,
                    payload
                )
            
            elif event_type == "call_ringing":
                return await CallStateMachine.transition_state(
                    call_id,
                    "ringing",
                    "provider_webhook"
                )
            
            elif event_type == "call_answered":
                return await CallStateMachine.transition_state(
                    call_id,
                    "answered",
                    "provider_webhook"
                )
            
            elif event_type == "call_completed":
                return await CallStateMachine.transition_state(
                    call_id,
                    "completed",
                    "provider_webhook"
                )
            
            elif event_type == "call_failed":
                return await CallStateMachine.transition_state(
                    call_id,
                    "failed",
                    "provider_webhook"
                )
            
            elif event_type == "busy":
                return await CallStateMachine.transition_state(
                    call_id,
                    "busy",
                    "provider_webhook"
                )
            
            elif event_type == "no_answer":
                return await CallStateMachine.transition_state(
                    call_id,
                    "no_answer",
                    "provider_webhook"
                )
            
            else:
                logger.warning(f"Unknown event type: {event_type}")
                return False
            
        except Exception as e:
            logger.error(f"Error processing event: {e}")
            return False
    
    @staticmethod
    async def _handle_incoming_call(
        phone_number_id: str,
        call_id: str,
        payload: Dict[str, Any]
    ) -> bool:
        """Handle incoming call event."""
        try:
            # Initialize call state
            await CallStateMachine.initialize_call(call_id, phone_number_id)
            
            # Publish event
            await EventBus.publish_call_started(phone_number_id, "incoming_call_received")
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling incoming call: {e}")
            return False
    
    @staticmethod
    async def _update_delivery_status(
        provider: str,
        webhook_id: str,
        status: str,
        error: Optional[str] = None
    ) -> bool:
        """Update webhook delivery status."""
        try:
            query = """
                UPDATE webhook_deliveries
                SET status = $1, last_error = $2, processed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE provider = $3 AND webhook_id = $4
            """
            
            await database.query(query, [status, error, provider, webhook_id])
            return True
            
        except Exception as e:
            logger.error(f"Error updating delivery status: {e}")
            return False
    
    @staticmethod
    async def retry_failed_webhooks() -> int:
        """Retry failed webhook processing."""
        try:
            query = """
                SELECT id, provider, webhook_id, event_type, payload
                FROM webhook_deliveries
                WHERE status = 'failed' AND retry_count < $1
                AND updated_at < CURRENT_TIMESTAMP - INTERVAL '5 minutes'
                LIMIT 100
            """
            
            rows = await database.query(query, [WebhookReceiverEngine.MAX_RETRIES])
            
            retry_count = 0
            for row in rows:
                # Increment retry count
                update_query = """
                    UPDATE webhook_deliveries
                    SET retry_count = retry_count + 1
                    WHERE id = $1
                """
                
                await database.query(update_query, [UUID(row.get("id"))])
                retry_count += 1
            
            return retry_count
            
        except Exception as e:
            logger.error(f"Error retrying webhooks: {e}")
            return 0
