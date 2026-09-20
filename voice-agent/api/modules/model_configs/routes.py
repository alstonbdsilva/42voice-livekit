"""
Model Configurations API Router.
"""
from typing import Any, Dict
from fastapi import APIRouter, Depends
from api.middlewares.auth import get_current_user
from api.modules.model_configs.schemas import (
    CreateModelConfigRequest,
    UpdateModelConfigRequest,
)
from api.modules.model_configs.services import ModelConfigService
from api.utils.api_response import ApiResponse

router = APIRouter()
service = ModelConfigService()


@router.get("")
async def list_model_configs(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    client_id = current_user.get("client_id")
    if not client_id:
        return ApiResponse.success(message="No model configurations for non-client context", data=[])

    configs = await service.list_model_configs(str(client_id))
    return ApiResponse.success(message="Model configurations retrieved successfully", data=configs)


@router.post("")
async def create_model_config(
    request: CreateModelConfigRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    config = await service.create_model_config(request.model_dump(), current_user)
    return ApiResponse.success(status_code=201, message="Model configuration created successfully", data=config)


@router.get("/{config_id}")
async def get_model_config(
    config_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    client_id = current_user.get("client_id")
    if not client_id:
        return ApiResponse.error(status_code=400, message="Client context required", code="CLIENT_REQUIRED")

    config = await service.get_model_config(config_id, str(client_id))
    return ApiResponse.success(message="Model configuration retrieved successfully", data=config)


@router.put("/{config_id}")
async def update_model_config(
    config_id: str,
    request: UpdateModelConfigRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    config = await service.update_model_config(config_id, request.model_dump(exclude_unset=True), current_user)
    return ApiResponse.success(message="Model configuration updated successfully", data=config)


@router.delete("/{config_id}")
async def delete_model_config(
    config_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    res = await service.delete_model_config(config_id, current_user)
    return ApiResponse.success(message="Model configuration deactivated successfully", data=res)
