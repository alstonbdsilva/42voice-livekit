"""
Pydantic schemas and DTOs for the Workflows API.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CreateWorkflowRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class UpdateWorkflowRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(active|archived)$")


class UpdateDraftRequest(BaseModel):
    definition: Dict[str, Any] = Field(..., description="Workflow executable definition containing nodes and edges")
    ui_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Editor visualization coordinates and viewport")


class ValidateWorkflowRequest(BaseModel):
    definition: Dict[str, Any] = Field(..., description="Workflow graph definition to validate")


class ValidationErrorItem(BaseModel):
    code: str
    message: str
    node_id: Optional[str] = None
    edge_id: Optional[str] = None


class ValidationResponse(BaseModel):
    valid: bool
    errors: List[ValidationErrorItem] = []
    warnings: List[ValidationErrorItem] = []
    node_count: int = 0
    edge_count: int = 0


class PublishWorkflowRequest(BaseModel):
    description: Optional[str] = None


class AssignWorkflowVersionRequest(BaseModel):
    workflowVersionId: Optional[str] = None
