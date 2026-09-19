"""
Workflow Runtime Resolver.
Resolves and compiles the exact immutable workflow version for an agent at call initialization.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from api.modules.workflows.repositories import WorkflowRepository
from workflow_engine import (
    WorkflowParser,
    WorkflowValidator,
    WorkflowCompiler,
    CompiledWorkflow,
    ToolPlatform,
    build_compatibility_workflow,
    tool_platform
)

logger = logging.getLogger("voice-agent.workflows.resolver")


class WorkflowRuntimeResolver:
    """
    Authoritative resolver for agent workflow definitions at call startup.
    Ensures exact pinned immutable versions are loaded and compiled without runtime drift.
    """

    def __init__(self, repository: Optional[WorkflowRepository] = None):
        self.repository = repository or WorkflowRepository()

    async def resolve_for_agent(
        self,
        agent_data: Optional[Dict[str, Any]],
        custom_prompt: Optional[str] = None,
        dynamic_tools: Optional[List[str]] = None,
        out_of_credits: bool = False,
        tool_platform_instance: Optional[ToolPlatform] = None
    ) -> Tuple[CompiledWorkflow, Optional[str], Optional[str]]:
        """
        Resolves the workflow definition for an active call.
        
        Returns:
            (CompiledWorkflow, workflow_id, workflow_version_id)
            
        Policy:
        - NULL published_workflow_version_id -> runtime compatibility workflow (legacy behavior)
        - NON-NULL published_workflow_version_id -> loads and compiles EXACT pinned version
        - Corrupt / missing / invalid published workflow -> raises RuntimeError (NO silent fallback)
        """
        tp = tool_platform_instance or tool_platform
        wf_version_id = agent_data.get("published_workflow_version_id") if agent_data else None

        # 1. Compatibility workflow when no published version is assigned
        if not wf_version_id:
            logger.info("[WF_RESOLVE] No published_workflow_version_id assigned -> using compatibility workflow")
            compiled_compat = build_compatibility_workflow(
                agent_data=agent_data,
                custom_prompt=custom_prompt,
                dynamic_tool_names=dynamic_tools,
                out_of_credits=out_of_credits,
                tool_platform_instance=tp
            )
            return compiled_compat, None, None

        # 2. Exact version resolution
        logger.info(f"[WF_RESOLVE] Resolving exact pinned workflow_version_id={wf_version_id}")
        version_row = await self.repository.find_version_by_id(str(wf_version_id))
        if not version_row:
            err_msg = f"Assigned published workflow version '{wf_version_id}' not found in database."
            logger.error(f"[WF_RUN] failed error=version_not_found workflow_version_id={wf_version_id}")
            raise RuntimeError(err_msg)

        if version_row.get("lifecycle_status") != "published":
            err_msg = f"Workflow version '{wf_version_id}' is not in 'published' state (status={version_row.get('lifecycle_status')})."
            logger.error(f"[WF_RUN] failed error=version_not_published workflow_version_id={wf_version_id}")
            raise RuntimeError(err_msg)

        raw_definition = version_row.get("definition") or {}
        if isinstance(raw_definition, str):
            try:
                raw_definition = json.loads(raw_definition)
            except Exception as e:
                err_msg = f"Failed to parse definition for version '{wf_version_id}': {e}"
                logger.error(f"[WF_RUN] failed error=corrupt_definition workflow_version_id={wf_version_id}")
                raise RuntimeError(err_msg)

        try:
            # Parse
            graph = WorkflowParser.parse(raw_definition)
            # Validate
            val_errors = WorkflowValidator.validate(graph, tp)
            if val_errors:
                err_msg = f"Validation failed for version '{wf_version_id}': {'; '.join(val_errors)}"
                logger.error(f"[WF_RUN] failed error=validation_failed workflow_version_id={wf_version_id} details={val_errors}")
                raise RuntimeError(err_msg)
            # Compile
            compiled = WorkflowCompiler.compile(graph, tp)
            logger.info(f"[WF_RESOLVE] Successfully compiled pinned workflow_id={version_row['workflow_id']} version_number={version_row['version_number']} version_id={wf_version_id}")
            return compiled, str(version_row["workflow_id"]), str(wf_version_id)
        except Exception as compile_err:
            logger.error(f"[WF_RUN] failed error=compile_error workflow_version_id={wf_version_id}: {compile_err}")
            raise RuntimeError(f"Failed to compile pinned workflow version '{wf_version_id}': {compile_err}")
