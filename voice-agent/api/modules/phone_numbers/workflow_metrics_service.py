"""
Workflow Metrics Service.
Tracks workflow execution metrics and observability.
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from api import database

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.workflow_metrics_service")


class WorkflowMetricsService:
    """Service for tracking workflow metrics."""
    
    @staticmethod
    async def initialize_metrics(workflow_id: str) -> Optional[Dict[str, Any]]:
        """Initialize metrics for a workflow."""
        try:
            query = """
                INSERT INTO workflow_metrics (workflow_id)
                VALUES ($1)
                ON CONFLICT (workflow_id) DO NOTHING
                RETURNING workflow_id, execution_count, success_count, failure_count,
                         escalation_count, average_execution_time_ms, average_step_time_ms,
                         average_plugin_time_ms, last_execution_at
            """
            
            rows = await database.query(query, [UUID(workflow_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error initializing metrics: {e}")
            return None
    
    @staticmethod
    async def get_metrics(workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a workflow."""
        try:
            query = """
                SELECT workflow_id, execution_count, success_count, failure_count,
                       escalation_count, average_execution_time_ms, average_step_time_ms,
                       average_plugin_time_ms, last_execution_at, created_at, updated_at
                FROM workflow_metrics
                WHERE workflow_id = $1
            """
            
            rows = await database.query(query, [UUID(workflow_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return None
    
    @staticmethod
    async def record_execution(
        workflow_id: str,
        execution_time_ms: int,
        status: str,
        step_time_ms: int = 0,
        plugin_time_ms: int = 0
    ) -> bool:
        """Record a workflow execution."""
        try:
            # Get current metrics
            metrics = await WorkflowMetricsService.get_metrics(workflow_id)
            
            if not metrics:
                await WorkflowMetricsService.initialize_metrics(workflow_id)
                metrics = await WorkflowMetricsService.get_metrics(workflow_id)
            
            # Calculate new averages
            execution_count = metrics["execution_count"] + 1
            success_count = metrics["success_count"] + (1 if status == "completed" else 0)
            failure_count = metrics["failure_count"] + (1 if status == "failed" else 0)
            escalation_count = metrics["escalation_count"] + (1 if status == "escalated" else 0)
            
            # Calculate running average
            old_avg_exec = metrics["average_execution_time_ms"] or 0
            new_avg_exec = int((old_avg_exec * (execution_count - 1) + execution_time_ms) / execution_count)
            
            old_avg_step = metrics["average_step_time_ms"] or 0
            new_avg_step = int((old_avg_step * (execution_count - 1) + step_time_ms) / execution_count) if step_time_ms > 0 else old_avg_step
            
            old_avg_plugin = metrics["average_plugin_time_ms"] or 0
            new_avg_plugin = int((old_avg_plugin * (execution_count - 1) + plugin_time_ms) / execution_count) if plugin_time_ms > 0 else old_avg_plugin
            
            # Update metrics
            query = """
                UPDATE workflow_metrics
                SET execution_count = $1,
                    success_count = $2,
                    failure_count = $3,
                    escalation_count = $4,
                    average_execution_time_ms = $5,
                    average_step_time_ms = $6,
                    average_plugin_time_ms = $7,
                    last_execution_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE workflow_id = $8
            """
            
            await database.query(
                query,
                [execution_count, success_count, failure_count, escalation_count,
                 new_avg_exec, new_avg_step, new_avg_plugin, UUID(workflow_id)]
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error recording execution: {e}")
            return False
    
    @staticmethod
    async def get_success_rate(workflow_id: str) -> Optional[float]:
        """Get workflow success rate."""
        try:
            metrics = await WorkflowMetricsService.get_metrics(workflow_id)
            
            if not metrics or metrics["execution_count"] == 0:
                return None
            
            success_rate = (metrics["success_count"] / metrics["execution_count"]) * 100
            return round(success_rate, 2)
            
        except Exception as e:
            logger.error(f"Error getting success rate: {e}")
            return None
    
    @staticmethod
    async def get_failure_rate(workflow_id: str) -> Optional[float]:
        """Get workflow failure rate."""
        try:
            metrics = await WorkflowMetricsService.get_metrics(workflow_id)
            
            if not metrics or metrics["execution_count"] == 0:
                return None
            
            failure_rate = (metrics["failure_count"] / metrics["execution_count"]) * 100
            return round(failure_rate, 2)
            
        except Exception as e:
            logger.error(f"Error getting failure rate: {e}")
            return None
    
    @staticmethod
    async def get_escalation_rate(workflow_id: str) -> Optional[float]:
        """Get workflow escalation rate."""
        try:
            metrics = await WorkflowMetricsService.get_metrics(workflow_id)
            
            if not metrics or metrics["execution_count"] == 0:
                return None
            
            escalation_rate = (metrics["escalation_count"] / metrics["execution_count"]) * 100
            return round(escalation_rate, 2)
            
        except Exception as e:
            logger.error(f"Error getting escalation rate: {e}")
            return None
