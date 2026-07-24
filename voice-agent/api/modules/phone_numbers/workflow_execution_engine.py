"""
Workflow Execution Engine.
Dynamic workflow execution with steps, conditions, and actions.
No hardcoded workflow logic.
"""

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone
from api import database

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.workflow_execution_engine")


class WorkflowExecutionEngine:
    """Engine for executing workflows dynamically."""
    
    @staticmethod
    async def create_execution(
        session_id: str,
        workflow_id: str
    ) -> Optional[Dict[str, Any]]:
        """Create a new workflow execution."""
        try:
            # Get first step of workflow
            query = """
                SELECT id FROM workflow_steps
                WHERE workflow_id = $1
                ORDER BY step_order ASC
                LIMIT 1
            """
            
            rows = await database.query(query, [UUID(workflow_id)])
            first_step_id = rows[0]["id"] if rows else None
            
            # Get session ID
            session_query = "SELECT id FROM conversation_sessions WHERE session_id = $1"
            session_rows = await database.query(session_query, [session_id])
            if not session_rows:
                return None
            
            session_uuid = session_rows[0]["id"]
            
            # Create execution
            exec_query = """
                INSERT INTO workflow_executions 
                (session_id, workflow_id, current_step_id, status)
                VALUES ($1, $2, $3, 'running')
                RETURNING id, session_id, workflow_id, current_step_id, status, created_at
            """
            
            exec_rows = await database.query(
                exec_query,
                [UUID(session_uuid), UUID(workflow_id), UUID(first_step_id) if first_step_id else None]
            )
            
            return exec_rows[0] if exec_rows else None
            
        except Exception as e:
            logger.error(f"Error creating workflow execution: {e}")
            return None
    
    @staticmethod
    async def get_execution(execution_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow execution details."""
        try:
            query = """
                SELECT id, session_id, workflow_id, current_step_id, status,
                       execution_context, workflow_context, customer_context,
                       plugin_results, extracted_entities, memory,
                       started_at, completed_at, created_at, updated_at
                FROM workflow_executions
                WHERE id = $1
            """
            
            rows = await database.query(query, [UUID(execution_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting workflow execution: {e}")
            return None
    
    @staticmethod
    async def load_workflow_steps(workflow_id: str) -> List[Dict[str, Any]]:
        """Load all steps for a workflow."""
        try:
            query = """
                SELECT id, workflow_id, step_order, step_type, configuration, next_step_id
                FROM workflow_steps
                WHERE workflow_id = $1
                ORDER BY step_order ASC
            """
            
            rows = await database.query(query, [UUID(workflow_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error loading workflow steps: {e}")
            return []
    
    @staticmethod
    async def get_step(step_id: str) -> Optional[Dict[str, Any]]:
        """Get step details."""
        try:
            query = """
                SELECT id, workflow_id, step_order, step_type, configuration, next_step_id
                FROM workflow_steps
                WHERE id = $1
            """
            
            rows = await database.query(query, [UUID(step_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting step: {e}")
            return None
    
    @staticmethod
    async def get_step_conditions(step_id: str) -> List[Dict[str, Any]]:
        """Get all conditions for a step."""
        try:
            query = """
                SELECT id, workflow_step_id, condition_type, configuration,
                       true_step_id, false_step_id
                FROM workflow_conditions
                WHERE workflow_step_id = $1
            """
            
            rows = await database.query(query, [UUID(step_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting step conditions: {e}")
            return []
    
    @staticmethod
    async def get_step_actions(step_id: str) -> List[Dict[str, Any]]:
        """Get all actions for a step."""
        try:
            query = """
                SELECT id, workflow_step_id, action_type, configuration, execution_order
                FROM workflow_actions
                WHERE workflow_step_id = $1
                ORDER BY execution_order ASC
            """
            
            rows = await database.query(query, [UUID(step_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting step actions: {e}")
            return []
    
    @staticmethod
    async def execute_step(
        execution_id: str,
        step_id: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a workflow step.
        
        Returns:
        {
            "status": "completed|failed|paused",
            "next_step_id": UUID or None,
            "context": updated context,
            "events": list of events
        }
        """
        try:
            step = await WorkflowExecutionEngine.get_step(step_id)
            if not step:
                return {"status": "failed", "error": "Step not found"}
            
            events = []
            
            # Execute based on step type
            if step["step_type"] == "condition":
                # Evaluate conditions
                conditions = await WorkflowExecutionEngine.get_step_conditions(step_id)
                next_step_id = step["next_step_id"]
                
                for condition in conditions:
                    # Evaluate condition (simplified - extend for specific condition types)
                    result = await WorkflowExecutionEngine.evaluate_condition(
                        condition,
                        context
                    )
                    
                    if result:
                        next_step_id = condition.get("true_step_id") or step["next_step_id"]
                    else:
                        next_step_id = condition.get("false_step_id") or step["next_step_id"]
                    
                    break
                
                return {
                    "status": "completed",
                    "next_step_id": next_step_id,
                    "context": context,
                    "events": events
                }
            
            elif step["step_type"] == "action":
                # Execute actions
                actions = await WorkflowExecutionEngine.get_step_actions(step_id)
                
                for action in actions:
                    result = await WorkflowExecutionEngine.execute_action(
                        action,
                        context,
                        execution_id
                    )
                    
                    if result.get("status") == "failed":
                        return {
                            "status": "failed",
                            "error": result.get("error"),
                            "context": context,
                            "events": events
                        }
                    
                    # Update context with action results
                    if result.get("context_updates"):
                        context.update(result["context_updates"])
                    
                    if result.get("event"):
                        events.append(result["event"])
                
                return {
                    "status": "completed",
                    "next_step_id": step.get("next_step_id"),
                    "context": context,
                    "events": events
                }
            
            elif step["step_type"] == "capability":
                # Capability step - return capability info
                config = step.get("configuration", {})
                return {
                    "status": "completed",
                    "next_step_id": step.get("next_step_id"),
                    "context": {**context, "capability_id": config.get("capability_id")},
                    "events": events
                }
            
            elif step["step_type"] == "end":
                return {
                    "status": "completed",
                    "next_step_id": None,
                    "context": context,
                    "events": events
                }
            
            elif step["step_type"] == "wait":
                # Wait step
                config = step.get("configuration", {})
                return {
                    "status": "paused",
                    "next_step_id": step.get("next_step_id"),
                    "context": context,
                    "events": events,
                    "wait_duration": config.get("duration_seconds")
                }
            
            else:
                return {
                    "status": "completed",
                    "next_step_id": step.get("next_step_id"),
                    "context": context,
                    "events": events
                }
            
        except Exception as e:
            logger.error(f"Error executing step: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    @staticmethod
    async def evaluate_condition(
        condition: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """
        Evaluate a workflow condition.
        Extension point for custom condition types.
        """
        try:
            condition_type = condition.get("condition_type")
            config = condition.get("configuration", {})
            
            if condition_type == "intent_match":
                detected_intent = context.get("detected_intent")
                expected_intent = config.get("intent")
                return detected_intent == expected_intent
            
            elif condition_type == "entity_exists":
                entity_name = config.get("entity_name")
                entities = context.get("extracted_entities", {})
                return entity_name in entities
            
            elif condition_type == "business_hours":
                # Check if current time is within business hours
                # Placeholder - implement with business hours service
                return True
            
            elif condition_type == "customer_exists":
                customer_id = context.get("customer_id")
                return customer_id is not None
            
            elif condition_type == "confidence_score":
                confidence = context.get("intent_confidence", 0)
                threshold = config.get("threshold", 0.7)
                return confidence >= threshold
            
            elif condition_type == "custom_expression":
                # Placeholder for custom expression evaluation
                return True
            
            else:
                return True
            
        except Exception as e:
            logger.error(f"Error evaluating condition: {e}")
            return False
    
    @staticmethod
    async def execute_action(
        action: Dict[str, Any],
        context: Dict[str, Any],
        execution_id: str
    ) -> Dict[str, Any]:
        """
        Execute a workflow action.
        Extension point for custom action types.
        """
        try:
            action_type = action.get("action_type")
            config = action.get("configuration", {})
            
            if action_type == "assign_capability":
                return {
                    "status": "completed",
                    "context_updates": {
                        "assigned_capability_id": config.get("capability_id")
                    },
                    "event": {
                        "type": "capability_assigned",
                        "capability_id": config.get("capability_id")
                    }
                }
            
            elif action_type == "update_context":
                return {
                    "status": "completed",
                    "context_updates": config.get("updates", {}),
                    "event": {
                        "type": "context_updated",
                        "updates": config.get("updates", {})
                    }
                }
            
            elif action_type == "notify_supervisor":
                # Publish event for supervisor
                return {
                    "status": "completed",
                    "context_updates": {},
                    "event": {
                        "type": "supervisor_notified",
                        "message": config.get("message")
                    }
                }
            
            elif action_type == "plugin":
                # Execute plugin
                plugin_id = config.get("plugin_id")
                # Placeholder - implement with plugin registry
                return {
                    "status": "completed",
                    "context_updates": {"plugin_result": {}},
                    "event": {
                        "type": "plugin_executed",
                        "plugin_id": plugin_id
                    }
                }
            
            else:
                return {
                    "status": "completed",
                    "context_updates": {},
                    "event": {
                        "type": "action_executed",
                        "action_type": action_type
                    }
                }
            
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    @staticmethod
    async def update_execution_context(
        execution_id: str,
        **kwargs
    ) -> bool:
        """Update execution context."""
        try:
            allowed_fields = [
                "execution_context", "workflow_context", "customer_context",
                "plugin_results", "extracted_entities", "memory", "current_step_id", "status"
            ]
            
            updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
            
            if not updates:
                return True
            
            set_clause = ", ".join([f"{k} = ${i+1}" for i, k in enumerate(updates.keys())])
            values = list(updates.values()) + [UUID(execution_id)]
            
            query = f"""
                UPDATE workflow_executions
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ${len(values)}
            """
            
            await database.query(query, values)
            return True
            
        except Exception as e:
            logger.error(f"Error updating execution context: {e}")
            return False
    
    @staticmethod
    async def publish_event(
        execution_id: str,
        event_type: str,
        event_data: Optional[Dict] = None
    ) -> bool:
        """Publish a workflow event."""
        try:
            query = """
                INSERT INTO workflow_events (execution_id, event_type, event_data)
                VALUES ($1, $2, $3)
            """
            
            await database.query(
                query,
                [UUID(execution_id), event_type, event_data]
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error publishing event: {e}")
            return False
    
    @staticmethod
    async def complete_execution(
        execution_id: str,
        status: str = "completed"
    ) -> bool:
        """Mark execution as completed."""
        try:
            query = """
                UPDATE workflow_executions
                SET status = $1, completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
            """
            
            await database.query(query, [status, UUID(execution_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error completing execution: {e}")
            return False
