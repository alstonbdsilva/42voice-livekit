"""
Clients Routers.
Defines endpoints for managing client organizations, applying reseller scopes where necessary.
"""

from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any, List

from api.utils.api_response import ApiResponse
from api.modules.clients.services import ClientService
from api.modules.users.routes import generate_temp_password
from api.middlewares.auth import get_current_user, require_roles
from api.utils.errors import ForbiddenError

router = APIRouter()
client_service = ClientService()

# --- Request Models ---

class CreateClientRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    monthlyRecurring: Optional[float] = Field(0.00, ge=0.0)
    contactEmail: EmailStr
    resellerId: Optional[str] = None # Optional because resellers default to their own ID


class UpdateClientRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    monthlyRecurring: Optional[float] = Field(None, ge=0.0)
    contactEmail: Optional[EmailStr] = None
    status: Optional[str] = Field(None, pattern="^(active|paused|inactive)$")
    resellerId: Optional[str] = None


# --- Route Endpoints ---
# All client routes require authentication

@router.get("")
async def get_all(current_user: Dict[str, Any] = Depends(get_current_user)):
    reseller_id = current_user["reseller_id"] if current_user["role"] == "RESELLER" else None
    clients = await client_service.get_all_clients(reseller_id)
    return ApiResponse.success(
        status_code=200,
        message="Clients retrieved successfully",
        data=clients
    )


@router.get("/{client_id}")
async def get_one(client_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    client = await client_service.get_client_by_id(client_id)
    if not client:
        return ApiResponse.error(
            status_code=404,
            message="Client not found",
            code="CLIENT_NOT_FOUND"
        )
        
    # Enforce reseller scoping check
    if current_user["role"] == "RESELLER" and client["resellerId"] != current_user["reseller_id"]:
        raise ForbiddenError("You do not have access to this client organization", "CLIENT_FORBIDDEN")
        
    return ApiResponse.success(
        status_code=200,
        message="Client retrieved successfully",
        data=client
    )


@router.post("", dependencies=[Depends(require_roles(["SUPER_ADMIN", "FINANCE_ADMIN", "RESELLER"]))])
async def create(req_body: CreateClientRequest, request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    # Resellers are forced to use their own reseller ID
    reseller_id = None
    if current_user["role"] == "RESELLER":
        if not current_user["reseller_id"]:
            return ApiResponse.error(
                status_code=403,
                message="Your account is not linked to a reseller organisation.",
                code="NO_RESELLER_LINKED"
            )
        reseller_id = current_user["reseller_id"]
    else:
        reseller_id = req_body.resellerId
        if not reseller_id:
            return ApiResponse.error(
                status_code=400,
                message="resellerId is required",
                code="RESELLER_ID_REQUIRED"
            )
            
    dto = req_body.model_dump()
    dto["resellerId"] = reseller_id
    
    temp_password = generate_temp_password()
    created = await client_service.create_client(
        dto, 
        temp_password, 
        current_user["id"], 
        client_ip, 
        user_agent
    )
    
    return ApiResponse.success(
        status_code=201,
        message="Client created successfully",
        data={
            "client": created,
            "credentials": {
                "email": req_body.contactEmail,
                "password": temp_password
            }
        }
    )


@router.put("/{client_id}", dependencies=[Depends(require_roles(["SUPER_ADMIN", "FINANCE_ADMIN", "RESELLER"]))])
async def update(client_id: str, req_body: UpdateClientRequest, request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    # Enforce reseller check
    client_rec = await client_service.get_client_by_id(client_id)
    if not client_rec:
        return ApiResponse.error(
            status_code=404,
            message="Client not found",
            code="CLIENT_NOT_FOUND"
        )
    if current_user["role"] == "RESELLER" and client_rec["resellerId"] != current_user["reseller_id"]:
        raise ForbiddenError("You do not have access to edit this client", "CLIENT_FORBIDDEN")
        
    dto = req_body.model_dump(exclude_unset=True)
    # Resellers cannot modify the resellerId relationship
    if current_user["role"] == "RESELLER" and "resellerId" in dto:
        dto.pop("resellerId")
        
    updated = await client_service.update_client(
        client_id, 
        dto, 
        current_user["id"], 
        client_ip, 
        user_agent
    )
    return ApiResponse.success(
        status_code=200,
        message="Client updated successfully",
        data=updated
    )


@router.delete("/{client_id}", dependencies=[Depends(require_roles(["SUPER_ADMIN", "FINANCE_ADMIN"]))])
async def delete(client_id: str, request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    # Enforce reseller check
    client_rec = await client_service.get_client_by_id(client_id)
    if not client_rec:
        return ApiResponse.error(
            status_code=404,
            message="Client not found",
            code="CLIENT_NOT_FOUND"
        )
    if current_user["role"] == "RESELLER" and client_rec["resellerId"] != current_user["reseller_id"]:
        raise ForbiddenError("You do not have access to delete this client", "CLIENT_FORBIDDEN")
        
    await client_service.delete_client(
        client_id, 
        current_user["id"], 
        client_ip, 
        user_agent
    )
    return ApiResponse.success(
        status_code=200,
        message="Client deleted successfully"
    )
