"""
Call Transfer Engine.
Manages call transfers between agents, groups, and queues.
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
from api import database
from api.modules.phone_numbers.call_state_machine import CallStateMachine
from api.modules.phone_numbers.event_bus import EventBus

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.call_transfer_engine")


class CallTransferEngine:
    """Engine for managing call transfers."""
    
    @staticmethod
    async def initiate_transfer(
        from_call_id: str,
        from_agent_id: str,
        to_agent_id: Optional[str] = None,
        transfer_type: str = "agent_to_agent",
        transfer_method: str = "warm",
        reason: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Initiate call transfer.
        
        Transfer types: ai_to_ai, ai_to_human, human_to_ai, agent_to_agent, agent_group, queue
        Transfer methods: blind, warm, consult, sip_refer
        """
        try:
            query = """
                INSERT INTO call_transfers 
                (from_call_id, from_agent_id, to_agent_id, transfer_type, transfer_method, 
                 status, reason)
                VALUES ($1, $2, $3, $4, $5, 'initiated', $6)
                RETURNING id, from_call_id, transfer_type, transfer_method, status, created_at
            """
            
            rows = await database.query(
                query,
                [from_call_id, UUID(from_agent_id) if from_agent_id else None,
                 UUID(to_agent_id) if to_agent_id else None,
                 transfer_type, transfer_method, reason]
            )
            
            if rows:
                transfer = rows[0]
                
                # Update call state
                await CallStateMachine.transition_state(
                    from_call_id,
                    "transferred",
                    f"Transfer initiated: {transfer_type}"
                )
                
                # Publish event
                await EventBus.publish_call_started(from_call_id, "call_transfer_initiated")
                
                return transfer
            
            return None
            
        except Exception as e:
            logger.error(f"Error initiating transfer: {e}")
            return None
    
    @staticmethod
    async def accept_transfer(
        transfer_id: str,
        to_call_id: str
    ) -> bool:
        """Accept transfer and connect calls."""
        try:
            query = """
                UPDATE call_transfers
                SET status = 'connected', to_call_id = $1, updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
            """
            
            await database.query(query, [to_call_id, UUID(transfer_id)])
            
            # Publish event
            await EventBus.publish_call_started(to_call_id, "call_transfer_accepted")
            
            return True
            
        except Exception as e:
            logger.error(f"Error accepting transfer: {e}")
            return False
    
    @staticmethod
    async def complete_transfer(transfer_id: str) -> bool:
        """Complete transfer."""
        try:
            # Get transfer details
            query = """
                SELECT from_call_id, to_call_id FROM call_transfers
                WHERE id = $1
            """
            
            rows = await database.query(query, [UUID(transfer_id)])
            if not rows:
                return False
            
            transfer = rows[0]
            
            # Update transfer status
            update_query = """
                UPDATE call_transfers
                SET status = 'completed', updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
            """
            
            await database.query(update_query, [UUID(transfer_id)])
            
            # Update call states
            if transfer.get("to_call_id"):
                await CallStateMachine.transition_state(
                    transfer.get("to_call_id"),
                    "active",
                    "Transfer completed"
                )
            
            # Publish event
            await EventBus.publish_call_started(transfer.get("from_call_id"), "call_transfer_completed")
            
            return True
            
        except Exception as e:
            logger.error(f"Error completing transfer: {e}")
            return False
    
    @staticmethod
    async def cancel_transfer(transfer_id: str) -> bool:
        """Cancel transfer."""
        try:
            # Get transfer details
            query = """
                SELECT from_call_id FROM call_transfers
                WHERE id = $1
            """
            
            rows = await database.query(query, [UUID(transfer_id)])
            if not rows:
                return False
            
            from_call_id = rows[0].get("from_call_id")
            
            # Update transfer status
            update_query = """
                UPDATE call_transfers
                SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
            """
            
            await database.query(update_query, [UUID(transfer_id)])
            
            # Revert call state
            await CallStateMachine.transition_state(
                from_call_id,
                "active",
                "Transfer cancelled"
            )
            
            # Publish event
            await EventBus.publish_call_started(from_call_id, "call_transfer_cancelled")
            
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling transfer: {e}")
            return False
    
    @staticmethod
    async def get_transfer(transfer_id: str) -> Optional[Dict[str, Any]]:
        """Get transfer details."""
        try:
            query = """
                SELECT id, from_call_id, to_call_id, from_agent_id, to_agent_id,
                       transfer_type, transfer_method, status, reason,
                       warm_transfer_duration_seconds, created_at, updated_at
                FROM call_transfers
                WHERE id = $1
            """
            
            rows = await database.query(query, [UUID(transfer_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting transfer: {e}")
            return None
    
    @staticmethod
    async def get_active_transfers(call_id: str) -> list:
        """Get active transfers for call."""
        try:
            query = """
                SELECT id, from_call_id, to_call_id, transfer_type, transfer_method,
                       status, created_at
                FROM call_transfers
                WHERE (from_call_id = $1 OR to_call_id = $1)
                AND status IN ('initiated', 'ringing', 'connected')
                ORDER BY created_at DESC
            """
            
            rows = await database.query(query, [call_id])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting active transfers: {e}")
            return []
