"""
Spam Detection Service.
Detects and manages spam calls.
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
from api import database

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.spam_detection_service")


class SpamDetectionService:
    """Service for spam detection."""
    
    @staticmethod
    async def check_spam(
        phone_number: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """Check if number is spam."""
        try:
            # Check blacklist
            blacklist_query = """
                SELECT spam_score FROM phone_number_spam_list
                WHERE tenant_id = $1 AND phone_number = $2 AND list_type = 'blacklist'
            """
            
            blacklist_rows = await database.query(
                blacklist_query,
                [UUID(tenant_id), phone_number]
            )
            
            if blacklist_rows:
                return {
                    "is_spam": True,
                    "spam_score": blacklist_rows[0].get("spam_score", 100),
                    "reason": "blacklisted"
                }
            
            # Check whitelist
            whitelist_query = """
                SELECT id FROM phone_number_spam_list
                WHERE tenant_id = $1 AND phone_number = $2 AND list_type = 'whitelist'
            """
            
            whitelist_rows = await database.query(
                whitelist_query,
                [UUID(tenant_id), phone_number]
            )
            
            if whitelist_rows:
                return {
                    "is_spam": False,
                    "spam_score": 0,
                    "reason": "whitelisted"
                }
            
            # Default: not spam
            return {
                "is_spam": False,
                "spam_score": 0,
                "reason": "unknown"
            }
            
        except Exception as e:
            logger.error(f"Error checking spam: {e}")
            return {
                "is_spam": False,
                "spam_score": 0,
                "reason": "error"
            }
    
    @staticmethod
    async def add_to_blacklist(
        tenant_id: str,
        phone_number: str,
        reason: Optional[str] = None,
        spam_score: int = 100
    ) -> bool:
        """Add number to blacklist."""
        try:
            query = """
                INSERT INTO phone_number_spam_list 
                (tenant_id, phone_number, list_type, reason, spam_score)
                VALUES ($1, $2, 'blacklist', $3, $4)
                ON CONFLICT (tenant_id, phone_number, list_type) DO UPDATE
                SET reason = $3, spam_score = $4, updated_at = CURRENT_TIMESTAMP
            """
            
            await database.query(
                query,
                [UUID(tenant_id), phone_number, reason, spam_score]
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding to blacklist: {e}")
            return False
    
    @staticmethod
    async def add_to_whitelist(
        tenant_id: str,
        phone_number: str,
        reason: Optional[str] = None
    ) -> bool:
        """Add number to whitelist."""
        try:
            query = """
                INSERT INTO phone_number_spam_list 
                (tenant_id, phone_number, list_type, reason, spam_score)
                VALUES ($1, $2, 'whitelist', $3, 0)
                ON CONFLICT (tenant_id, phone_number, list_type) DO UPDATE
                SET reason = $3, updated_at = CURRENT_TIMESTAMP
            """
            
            await database.query(
                query,
                [UUID(tenant_id), phone_number, reason]
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding to whitelist: {e}")
            return False
    
    @staticmethod
    async def remove_from_list(
        tenant_id: str,
        phone_number: str,
        list_type: str
    ) -> bool:
        """Remove number from list."""
        try:
            query = """
                DELETE FROM phone_number_spam_list
                WHERE tenant_id = $1 AND phone_number = $2 AND list_type = $3
            """
            
            await database.query(
                query,
                [UUID(tenant_id), phone_number, list_type]
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error removing from list: {e}")
            return False
