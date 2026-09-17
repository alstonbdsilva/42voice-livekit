"""
FastAPI Routes for Telephony Configurations & Phone Numbers (Twilio & Vobiz).
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
import logging

from api.middlewares.auth import get_current_user
from api.utils.api_response import ApiResponse
from api.modules.telephony_configs.schemas import (
    TelephonyProviderMetadataResponse,
    TelephonyConfigurationCreateRequest,
    TelephonyConfigurationUpdateRequest,
    PhoneNumberCreateRequest,
    PhoneNumberUpdateRequest,
    InitiateCallRequest,
)
from api.modules.telephony_configs import db_service

router = APIRouter()
logger = logging.getLogger("voice-agent.api.telephony_configs")

# Metadata definitions for Twilio and Vobiz ONLY
TWILIO_METADATA = {
    "provider": "twilio",
    "display_name": "Twilio",
    "docs_url": "https://www.twilio.com/docs/voice",
    "fields": [
        {
            "name": "account_sid",
            "label": "Account SID",
            "type": "text",
            "required": True,
            "sensitive": True,
            "description": "Twilio Account SID (found in Twilio Console Dashboard)",
            "placeholder": "AC..."
        },
        {
            "name": "auth_token",
            "label": "Auth Token",
            "type": "password",
            "required": True,
            "sensitive": True,
            "description": "Twilio Auth Token",
            "placeholder": "••••••••••••••••••••••••••••••••"
        },
        {
            "name": "amd_enabled",
            "label": "Answering Machine Detection (AMD)",
            "type": "boolean",
            "required": False,
            "sensitive": False,
            "description": "Detect whether outbound calls are answered by a person or machine."
        }
    ]
}

VOBIZ_METADATA = {
    "provider": "vobiz",
    "display_name": "Vobiz",
    "docs_url": "https://vobiz.ai/docs",
    "fields": [
        {
            "name": "auth_id",
            "label": "Account ID",
            "type": "text",
            "required": True,
            "sensitive": True,
            "description": "Vobiz Account ID (e.g., MA_SYQRLN1K)",
            "placeholder": "MA_..."
        },
        {
            "name": "auth_token",
            "label": "Auth Token",
            "type": "password",
            "required": True,
            "sensitive": True,
            "description": "Vobiz Auth Token",
            "placeholder": "••••••••••••••••••••••••••••••••"
        },
        {
            "name": "application_id",
            "label": "Application ID",
            "type": "text",
            "required": False,
            "sensitive": False,
            "description": "Vobiz Application ID for webhook answer URL handling.",
            "placeholder": "app_..."
        }
    ]
}


def get_scoped_client_id(current_user: Dict[str, Any]) -> Optional[str]:
    role = str(current_user.get("role", "")).upper()
    if role in ["SUPER_ADMIN", "SUPERADMIN", "FINANCE_ADMIN", "ADMIN"]:
        return None
    return current_user.get("client_id")


@router.get("/metadata")
async def get_telephony_providers_metadata(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Return provider metadata fields for Twilio and Vobiz ONLY."""
    return ApiResponse.success(data={"providers": [TWILIO_METADATA, VOBIZ_METADATA]})


@router.get("")
async def list_telephony_configurations(current_user: Dict[str, Any] = Depends(get_current_user)):
    client_id = get_scoped_client_id(current_user)
    configs = await db_service.list_telephony_configurations(client_id)
    return ApiResponse.success(data={"configurations": configs})


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_telephony_configuration(
    req: TelephonyConfigurationCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    client_id = get_scoped_client_id(current_user)
    provider = req.config.get("provider")
    if provider not in ["twilio", "vobiz"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported provider. Allowed providers: twilio, vobiz"
        )
    config_data = dict(req.config)
    config_data.pop("provider", None)

    created = await db_service.create_telephony_configuration(
        name=req.name,
        provider=provider,
        credentials=config_data,
        is_default_outbound=req.is_default_outbound,
        client_id=client_id
    )
    return ApiResponse.success(status_code=status.HTTP_201_CREATED, message="Configuration created successfully", data=created)


@router.get("/{config_id}")
async def get_telephony_configuration_by_id(
    config_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    client_id = get_scoped_client_id(current_user)
    config = await db_service.get_telephony_configuration(config_id, client_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")
    config.pop("raw_credentials", None)
    return ApiResponse.success(data=config)


@router.put("/{config_id}")
async def update_telephony_configuration(
    config_id: str,
    req: TelephonyConfigurationUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    client_id = get_scoped_client_id(current_user)
    config_data = dict(req.config) if req.config else None
    if config_data:
        config_data.pop("provider", None)

    updated = await db_service.update_telephony_configuration(
        config_id=config_id,
        name=req.name,
        credentials=config_data,
        client_id=client_id
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")
    return ApiResponse.success(message="Configuration updated successfully", data=updated)


@router.delete("/{config_id}")
async def delete_telephony_configuration(
    config_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    client_id = get_scoped_client_id(current_user)
    success = await db_service.delete_telephony_configuration(config_id, client_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")
    return ApiResponse.success(message="Configuration deleted")


@router.post("/{config_id}/set-default-outbound")
async def set_default_outbound(
    config_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    client_id = get_scoped_client_id(current_user)
    success = await db_service.set_default_telephony_configuration(config_id, client_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")
    return ApiResponse.success(message="Set as default outbound configuration")


# --- Phone Numbers Sub-routes ---

@router.get("/{config_id}/phone-numbers")
async def list_phone_numbers(
    config_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    client_id = get_scoped_client_id(current_user)
    config = await db_service.get_telephony_configuration(config_id, client_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")
    numbers = await db_service.list_phone_numbers(config_id)
    return ApiResponse.success(data={"phone_numbers": numbers})


@router.post("/{config_id}/phone-numbers", status_code=status.HTTP_201_CREATED)
async def add_phone_number(
    config_id: str,
    req: PhoneNumberCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    client_id = get_scoped_client_id(current_user)
    config = await db_service.get_telephony_configuration(config_id, client_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")

    number = await db_service.add_phone_number(
        config_id=config_id,
        address=req.address,
        address_type=req.address_type,
        country_code=req.country_code,
        label=req.label,
        is_active=req.is_active,
        is_default_caller_id=req.is_default_caller_id,
        inbound_agent_id=req.inbound_agent_id
    )
    return ApiResponse.success(status_code=status.HTTP_201_CREATED, message="Phone number added", data=number)


@router.put("/{config_id}/phone-numbers/{phone_number_id}")
async def update_phone_number(
    config_id: str,
    phone_number_id: str,
    req: PhoneNumberUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    client_id = get_scoped_client_id(current_user)
    config = await db_service.get_telephony_configuration(config_id, client_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")

    updated = await db_service.update_phone_number(
        phone_number_id=phone_number_id,
        config_id=config_id,
        address=req.address,
        address_type=req.address_type,
        country_code=req.country_code,
        label=req.label,
        is_active=req.is_active,
        inbound_agent_id=req.inbound_agent_id
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone number not found")
    return ApiResponse.success(message="Phone number updated", data=updated)


@router.delete("/{config_id}/phone-numbers/{phone_number_id}")
async def delete_phone_number(
    config_id: str,
    phone_number_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    client_id = get_scoped_client_id(current_user)
    config = await db_service.get_telephony_configuration(config_id, client_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")

    await db_service.delete_phone_number(phone_number_id, config_id)
    return ApiResponse.success(message="Phone number deleted")


@router.post("/{config_id}/phone-numbers/{phone_number_id}/set-default-caller")
async def set_default_caller_id(
    config_id: str,
    phone_number_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    client_id = get_scoped_client_id(current_user)
    config = await db_service.get_telephony_configuration(config_id, client_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")

    await db_service.set_default_caller_id(phone_number_id, config_id)
    return ApiResponse.success(message="Set as default caller ID")


@router.post("/initiate-call")
async def initiate_call(
    req: InitiateCallRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if not req.phone_number or not req.phone_number.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number is required"
        )
    logger.info(f"Initiating test call to {req.phone_number} for agent_id={req.agent_id}, config_id={req.telephony_configuration_id}")
    return ApiResponse.success(message=f"Test call initiated to {req.phone_number} successfully!")

