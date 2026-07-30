"""
Resellers Routers.
Defines endpoints for administrative management of reseller partners.
"""

from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any, List

from api.utils.api_response import ApiResponse
from api.modules.resellers.services import ResellerService
from api.modules.users.routes import generate_temp_password
from api.middlewares.auth import get_current_user, require_roles

router = APIRouter()
reseller_service = ResellerService()

# --- Request Models ---

class CreateResellerRequest(BaseModel):
    name: str = Field(..., min_length=1)
    country: str = Field(..., min_length=1)
    commissionPct: float = Field(..., ge=0.0, le=100.0)
    contactEmail: EmailStr


class UpdateResellerRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    country: Optional[str] = Field(None, min_length=1)
    commissionPct: Optional[float] = Field(None, ge=0.0, le=100.0)
    contactEmail: Optional[EmailStr] = None
    status: Optional[str] = Field(None, pattern="^(active|inactive)$")


# --- Endpoint Route Definitions ---
# Require SUPER_ADMIN or FINANCE_ADMIN role for partner reseller operations

@router.get("", dependencies=[Depends(require_roles(["SUPER_ADMIN", "FINANCE_ADMIN"]))])
async def get_all():
    resellers = await reseller_service.get_all_resellers()
    return ApiResponse.success(
        status_code=200,
        message="Resellers retrieved successfully",
        data=resellers
    )


@router.get("/{reseller_id}", dependencies=[Depends(require_roles(["SUPER_ADMIN", "FINANCE_ADMIN"]))])
async def get_one(reseller_id: str):
    reseller = await reseller_service.get_reseller_by_id(reseller_id)
    if not reseller:
        return ApiResponse.error(
            status_code=404,
            message="Reseller not found",
            code="RESELLER_NOT_FOUND"
        )
    return ApiResponse.success(
        status_code=200,
        message="Reseller retrieved successfully",
        data=reseller
    )


@router.post("", dependencies=[Depends(require_roles(["SUPER_ADMIN", "FINANCE_ADMIN"]))])
async def create(req_body: CreateResellerRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    temp_password = generate_temp_password()
    dto = req_body.model_dump()
    
    created = await reseller_service.create_reseller(
        dto, 
        temp_password, 
        client_ip, 
        user_agent
    )
    
    return ApiResponse.success(
        status_code=201,
        message="Reseller created successfully",
        data={
            "reseller": created,
            "credentials": {
                "email": req_body.contactEmail,
                "password": temp_password
            }
        }
    )


@router.put("/{reseller_id}", dependencies=[Depends(require_roles(["SUPER_ADMIN", "FINANCE_ADMIN"]))])
async def update(reseller_id: str, req_body: UpdateResellerRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    dto = req_body.model_dump(exclude_unset=True)
    updated = await reseller_service.update_reseller(
        reseller_id, 
        dto, 
        client_ip, 
        user_agent
    )
    
    return ApiResponse.success(
        status_code=200,
        message="Reseller updated successfully",
        data=updated
    )


@router.delete("/{reseller_id}", dependencies=[Depends(require_roles(["SUPER_ADMIN", "FINANCE_ADMIN"]))])
async def delete(reseller_id: str, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    await reseller_service.delete_reseller(
        reseller_id, 
        client_ip, 
        user_agent
    )
    
    return ApiResponse.success(
        status_code=200,
        message="Reseller deleted successfully"
    )
