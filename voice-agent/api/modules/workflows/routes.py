"""
FastAPI route endpoints for the Workflows API.
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Request

from api.utils.api_response import ApiResponse
from api.middlewares.auth import get_current_user
from api.modules.workflows.services import WorkflowService
from api.modules.workflows.schemas import (
    CreateWorkflowRequest,
    UpdateWorkflowRequest,
    UpdateDraftRequest,
    ValidateWorkflowRequest,
    PublishWorkflowRequest
)

logger = logging.getLogger("voice-agent.api.workflows.routes")

router = APIRouter()
workflow_service = WorkflowService()


@router.post("")
async def create_workflow(
    req_body: CreateWorkflowRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new logical workflow."""
    wf = await workflow_service.create_workflow(req_body.model_dump(), current_user)
    return ApiResponse.success(
        status_code=201,
        message="Workflow created successfully",
        data=wf
    )


@router.get("")
async def get_all_workflows(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List all workflows accessible to current user/tenant."""
    wfs = await workflow_service.get_all_workflows(current_user)
    return ApiResponse.success(
        status_code=200,
        message="Workflows retrieved successfully",
        data=wfs
    )


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get single workflow by ID."""
    wf = await workflow_service.get_workflow_by_id(workflow_id, current_user)
    return ApiResponse.success(
        status_code=200,
        message="Workflow retrieved successfully",
        data=wf
    )


@router.patch("/{workflow_id}")
async def update_workflow(
    workflow_id: str,
    req_body: UpdateWorkflowRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update top-level workflow metadata."""
    wf = await workflow_service.update_workflow(workflow_id, req_body.model_dump(exclude_unset=True), current_user)
    return ApiResponse.success(
        status_code=200,
        message="Workflow updated successfully",
        data=wf
    )


@router.get("/{workflow_id}/draft")
async def get_draft(
    workflow_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get mutable draft definition for a workflow."""
    draft = await workflow_service.get_draft(workflow_id, current_user)
    return ApiResponse.success(
        status_code=200,
        message="Draft retrieved successfully",
        data=draft
    )


@router.put("/{workflow_id}/draft")
async def update_draft(
    workflow_id: str,
    req_body: UpdateDraftRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Save changes to the mutable workflow draft."""
    draft = await workflow_service.update_draft(workflow_id, req_body.model_dump(), current_user)
    return ApiResponse.success(
        status_code=200,
        message="Draft saved successfully",
        data=draft
    )


@router.post("/{workflow_id}/validate")
async def validate_workflow(
    workflow_id: str,
    req_body: ValidateWorkflowRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Validate a workflow definition without publishing."""
    # Verify tenant ownership first
    await workflow_service.get_workflow_by_id(workflow_id, current_user)
    val_res = workflow_service.validate_definition(req_body.definition, client_id=current_user.get("client_id"))
    return ApiResponse.success(
        status_code=200,
        message="Workflow validated",
        data=val_res
    )


@router.post("/{workflow_id}/publish")
async def publish_workflow(
    workflow_id: str,
    req_body: Optional[PublishWorkflowRequest] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Validate draft and publish an immutable new snapshot version."""
    published = await workflow_service.publish_workflow(workflow_id, current_user)
    return ApiResponse.success(
        status_code=201,
        message="Workflow published successfully",
        data=published
    )


@router.get("/{workflow_id}/versions")
async def list_versions(
    workflow_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List all immutable published versions of a workflow."""
    versions = await workflow_service.list_versions(workflow_id, current_user)
    return ApiResponse.success(
        status_code=200,
        message="Workflow versions retrieved successfully",
        data=versions
    )


@router.get("/{workflow_id}/versions/{version_id}")
async def get_version(
    workflow_id: str,
    version_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get a specific published version snapshot."""
    version = await workflow_service.get_version_by_id(workflow_id, version_id, current_user)
    return ApiResponse.success(
        status_code=200,
        message="Workflow version retrieved successfully",
        data=version
    )
