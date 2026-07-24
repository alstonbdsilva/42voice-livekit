"""
Intent Service.
Manages intent-to-capability mappings and intent detection.
"""

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from api import database

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.intent_service")


class IntentService:
    """Service for managing intent-to-capability mappings."""
    
    @staticmethod
    async def map_intent_to_capability(
        intent_name: str,
        capability_id: str,
        user_id: str,
        client_id: Optional[str] = None,
        confidence_threshold: float = 0.7
    ) -> Optional[Dict[str, Any]]:
        """Map an intent to a capability."""
        try:
            if not (0 <= confidence_threshold <= 1):
                logger.error("Confidence threshold must be between 0 and 1")
                return None
            
            query = """
                INSERT INTO intent_capabilities 
                (intent_name, capability_id, confidence_threshold, user_id, client_id)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (intent_name, capability_id, user_id, client_id) DO UPDATE
                SET confidence_threshold = $3, updated_at = CURRENT_TIMESTAMP
                RETURNING id, intent_name, capability_id, confidence_threshold, created_at, updated_at
            """
            
            rows = await database.query(
                query,
                [intent_name, UUID(capability_id), confidence_threshold, 
                 UUID(user_id), UUID(client_id) if client_id else None]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error mapping intent: {e}")
            return None
    
    @staticmethod
    async def get_capability_for_intent(
        intent_name: str,
        user_id: str,
        client_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get capability for a detected intent."""
        try:
            query = """
                SELECT ic.id, ic.intent_name, ic.capability_id, ic.confidence_threshold,
                       c.name, c.description
                FROM intent_capabilities ic
                JOIN capabilities c ON ic.capability_id = c.id
                WHERE ic.intent_name = $1 
                AND (ic.user_id = $2 OR ic.client_id = $3)
                LIMIT 1
            """
            
            rows = await database.query(
                query,
                [intent_name, UUID(user_id), UUID(client_id) if client_id else None]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting capability for intent: {e}")
            return None
    
    @staticmethod
    async def get_intents_for_capability(capability_id: str) -> List[Dict[str, Any]]:
        """Get all intents mapped to a capability."""
        try:
            query = """
                SELECT id, intent_name, confidence_threshold, created_at, updated_at
                FROM intent_capabilities
                WHERE capability_id = $1
                ORDER BY created_at DESC
            """
            
            rows = await database.query(query, [UUID(capability_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting intents for capability: {e}")
            return []
    
    @staticmethod
    async def get_user_intent_mappings(user_id: str) -> List[Dict[str, Any]]:
        """Get all intent mappings for a user."""
        try:
            query = """
                SELECT ic.id, ic.intent_name, ic.capability_id, ic.confidence_threshold,
                       c.name as capability_name, c.description
                FROM intent_capabilities ic
                JOIN capabilities c ON ic.capability_id = c.id
                WHERE ic.user_id = $1
                ORDER BY ic.intent_name ASC
            """
            
            rows = await database.query(query, [UUID(user_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting user intent mappings: {e}")
            return []
    
    @staticmethod
    async def get_client_intent_mappings(client_id: str) -> List[Dict[str, Any]]:
        """Get all intent mappings for a client."""
        try:
            query = """
                SELECT ic.id, ic.intent_name, ic.capability_id, ic.confidence_threshold,
                       c.name as capability_name, c.description
                FROM intent_capabilities ic
                JOIN capabilities c ON ic.capability_id = c.id
                WHERE ic.client_id = $1
                ORDER BY ic.intent_name ASC
            """
            
            rows = await database.query(query, [UUID(client_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting client intent mappings: {e}")
            return []
    
    @staticmethod
    async def remove_intent_mapping(
        intent_name: str,
        capability_id: str,
        user_id: str,
        client_id: Optional[str] = None
    ) -> bool:
        """Remove an intent-to-capability mapping."""
        try:
            query = """
                DELETE FROM intent_capabilities
                WHERE intent_name = $1 AND capability_id = $2
                AND (user_id = $3 OR client_id = $4)
            """
            
            await database.query(
                query,
                [intent_name, UUID(capability_id), UUID(user_id), 
                 UUID(client_id) if client_id else None]
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error removing intent mapping: {e}")
            return False
