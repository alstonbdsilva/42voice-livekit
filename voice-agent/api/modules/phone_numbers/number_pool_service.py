"""
Number Pool Service.
Manages pools of phone numbers with selection strategies.
"""

import logging
import random
from typing import Optional, Dict, Any, List
from uuid import UUID
from api import database

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.number_pool_service")


class NumberPoolService:
    """Service for managing number pools."""
    
    @staticmethod
    async def create_pool(
        tenant_id: str,
        pool_name: str,
        pool_type: str,
        selection_strategy: str = "round_robin"
    ) -> Optional[Dict[str, Any]]:
        """Create number pool."""
        try:
            query = """
                INSERT INTO number_pools 
                (tenant_id, pool_name, pool_type, selection_strategy)
                VALUES ($1, $2, $3, $4)
                RETURNING id, tenant_id, pool_name, pool_type, selection_strategy, created_at
            """
            
            rows = await database.query(
                query,
                [UUID(tenant_id), pool_name, pool_type, selection_strategy]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error creating pool: {e}")
            return None
    
    @staticmethod
    async def add_number_to_pool(
        pool_id: str,
        phone_number_id: str,
        priority: int = 0
    ) -> Optional[Dict[str, Any]]:
        """Add number to pool."""
        try:
            query = """
                INSERT INTO number_pool_members 
                (pool_id, phone_number_id, priority, usage_count)
                VALUES ($1, $2, $3, 0)
                ON CONFLICT (pool_id, phone_number_id) DO UPDATE
                SET priority = $3
                RETURNING id, pool_id, phone_number_id, priority, usage_count, created_at
            """
            
            rows = await database.query(
                query,
                [UUID(pool_id), UUID(phone_number_id), priority]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error adding number to pool: {e}")
            return None
    
    @staticmethod
    async def select_number(
        pool_id: str,
        strategy: Optional[str] = None
    ) -> Optional[str]:
        """Select number from pool."""
        try:
            # Get pool
            pool_query = """
                SELECT selection_strategy FROM number_pools WHERE id = $1
            """
            
            pool_rows = await database.query(pool_query, [UUID(pool_id)])
            if not pool_rows:
                return None
            
            pool = pool_rows[0]
            selection_strategy = strategy or pool.get("selection_strategy", "round_robin")
            
            # Get pool members
            members_query = """
                SELECT phone_number_id, priority, usage_count
                FROM number_pool_members
                WHERE pool_id = $1
                ORDER BY priority DESC, usage_count ASC
            """
            
            members = await database.query(members_query, [UUID(pool_id)])
            
            if not members:
                return None
            
            # Select based on strategy
            if selection_strategy == "round_robin":
                # Select least used
                selected = members[0]
            
            elif selection_strategy == "least_used":
                # Select least used
                selected = min(members, key=lambda x: x.get("usage_count", 0))
            
            elif selection_strategy == "priority":
                # Select highest priority
                selected = members[0]
            
            elif selection_strategy == "random":
                # Select random
                selected = random.choice(members)
            
            else:
                selected = members[0]
            
            phone_number_id = str(selected.get("phone_number_id"))
            
            # Increment usage count
            update_query = """
                UPDATE number_pool_members
                SET usage_count = usage_count + 1
                WHERE pool_id = $1 AND phone_number_id = $2
            """
            
            await database.query(update_query, [UUID(pool_id), UUID(phone_number_id)])
            
            return phone_number_id
            
        except Exception as e:
            logger.error(f"Error selecting number: {e}")
            return None
    
    @staticmethod
    async def remove_number_from_pool(
        pool_id: str,
        phone_number_id: str
    ) -> bool:
        """Remove number from pool."""
        try:
            query = """
                DELETE FROM number_pool_members
                WHERE pool_id = $1 AND phone_number_id = $2
            """
            
            await database.query(query, [UUID(pool_id), UUID(phone_number_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error removing number from pool: {e}")
            return False
    
    @staticmethod
    async def get_pool_members(pool_id: str) -> List[Dict[str, Any]]:
        """Get pool members."""
        try:
            query = """
                SELECT npm.id, npm.phone_number_id, npm.priority, npm.usage_count,
                       pn.e164_number, pn.friendly_name
                FROM number_pool_members npm
                JOIN phone_numbers pn ON npm.phone_number_id = pn.id
                WHERE npm.pool_id = $1
                ORDER BY npm.priority DESC, npm.usage_count ASC
            """
            
            rows = await database.query(query, [UUID(pool_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting pool members: {e}")
            return []
    
    @staticmethod
    async def get_pool_stats(pool_id: str) -> Dict[str, Any]:
        """Get pool statistics."""
        try:
            query = """
                SELECT 
                    COUNT(*) as total_numbers,
                    SUM(usage_count) as total_usage,
                    AVG(usage_count) as avg_usage,
                    MIN(usage_count) as min_usage,
                    MAX(usage_count) as max_usage
                FROM number_pool_members
                WHERE pool_id = $1
            """
            
            rows = await database.query(query, [UUID(pool_id)])
            
            if rows:
                return rows[0]
            
            return {
                "total_numbers": 0,
                "total_usage": 0,
                "avg_usage": 0,
                "min_usage": 0,
                "max_usage": 0
            }
            
        except Exception as e:
            logger.error(f"Error getting pool stats: {e}")
            return {}
