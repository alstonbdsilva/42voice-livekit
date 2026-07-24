"""
Workflow Service.
Manages workflows and workflow execution.
Extensible for future multi-step workflow execution.
"""

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from api import database

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.workflow_service")


class WorkflowService:
    """Service for managing and executing workflows."""
    
    @staticmethod
    async def create_workflow(
        name: str,
        user_id: str,
        client_id: Optional[str] = None,
        description: Optional[str] = None,
        entry_capability_id: Optional[str] = None,
        is_active: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Create a new workflow."""
        try:
            query = """
                INSERT INTO workflows 
                (name, description, entry_capability_id, is_active, user_id, client_id)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id, name, description, entry_capability_id, is_active, created_at, updated_at
            """
            
            rows = await database.query(
                query,
                [name, description, UUID(entry_capability_id) if entry_capability_id else None,
                 is_active, UUID(user_id), UUID(client_id) if client_id else None]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error creating workflow: {e}")
            return None
    
    @staticmethod
    async def get_workflow(workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow details."""
        try:
            query = """
                SELECT id, name, description, entry_capability_id, is_active, user_id, client_id, created_at, updated_at
                FROM workflows
                WHERE id = $1
            """
            
            rows = await database.query(query, [UUID(workflow_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting workflow: {e}")
            return None
    
    @staticmethod
    async def get_user_workflows(user_id: str) -> List[Dict[str, Any]]:
        """Get all workflows for a user."""
        try:
            query = """
                SELECT id, name, description, entry_capability_id, is_active, created_at, updated_at
                FROM workflows
                WHERE user_id = $1
                ORDER BY created_at DESC
            """
            
            rows = await database.query(query, [UUID(user_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting user workflows: {e}")
            return []
    
    @staticmethod
    async def get_client_workflows(client_id: str) -> List[Dict[str, Any]]:
        """Get all workflows for a client."""
        try:
            query = """
                SELECT id, name, description, entry_capability_id, is_active, created_at, updated_at
                FROM workflows
                WHERE client_id = $1
                ORDER BY created_at DESC
            """
            
            rows = await database.query(query, [UUID(client_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting client workflows: {e}")
            return []
    
    @staticmethod
    async def update_workflow(
        workflow_id: str,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Update workflow."""
        try:
            allowed_fields = ["name", "description", "entry_capability_id", "is_active"]
            updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
            
            if not updates:
                return await WorkflowService.get_workflow(workflow_id)
            
            set_clause = ", ".join([f"{k} = ${i+1}" for i, k in enumerate(updates.keys())])
            values = list(updates.values()) + [UUID(workflow_id)]
            
            query = f"""
                UPDATE workflows
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ${len(values)}
                RETURNING id, name, description, entry_capability_id, is_active, created_at, updated_at
            """
            
            rows = await database.query(query, values)
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error updating workflow: {e}")
            return None
    
    @staticmethod
    async def delete_workflow(workflow_id: str) -> bool:
        """Delete a workflow."""
        try:
            query = "DELETE FROM workflows WHERE id = $1"
            await database.query(query, [UUID(workflow_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error deleting workflow: {e}")
            return False
    
    @staticmethod
    async def execute_workflow(
        workflow_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Execute a workflow and return the entry capability.
        
        Extension point for future multi-step workflow execution.
        Currently returns the entry capability.
        Future: Can execute multiple steps, collect data, etc.
        """
        try:
            workflow = await WorkflowService.get_workflow(workflow_id)
            
            if not workflow:
                logger.warning(f"Workflow {workflow_id} not found")
                return None
            
            if not workflow.get("is_active"):
                logger.warning(f"Workflow {workflow_id} is not active")
                return None
            
            # Return entry capability
            # Future: Execute multi-step workflow here
            return {
                "workflow_id": str(workflow["id"]),
                "workflow_name": workflow["name"],
                "entry_capability_id": str(workflow["entry_capability_id"]) if workflow["entry_capability_id"] else None,
                "status": "completed"
            }
            
        except Exception as e:
            logger.error(f"Error executing workflow: {e}")
            return None
    
    @staticmethod
    async def map_intent_to_workflow(
        intent_name: str,
        workflow_id: str,
        user_id: str,
        client_id: Optional[str] = None,
        confidence_threshold: float = 0.7
    ) -> Optional[Dict[str, Any]]:
        """Map an intent to a workflow."""
        try:
            if not (0 <= confidence_threshold <= 1):
                logger.error("Confidence threshold must be between 0 and 1")
                return None
            
            query = """
                INSERT INTO intent_workflows 
                (intent_name, workflow_id, confidence_threshold, user_id, client_id)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (intent_name, workflow_id, user_id, client_id) DO UPDATE
                SET confidence_threshold = $3, updated_at = CURRENT_TIMESTAMP
                RETURNING id, intent_name, workflow_id, confidence_threshold, created_at, updated_at
            """
            
            rows = await database.query(
                query,
                [intent_name, UUID(workflow_id), confidence_threshold,
                 UUID(user_id), UUID(client_id) if client_id else None]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error mapping intent to workflow: {e}")
            return None
    
    @staticmethod
    async def get_workflow_for_intent(
        intent_name: str,
        user_id: str,
        client_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get workflow for a detected intent."""
        try:
            query = """
                SELECT iw.id, iw.intent_name, iw.workflow_id, iw.confidence_threshold,
                       w.name as workflow_name, w.description, w.entry_capability_id, w.is_active
                FROM intent_workflows iw
                JOIN workflows w ON iw.workflow_id = w.id
                WHERE iw.intent_name = $1 
                AND (iw.user_id = $2 OR iw.client_id = $3)
                AND w.is_active = TRUE
                LIMIT 1
            """
            
            rows = await database.query(
                query,
                [intent_name, UUID(user_id), UUID(client_id) if client_id else None]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting workflow for intent: {e}")
            return None
    
    @staticmethod
    async def get_intents_for_workflow(workflow_id: str) -> List[Dict[str, Any]]:
        """Get all intents mapped to a workflow."""
        try:
            query = """
                SELECT id, intent_name, confidence_threshold, created_at, updated_at
                FROM intent_workflows
                WHERE workflow_id = $1
                ORDER BY created_at DESC
            """
            
            rows = await database.query(query, [UUID(workflow_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting intents for workflow: {e}")
            return []
    
    @staticmethod
    async def remove_intent_workflow_mapping(
        intent_name: str,
        workflow_id: str,
        user_id: str,
        client_id: Optional[str] = None
    ) -> bool:
        """Remove an intent-to-workflow mapping."""
        try:
            query = """
                DELETE FROM intent_workflows
                WHERE intent_name = $1 AND workflow_id = $2
                AND (user_id = $3 OR client_id = $4)
            """
            
            await database.query(
                query,
                [intent_name, UUID(workflow_id), UUID(user_id),
                 UUID(client_id) if client_id else None]
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error removing intent workflow mapping: {e}")
            return False
