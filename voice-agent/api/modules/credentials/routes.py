"""
Credentials Router.
Defines HTTP routes for managing client credentials used by tools.
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.middlewares.auth import get_current_user
from api.modules.credentials.services import CredentialService
from api.utils.api_response import ApiResponse

router = APIRouter()
service = CredentialService()


class CreateCredentialRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    credential_type: str = Field(..., min_length=1)
    credential_data: Dict[str, Any] = Field(default_factory=dict)


class UpdateCredentialRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    credential_type: Optional[str] = None
    credential_data: Optional[Dict[str, Any]] = None


@router.get("")
async def list_credentials(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    client_id = current_user.get("client_id")
    if not client_id:
        return ApiResponse.success(message="No credentials available for non-client contexts", data=[])
    
    creds = await service.list_credentials(client_id)
    return ApiResponse.success(message="Credentials retrieved successfully", data=creds)


@router.post("")
async def create_credential(
    request: CreateCredentialRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    cred = await service.create_credential(request.dict(), current_user)
    return ApiResponse.success(status_code=201, message="Credential created successfully", data=cred)


@router.get("/{credential_uuid}")
async def get_credential(
    credential_uuid: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    client_id = current_user.get("client_id")
    if not client_id:
        return ApiResponse.error(status_code=400, message="Client context required", code="CLIENT_REQUIRED")
    
    cred = await service.get_credential(credential_uuid, client_id)
    return ApiResponse.success(message="Credential retrieved successfully", data=cred)


@router.put("/{credential_uuid}")
async def update_credential(
    credential_uuid: str,
    request: UpdateCredentialRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    cred = await service.update_credential(credential_uuid, request.dict(exclude_unset=True), current_user)
    return ApiResponse.success(message="Credential updated successfully", data=cred)


@router.delete("/{credential_uuid}")
async def delete_credential(
    credential_uuid: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    res = await service.delete_credential(credential_uuid, current_user)
    return ApiResponse.success(message="Credential deleted successfully", data=res)
