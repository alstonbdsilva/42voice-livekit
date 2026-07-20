"""
Audit Logs Routers.
Defines endpoints for superusers to retrieve platform audit trail logs.
"""

from fastapi import APIRouter, Depends, Request
from typing import Optional, Dict, Any, List

from api.utils.api_response import ApiResponse
from api.modules.audit.services import AuditService
from api.middlewares.auth import require_roles

router = APIRouter()
audit_service = AuditService()

# --- Route Endpoints ---
# Audit log endpoints require SUPER_ADMIN authority

@router.get("", dependencies=[Depends(require_roles(["SUPER_ADMIN"]))])
async def get_all():
    """Retrieve list of system audit logs."""
    logs = await audit_service.get_all_audit_logs()
    return ApiResponse.success(
        status_code=200,
        message="Audit logs retrieved successfully",
        data=logs
    )
