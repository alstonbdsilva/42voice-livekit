"""
FastAPI Authentication Routers.
Defines routes, request Pydantic validations, and mounts service actions.
"""

from fastapi import APIRouter, Request, Depends, Query
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any

from api.utils.api_response import ApiResponse
from api.modules.auth.services import AuthService, TokenService
from api.middlewares.auth import get_current_user

router = APIRouter()
auth_service = AuthService()
token_service = TokenService()

# --- Pydantic Request Models ---

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    role_name: Optional[str] = "CLIENT"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    password: str = Field(..., min_length=8)


class ChangePasswordRequest(BaseModel):
    oldPassword: str = Field(..., min_length=1)
    newPassword: str = Field(..., min_length=8)


class UpdateProfileRequest(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1)
    last_name: Optional[str] = Field(None, min_length=1)
    phone: Optional[str] = None
    avatar_url: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    refreshToken: str = Field(..., min_length=1)


# --- Endpoint Route Definitions ---

@router.post("/register")
async def register(req_body: RegisterRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    # Map input schema to database DTO keys
    dto = {
        "email": req_body.email,
        "password_hash": req_body.password,
        "first_name": req_body.first_name,
        "last_name": req_body.last_name,
        "phone": req_body.phone,
        "avatar_url": req_body.avatar_url,
        "role_name": req_body.role_name
    }
    
    user = await auth_service.register(dto, client_ip, user_agent)
    return ApiResponse.success(
        status_code=201,
        message="Registration successful. Please check your email to verify your account.",
        data=user
    )


@router.post("/login")
async def login(req_body: LoginRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    result = await auth_service.login(req_body.email, req_body.password, client_ip, user_agent)
    return ApiResponse.success(
        status_code=200,
        message="Login successful",
        data=result
    )


@router.post("/refresh-token")
async def refresh_token(req_body: RefreshTokenRequest):
    new_access, new_refresh = await token_service.rotate_refresh_token(req_body.refreshToken)
    return ApiResponse.success(
        status_code=200,
        message="Token refreshed successfully",
        data={
            "accessToken": new_access,
            "refreshToken": new_refresh
        }
    )


@router.get("/verify-email")
async def verify_email(request: Request, token: str = Query(..., min_length=1)):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    await auth_service.verify_email(token, client_ip, user_agent)
    return ApiResponse.success(
        status_code=200,
        message="Email address verified successfully"
    )


@router.post("/resend-verification")
async def resend_verification(req_body: ForgotPasswordRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    await auth_service.resend_verification(req_body.email, client_ip, user_agent)
    return ApiResponse.success(
        status_code=200,
        message="Verification email has been sent successfully"
    )


@router.post("/forgot-password")
async def forgot_password(req_body: ForgotPasswordRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    await auth_service.forgot_password(req_body.email, client_ip, user_agent)
    return ApiResponse.success(
        status_code=200,
        message="If your email is registered in our platform, a reset link will be sent shortly."
    )


@router.post("/reset-password")
async def reset_password(req_body: ResetPasswordRequest, request: Request, token: str = Query(..., min_length=1)):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    await auth_service.reset_password(token, req_body.password, client_ip, user_agent)
    return ApiResponse.success(
        status_code=200,
        message="Password has been reset successfully. Please log in with your new credentials."
    )


@router.post("/logout")
async def logout(req_body: RefreshTokenRequest, request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    await auth_service.logout(req_body.refreshToken, current_user["id"], client_ip, user_agent)
    return ApiResponse.success(
        status_code=200,
        message="Logout successful"
    )


@router.post("/change-password")
async def change_password(req_body: ChangePasswordRequest, request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    await auth_service.change_password(
        current_user["id"], 
        req_body.oldPassword, 
        req_body.newPassword, 
        client_ip, 
        user_agent
    )
    return ApiResponse.success(
        status_code=200,
        message="Password changed successfully"
    )


@router.get("/profile")
async def get_profile(current_user: Dict[str, Any] = Depends(get_current_user)):
    profile = await auth_service.get_profile(current_user["id"])
    return ApiResponse.success(
        status_code=200,
        message="User profile retrieved successfully",
        data=profile
    )


@router.patch("/profile")
async def update_profile(req_body: UpdateProfileRequest, request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    # Filter only provided values (selective profile updates)
    updates = req_body.model_dump(exclude_unset=True)
    
    profile = await auth_service.update_profile(current_user["id"], updates, client_ip, user_agent)
    return ApiResponse.success(
        status_code=200,
        message="User profile updated successfully",
        data=profile
    )


@router.post("/deactivate")
async def deactivate(request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    await auth_service.deactivate_user(current_user["id"], client_ip, user_agent)
    return ApiResponse.success(
        status_code=200,
        message="Account deactivated successfully"
    )
