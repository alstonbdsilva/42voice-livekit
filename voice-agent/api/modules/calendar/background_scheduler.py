"""
Background Scheduler.
Handles scheduled background jobs for calendar operations.
"""

import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID
from api import database
from api.modules.calendar.slot_reservation_service import SlotReservationService
from api.modules.calendar.calendar_health_service import CalendarHealthService
from api.modules.calendar.calendar_audit_service import CalendarAuditService

logger = logging.getLogger("voice-agent.api.modules.calendar.background_scheduler")


class BackgroundScheduler:
    """Background scheduler for calendar operations."""
    
    _running = False
    
    @staticmethod
    async def start():
        """Start background scheduler."""
        try:
            if BackgroundScheduler._running:
                return
            
            BackgroundScheduler._running = True
            logger.info("Starting background scheduler")
            
            # Run all scheduled tasks
            await asyncio.gather(
                BackgroundScheduler._run_token_refresh_job(),
                BackgroundScheduler._run_reservation_cleanup_job(),
                BackgroundScheduler._run_calendar_reconciliation_job(),
                BackgroundScheduler._run_webhook_retry_job(),
                BackgroundScheduler._run_health_check_job()
            )
            
        except Exception as e:
            logger.error(f"Error starting scheduler: {e}")
            BackgroundScheduler._running = False
    
    @staticmethod
    async def stop():
        """Stop background scheduler."""
        try:
            BackgroundScheduler._running = False
            logger.info("Stopping background scheduler")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")
    
    @staticmethod
    async def _run_token_refresh_job():
        """Refresh OAuth tokens before expiration."""
        try:
            while BackgroundScheduler._running:
                try:
                    # Get tokens expiring in next 24 hours
                    query = """
                        SELECT id, provider, refresh_token, expires_at
                        FROM oauth_connections
                        WHERE status = 'active'
                        AND refresh_token IS NOT NULL
                        AND expires_at < CURRENT_TIMESTAMP + INTERVAL '24 hours'
                        AND expires_at > CURRENT_TIMESTAMP
                        LIMIT 100
                    """
                    
                    rows = await database.query(query)
                    
                    for row in rows:
                        # Refresh token
                        success = await BackgroundScheduler._refresh_oauth_token(
                            str(row.get("id")),
                            row.get("provider"),
                            row.get("refresh_token")
                        )
                        
                        if success:
                            await CalendarAuditService.log_token_refreshed(
                                str(row.get("id")),
                                True
                            )
                    
                    # Sleep for 1 hour
                    await asyncio.sleep(3600)
                    
                except Exception as e:
                    logger.error(f"Error in token refresh job: {e}")
                    await asyncio.sleep(300)
                    
        except Exception as e:
            logger.error(f"Error running token refresh job: {e}")
    
    @staticmethod
    async def _run_reservation_cleanup_job():
        """Clean up expired slot reservations."""
        try:
            while BackgroundScheduler._running:
                try:
                    # Expire old reservations
                    expired_count = await SlotReservationService.expire_old_reservations()
                    
                    if expired_count > 0:
                        logger.info(f"Expired {expired_count} slot reservations")
                    
                    # Sleep for 5 minutes
                    await asyncio.sleep(300)
                    
                except Exception as e:
                    logger.error(f"Error in reservation cleanup job: {e}")
                    await asyncio.sleep(300)
                    
        except Exception as e:
            logger.error(f"Error running reservation cleanup job: {e}")
    
    @staticmethod
    async def _run_calendar_reconciliation_job():
        """Reconcile calendars with provider."""
        try:
            while BackgroundScheduler._running:
                try:
                    # Get calendars that need reconciliation
                    query = """
                        SELECT id FROM calendar_connections
                        WHERE is_active = TRUE
                        AND (
                            SELECT last_successful_sync FROM calendar_health
                            WHERE calendar_connection_id = calendar_connections.id
                        ) < CURRENT_TIMESTAMP - INTERVAL '6 hours'
                        LIMIT 50
                    """
                    
                    rows = await database.query(query)
                    
                    for row in rows:
                        # Trigger reconciliation
                        await BackgroundScheduler._reconcile_calendar(str(row.get("id")))
                    
                    # Sleep for 30 minutes
                    await asyncio.sleep(1800)
                    
                except Exception as e:
                    logger.error(f"Error in reconciliation job: {e}")
                    await asyncio.sleep(1800)
                    
        except Exception as e:
            logger.error(f"Error running reconciliation job: {e}")
    
    @staticmethod
    async def _run_webhook_retry_job():
        """Retry failed webhook processing."""
        try:
            while BackgroundScheduler._running:
                try:
                    # Get failed webhooks
                    query = """
                        SELECT id, calendar_connection_id FROM calendar_webhooks
                        WHERE status = 'failed'
                        AND updated_at < CURRENT_TIMESTAMP - INTERVAL '5 minutes'
                        LIMIT 50
                    """
                    
                    rows = await database.query(query)
                    
                    for row in rows:
                        # Retry webhook processing
                        await BackgroundScheduler._retry_webhook(
                            str(row.get("id")),
                            str(row.get("calendar_connection_id"))
                        )
                    
                    # Sleep for 10 minutes
                    await asyncio.sleep(600)
                    
                except Exception as e:
                    logger.error(f"Error in webhook retry job: {e}")
                    await asyncio.sleep(600)
                    
        except Exception as e:
            logger.error(f"Error running webhook retry job: {e}")
    
    @staticmethod
    async def _run_health_check_job():
        """Check health of all calendars."""
        try:
            while BackgroundScheduler._running:
                try:
                    # Get unhealthy calendars
                    unhealthy = await CalendarHealthService.get_unhealthy_calendars()
                    
                    for calendar in unhealthy:
                        # Log health check
                        logger.warning(
                            f"Unhealthy calendar: {calendar.get('calendar_connection_id')} "
                            f"- OAuth: {calendar.get('oauth_status')}, "
                            f"Sync: {calendar.get('sync_status')}"
                        )
                    
                    # Sleep for 15 minutes
                    await asyncio.sleep(900)
                    
                except Exception as e:
                    logger.error(f"Error in health check job: {e}")
                    await asyncio.sleep(900)
                    
        except Exception as e:
            logger.error(f"Error running health check job: {e}")
    
    @staticmethod
    async def _refresh_oauth_token(
        connection_id: str,
        provider: str,
        refresh_token: str
    ) -> bool:
        """Refresh OAuth token."""
        try:
            # Placeholder - implement with actual provider refresh
            logger.info(f"Refreshing token for {provider}")
            return True
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return False
    
    @staticmethod
    async def _reconcile_calendar(calendar_connection_id: str) -> bool:
        """Reconcile calendar with provider."""
        try:
            logger.info(f"Reconciling calendar: {calendar_connection_id}")
            # Placeholder - implement with actual reconciliation
            return True
        except Exception as e:
            logger.error(f"Error reconciling calendar: {e}")
            return False
    
    @staticmethod
    async def _retry_webhook(webhook_id: str, calendar_connection_id: str) -> bool:
        """Retry webhook processing."""
        try:
            logger.info(f"Retrying webhook: {webhook_id}")
            # Placeholder - implement with actual retry logic
            return True
        except Exception as e:
            logger.error(f"Error retrying webhook: {e}")
            return False
