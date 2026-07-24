"""
Workflow Step Service.
Manages workflow steps, conditions, and actions.
"""

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from api import database

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.workflow_step_service")


class WorkflowStepService:
    """Service for managing workflow steps."""
    
    @staticmethod
    async def create_step(
        workflow_id: str,
        step_order: int,
        step_type: str,
        configuration: Optional[Dict] = None,
        next_step_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a workflow step."""
        try:
            query = """
                INSERT INTO workflow_steps 
                (workflow_id, step_order, step_type, configuration, next_step_id)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id, workflow_id, step_order, step_type, configuration, next_step_id, created_at
            """
            
            rows = await database.query(
                query,
                [UUID(workflow_id), step_order, step_type, configuration,
                 UUID(next_step_id) if next_step_id else None]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error creating step: {e}")
            return None
    
    @staticmethod
    async def get_step(step_id: str) -> Optional[Dict[str, Any]]:
        """Get step details."""
        try:
            query = """
                SELECT id, workflow_id, step_order, step_type, configuration, next_step_id, created_at
                FROM workflow_steps
                WHERE id = $1
            """
            
            rows = await database.query(query, [UUID(step_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting step: {e}")
            return None
    
    @staticmethod
    async def update_step(
        step_id: str,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Update a workflow step."""
        try:
            allowed_fields = ["step_type", "configuration", "next_step_id"]
            updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
            
            if not updates:
                return await WorkflowStepService.get_step(step_id)
            
            set_clause = ", ".join([f"{k} = ${i+1}" for i, k in enumerate(updates.keys())])
            values = list(updates.values()) + [UUID(step_id)]
            
            query = f"""
                UPDATE workflow_steps
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ${len(values)}
                RETURNING id, workflow_id, step_order, step_type, configuration, next_step_id, created_at
            """
            
            rows = await database.query(query, values)
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error updating step: {e}")
            return None
    
    @staticmethod
    async def delete_step(step_id: str) -> bool:
        """Delete a workflow step."""
        try:
            query = "DELETE FROM workflow_steps WHERE id = $1"
            await database.query(query, [UUID(step_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error deleting step: {e}")
            return False
    
    @staticmethod
    async def create_condition(
        step_id: str,
        condition_type: str,
        configuration: Dict,
        true_step_id: Optional[str] = None,
        false_step_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a workflow condition."""
        try:
            query = """
                INSERT INTO workflow_conditions 
                (workflow_step_id, condition_type, configuration, true_step_id, false_step_id)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id, workflow_step_id, condition_type, configuration, true_step_id, false_step_id, created_at
            """
            
            rows = await database.query(
                query,
                [UUID(step_id), condition_type, configuration,
                 UUID(true_step_id) if true_step_id else None,
                 UUID(false_step_id) if false_step_id else None]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error creating condition: {e}")
            return None
    
    @staticmethod
    async def get_condition(condition_id: str) -> Optional[Dict[str, Any]]:
        """Get condition details."""
        try:
            query = """
                SELECT id, workflow_step_id, condition_type, configuration, true_step_id, false_step_id, created_at
                FROM workflow_conditions
                WHERE id = $1
            """
            
            rows = await database.query(query, [UUID(condition_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting condition: {e}")
            return None
    
    @staticmethod
    async def delete_condition(condition_id: str) -> bool:
        """Delete a workflow condition."""
        try:
            query = "DELETE FROM workflow_conditions WHERE id = $1"
            await database.query(query, [UUID(condition_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error deleting condition: {e}")
            return False
    
    @staticmethod
    async def create_action(
        step_id: str,
        action_type: str,
        configuration: Dict,
        execution_order: int = 0
    ) -> Optional[Dict[str, Any]]:
        """Create a workflow action."""
        try:
            query = """
                INSERT INTO workflow_actions 
                (workflow_step_id, action_type, configuration, execution_order)
                VALUES ($1, $2, $3, $4)
                RETURNING id, workflow_step_id, action_type, configuration, execution_order, created_at
            """
            
            rows = await database.query(
                query,
                [UUID(step_id), action_type, configuration, execution_order]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error creating action: {e}")
            return None
    
    @staticmethod
    async def get_action(action_id: str) -> Optional[Dict[str, Any]]:
        """Get action details."""
        try:
            query = """
                SELECT id, workflow_step_id, action_type, configuration, execution_order, created_at
                FROM workflow_actions
                WHERE id = $1
            """
            
            rows = await database.query(query, [UUID(action_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting action: {e}")
            return None
    
    @staticmethod
    async def delete_action(action_id: str) -> bool:
        """Delete a workflow action."""
        try:
            query = "DELETE FROM workflow_actions WHERE id = $1"
            await database.query(query, [UUID(action_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error deleting action: {e}")
            return False
