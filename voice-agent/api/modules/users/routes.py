"""
Users Admin Routers.
Defines endpoints for superusers to register, update, delete and list users.
"""

import string
import random
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any, List

from api.utils.api_response import ApiResponse
from api.modules.users.services import UsersService
from api.middlewares.auth import get_current_user, require_roles

router = APIRouter()
users_service = UsersService()

# --- Helpers ---

def generate_temp_password() -> str:
    """Generate a password with uppercase, lowercase, numbers, and symbols."""
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    symbols = "!@#$%^&*"
    
    password = [
        random.choice(uppercase),
        random.choice(lowercase),
        random.choice(digits),
        random.choice(symbols)
    ]
    
    all_chars = uppercase + lowercase + digits + symbols
    for _ in range(8):
        password.append(random.choice(all_chars))
        
    random.shuffle(password)
    return "".join(password)


# --- Request Models ---

class CreateUserRequest(BaseModel):
    email: EmailStr
    firstName: str = Field(..., min_length=1)
    lastName: str = Field(..., min_length=1)
    phone: Optional[str] = None
    roleName: str = Field(..., pattern="^(SUPER_ADMIN|FINANCE_ADMIN|RESELLER|CLIENT)$")
    resellerId: Optional[str] = None
    clientId: Optional[str] = None


class UpdateUserRequest(BaseModel):
    email: Optional[EmailStr] = None
    firstName: Optional[str] = Field(None, min_length=1)
    lastName: Optional[str] = Field(None, min_length=1)
    phone: Optional[str] = None
    roleName: Optional[str] = Field(None, pattern="^(SUPER_ADMIN|FINANCE_ADMIN|RESELLER|CLIENT)$")
    resellerId: Optional[str] = None
    clientId: Optional[str] = None
    isActive: Optional[bool] = None
    isVerified: Optional[bool] = None


# --- Route Endpoints ---
# All user endpoints require SUPER_ADMIN authority

@router.get("", dependencies=[Depends(require_roles(["SUPER_ADMIN"]))])
async def get_all():
    users = await users_service.get_all_users()
    return ApiResponse.success(
        status_code=200,
        message="Users retrieved successfully",
        data=users
    )


@router.get("/{user_id}", dependencies=[Depends(require_roles(["SUPER_ADMIN"]))])
async def get_one(user_id: str):
    user = await users_service.get_user_by_id(user_id)
    if not user:
        return ApiResponse.error(
            status_code=404,
            message="User not found",
            code="USER_NOT_FOUND"
        )
    return ApiResponse.success(
        status_code=200,
        message="User retrieved successfully",
        data=user
    )


@router.post("", dependencies=[Depends(require_roles(["SUPER_ADMIN"]))])
async def create(req_body: CreateUserRequest, request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    temp_password = generate_temp_password()
    dto = req_body.dict()
    
    created = await users_service.create_user(
        dto, 
        temp_password, 
        current_user["id"], 
        client_ip, 
        user_agent
    )
    
    return ApiResponse.success(
        status_code=201,
        message="User created successfully",
        data={
            "user": created,
            "credentials": {
                "email": req_body.email,
                "password": temp_password
            }
        }
    )


@router.put("/{user_id}", dependencies=[Depends(require_roles(["SUPER_ADMIN"]))])
async def update(user_id: str, req_body: UpdateUserRequest, request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    dto = req_body.dict(exclude_unset=True)
    updated = await users_service.update_user(
        user_id, 
        dto, 
        current_user["id"], 
        client_ip, 
        user_agent
    )
    
    return ApiResponse.success(
        status_code=200,
        message="User updated successfully",
        data=updated
    )


@router.delete("/{user_id}", dependencies=[Depends(require_roles(["SUPER_ADMIN"]))])
async def delete(user_id: str, request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    await users_service.delete_user(
        user_id, 
        current_user["id"], 
        client_ip, 
        user_agent
    )
    
    return ApiResponse.success(
        status_code=200,
        message="User deleted successfully"
    )
