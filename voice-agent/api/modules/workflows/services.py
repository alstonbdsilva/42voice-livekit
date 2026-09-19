"""
Workflows business logic service.
Manages workflow authoring, validation, publication, immutability, and tenant security.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from api.modules.workflows.repositories import WorkflowRepository
from api.modules.workflows.models import (
    map_workflow_row,
    map_workflow_version_row,
    map_workflow_run_row
)
from api.utils.errors import NotFoundError, BadRequestError, ForbiddenError
from workflow_engine import (
    WorkflowParser,
    WorkflowValidator,
    WorkflowCompiler,
    WorkflowGraph,
    ToolPlatform,
    tool_platform,
    SystemToolRegistry
)

logger = logging.getLogger("voice-agent.api.workflows.services")


class WorkflowService:
    """Service orchestrating workflows domain logic, compilation, and version immutability."""

    def __init__(self):
        self.repository = WorkflowRepository()

    def _verify_tenant_ownership(self, workflow_record: Dict[str, Any], user_context: Dict[str, Any]) -> None:
        """Verify that the user/tenant is authorized to access the workflow."""
        role = user_context.get("role")
        if role in ["SUPER_ADMIN", "FINANCE_ADMIN"]:
            return

        client_id = user_context.get("client_id")
        user_id = user_context.get("id") or user_context.get("userId")

        record_client_id = str(workflow_record["client_id"]) if workflow_record.get("client_id") else None
        record_user_id = str(workflow_record["user_id"]) if workflow_record.get("user_id") else None

        if client_id and record_client_id and client_id == record_client_id:
            return

        if user_id and record_user_id and user_id == record_user_id:
            return

        raise ForbiddenError("You do not have permission to access this workflow.", "TENANT_ACCESS_DENIED")

    async def create_workflow(self, data: Dict[str, Any], user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new workflow container and initial draft."""
        payload = {
            "name": data["name"],
            "description": data.get("description"),
            "status": "active",
            "clientId": user_context.get("client_id"),
            "userId": user_context.get("id") or user_context.get("userId")
        }
        wf = await self.repository.create_workflow(payload)
        logger.info(f"[WF_DB] workflow_created workflow_id={wf['id']}")
        return map_workflow_row(wf)

    async def get_all_workflows(self, user_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """List workflows within authorized tenant scope."""
        filter_data = {
            "role": user_context.get("role"),
            "userId": user_context.get("id") or user_context.get("userId"),
            "clientId": user_context.get("client_id"),
            "resellerId": user_context.get("reseller_id")
        }
        rows = await self.repository.find_all(filter_data)
        return [map_workflow_row(r) for r in rows]

    async def get_workflow_by_id(self, workflow_id: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve a single workflow by ID with ownership verification."""
        wf = await self.repository.find_by_id(workflow_id)
        if not wf:
            raise NotFoundError(f"Workflow '{workflow_id}' not found", "WORKFLOW_NOT_FOUND")
        self._verify_tenant_ownership(wf, user_context)
        return map_workflow_row(wf)

    async def update_workflow(self, workflow_id: str, data: Dict[str, Any], user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Update top-level workflow metadata."""
        wf = await self.repository.find_by_id(workflow_id)
        if not wf:
            raise NotFoundError(f"Workflow '{workflow_id}' not found", "WORKFLOW_NOT_FOUND")
        self._verify_tenant_ownership(wf, user_context)

        updated = await self.repository.update_workflow(workflow_id, data)
        return map_workflow_row(updated)

    async def get_draft(self, workflow_id: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve current editable draft for a workflow."""
        wf = await self.repository.find_by_id(workflow_id)
        if not wf:
            raise NotFoundError(f"Workflow '{workflow_id}' not found", "WORKFLOW_NOT_FOUND")
        self._verify_tenant_ownership(wf, user_context)

        draft = await self.repository.get_or_create_draft(workflow_id)
        return map_workflow_version_row(draft)

    async def update_draft(self, workflow_id: str, data: Dict[str, Any], user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Save updates to the mutable draft version."""
        wf = await self.repository.find_by_id(workflow_id)
        if not wf:
            raise NotFoundError(f"Workflow '{workflow_id}' not found", "WORKFLOW_NOT_FOUND")
        self._verify_tenant_ownership(wf, user_context)

        definition = data.get("definition", {})
        ui_metadata = data.get("ui_metadata", {})

        # Optional defensive validation preview
        validation_res = self.validate_definition(definition, client_id=user_context.get("client_id"))
        validation_metadata = {
            "valid": validation_res["valid"],
            "error_count": len(validation_res["errors"]),
            "warning_count": len(validation_res["warnings"])
        }

        updated_draft = await self.repository.update_draft(
            workflow_id=workflow_id,
            definition=definition,
            ui_metadata=ui_metadata,
            validation_metadata=validation_metadata
        )
        logger.info(f"[WF_DB] draft_updated workflow_id={workflow_id}")
        return map_workflow_version_row(updated_draft)

    def validate_definition(self, definition: Dict[str, Any], client_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate workflow graph definition using parser, validator, and compiler.
        Returns structured errors without throwing raw Python stack traces.
        """
        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []
        node_count = 0
        edge_count = 0

        try:
            # 1. Parse JSON definition into WorkflowGraph
            graph = WorkflowParser.parse(definition)
            node_count = len(graph.nodes)
            edge_count = len(graph.edges)

            # 2. Build scoped tool platform view for validation
            scoped_tp = ToolPlatform(client_id=client_id)

            # 3. Validate graph rules
            val_errors = WorkflowValidator.validate(graph, scoped_tp)
            for err in val_errors:
                errors.append({
                    "code": "VALIDATION_ERROR",
                    "message": str(err),
                    "node_id": None,
                    "edge_id": None
                })

            # 4. Attempt dry compilation if validation passed
            if not errors:
                try:
                    WorkflowCompiler.compile(graph, scoped_tp)
                except Exception as compile_err:
                    errors.append({
                        "code": "COMPILATION_ERROR",
                        "message": str(compile_err),
                        "node_id": None,
                        "edge_id": None
                    })

        except Exception as parse_err:
            errors.append({
                "code": "PARSE_ERROR",
                "message": str(parse_err),
                "node_id": None,
                "edge_id": None
            })

        is_valid = len(errors) == 0
        logger.info(f"[WF_VALIDATE] valid={is_valid} errors_count={len(errors)} warnings_count={len(warnings)}")
        return {
            "valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "node_count": node_count,
            "edge_count": edge_count
        }

    async def publish_workflow(self, workflow_id: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate current draft and publish an immutable new snapshot.
        Enforces parent workflow row locking and concurrency safety.
        """
        wf = await self.repository.find_by_id(workflow_id)
        if not wf:
            raise NotFoundError(f"Workflow '{workflow_id}' not found", "WORKFLOW_NOT_FOUND")
        self._verify_tenant_ownership(wf, user_context)

        draft = await self.repository.get_or_create_draft(workflow_id)
        if not draft:
            raise BadRequestError("Cannot publish workflow: no draft version exists.", "NO_DRAFT_FOUND")

        raw_def = draft.get("definition") or {}
        if isinstance(raw_def, str):
            raw_def = json.loads(raw_def)

        # 1. Validate definition before publication
        val_result = self.validate_definition(raw_def, client_id=user_context.get("client_id"))
        if not val_result["valid"]:
            error_details = "; ".join([e["message"] for e in val_result["errors"]])
            raise BadRequestError(
                f"Cannot publish invalid workflow definition: {error_details}",
                "WORKFLOW_VALIDATION_FAILED"
            )

        raw_ui = draft.get("ui_metadata") or {}
        if isinstance(raw_ui, str):
            raw_ui = json.loads(raw_ui)

        # 2. Transactional publication with row locking
        user_id = user_context.get("id") or user_context.get("userId")
        published_version = await self.repository.publish_version(
            workflow_id=workflow_id,
            definition=raw_def,
            ui_metadata=raw_ui,
            validation_metadata={"valid": True, "published": True},
            user_id=user_id
        )

        return map_workflow_version_row(published_version)

    async def list_versions(self, workflow_id: str, user_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """List all published versions of a workflow."""
        wf = await self.repository.find_by_id(workflow_id)
        if not wf:
            raise NotFoundError(f"Workflow '{workflow_id}' not found", "WORKFLOW_NOT_FOUND")
        self._verify_tenant_ownership(wf, user_context)

        versions = await self.repository.list_versions(workflow_id)
        return [map_workflow_version_row(v) for v in versions]

    async def get_version_by_id(self, workflow_id: str, version_id: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Get specific immutable version snapshot."""
        wf = await self.repository.find_by_id(workflow_id)
        if not wf:
            raise NotFoundError(f"Workflow '{workflow_id}' not found", "WORKFLOW_NOT_FOUND")
        self._verify_tenant_ownership(wf, user_context)

        version = await self.repository.find_version_by_id(version_id)
        if not version or str(version["workflow_id"]) != str(workflow_id):
            raise NotFoundError(f"Workflow version '{version_id}' not found for workflow '{workflow_id}'", "VERSION_NOT_FOUND")

        return map_workflow_version_row(version)
