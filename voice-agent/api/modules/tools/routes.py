"""
Tools Router.
Defines endpoints for managing reusable agent tools (HTTP API, End Call,
Transfer Call, Calculator, MCP), plus test-execution and MCP catalog refresh.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.middlewares.auth import get_current_user
from api.modules.tools.services import ToolService
from api.utils.api_response import ApiResponse

router = APIRouter()
tool_service = ToolService()


# --- Request Models ---

class CreateToolRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: str = Field(default="http_api")
    icon: Optional[str] = "globe"
    icon_color: Optional[str] = "#3B82F6"
    definition: Dict[str, Any] = Field(default_factory=dict)


class UpdateToolRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    icon_color: Optional[str] = None
    definition: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class ToolTestRequest(BaseModel):
    llm_params: Dict[str, Any] = Field(default_factory=dict)
    preset_params: Dict[str, Any] = Field(default_factory=dict)


def _filter_context(current_user: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "role": current_user["role"],
        "userId": current_user["id"],
        "clientId": current_user.get("client_id"),
    }


# --- Route Endpoints ---

@router.get("")
async def list_tools(
    status: Optional[str] = None,
    category: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    if status:
        ToolService.validate_status(status)
    if category:
        ToolService.validate_category(category)

    filter_data = {**_filter_context(current_user), "status": status, "category": category}
    tools = await tool_service.list_tools(filter_data)
    return ApiResponse.success(message="Tools retrieved successfully", data=tools)


@router.post("")
async def create_tool(
    request: CreateToolRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    tool = await tool_service.create_tool(request.dict(), current_user)
    return ApiResponse.success(status_code=201, message="Tool created successfully", data=tool)


@router.get("/{tool_uuid}")
async def get_tool(
    tool_uuid: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    tool = await tool_service.get_tool(tool_uuid, _filter_context(current_user))
    return ApiResponse.success(message="Tool retrieved successfully", data=tool)


@router.put("/{tool_uuid}")
async def update_tool(
    tool_uuid: str,
    request: UpdateToolRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    tool = await tool_service.update_tool(
        tool_uuid, request.dict(exclude_unset=True), _filter_context(current_user)
    )
    return ApiResponse.success(message="Tool updated successfully", data=tool)


@router.delete("/{tool_uuid}")
async def delete_tool(
    tool_uuid: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    tool = await tool_service.archive_tool(tool_uuid, _filter_context(current_user))
    return ApiResponse.success(message="Tool archived successfully", data=tool)


@router.post("/{tool_uuid}/unarchive")
async def unarchive_tool(
    tool_uuid: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    tool = await tool_service.unarchive_tool(tool_uuid, _filter_context(current_user))
    return ApiResponse.success(message="Tool unarchived successfully", data=tool)


@router.post("/{tool_uuid}/test")
async def test_tool(
    tool_uuid: str,
    request: ToolTestRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    result = await tool_service.test_http_tool(
        tool_uuid, request.llm_params, request.preset_params, _filter_context(current_user)
    )
    return ApiResponse.success(message="Tool test executed", data=result)


@router.post("/{tool_uuid}/mcp/refresh")
async def refresh_mcp_tools(
    tool_uuid: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    result = await tool_service.refresh_mcp_tool(tool_uuid, _filter_context(current_user))
    return ApiResponse.success(message="MCP tools refreshed", data=result)
