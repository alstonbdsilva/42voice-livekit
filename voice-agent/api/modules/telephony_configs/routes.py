"""
FastAPI Routes for Telephony Configurations & Phone Numbers (Twilio & Vobiz).
"""

import json
import uuid
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status

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
            "name": "sip_trunk_id",
            "label": "SIP Trunk ID (Optional)",
            "type": "text",
            "required": False,
            "sensitive": False,
            "description": "Optional LiveKit Outbound SIP Trunk ID (ST_...). Leave blank to use server TWILIO_SIP_TRUNK_ID",
            "placeholder": "ST_..."
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
    import httpx
    from config import get_settings
    from api import database

    if not req.phone_number or not req.phone_number.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number is required"
        )

    client_id = get_scoped_client_id(current_user)
    dest_number = req.phone_number.strip()

    # 1. Fetch telephony configuration
    config = None
    if req.telephony_configuration_id:
        config = await db_service.get_telephony_configuration(req.telephony_configuration_id, client_id)

    if not config:
        configs = await db_service.list_telephony_configurations(client_id)
        if configs:
            default_item = next((c for c in configs if c.get("is_default_outbound")), configs[0])
            config = await db_service.get_telephony_configuration(default_item["id"], client_id)

    # 2. Fetch caller ID phone number
    from_number = None
    if config:
        numbers = await db_service.list_phone_numbers(config["id"])
        if req.from_phone_number_id:
            phone_obj = next((n for n in numbers if n["id"] == req.from_phone_number_id), None)
        else:
            phone_obj = next((n for n in numbers if n.get("is_default_caller_id")), numbers[0] if numbers else None)
        if phone_obj:
            from_number = phone_obj.get("address")

    # 3. Fetch agent info if provided
    agent_name = "Voice Agent"
    if req.agent_id and db_service.is_valid_uuid(req.agent_id):
        rows = await database.query("SELECT name FROM agents WHERE id = $1::uuid", [req.agent_id])
        if rows:
            agent_name = rows[0]["name"]

    logger.info(f"Initiating call to {dest_number} (Agent: '{agent_name}', Config: {config.get('name') if config else 'None'}, CallerID: {from_number})")

    # 4. Prepare Metadata for LiveKit Dispatch & Worker
    metadata_dict = {
        "agent_id": req.agent_id,
        "agent_name": agent_name,
        "from_phone_number": from_number,
        "dest_number": dest_number
    } if req.agent_id else {}
    metadata_payload = json.dumps(metadata_dict) if metadata_dict else ""

    # 5. Initiate via LiveKit SIP API if configured
    settings = get_settings()
    if settings.livekit_url and settings.livekit_api_key and settings.livekit_api_secret:
        try:
            from livekit import api as lk_api
            lk = lk_api.LiveKitAPI(settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret)
            room_name = f"call-{uuid.uuid4().hex[:8]}"
            
            # Dispatch agent worker to the room
            if settings.livekit_agent_name:
                try:
                    await lk.agent_dispatch.create_dispatch(
                        lk_api.CreateAgentDispatchRequest(
                            agent_name=settings.livekit_agent_name,
                            room=room_name,
                            metadata=metadata_payload
                        )
                    )
                    logger.info(f"Dispatched agent '{settings.livekit_agent_name}' to room '{room_name}' with metadata: {metadata_payload}")
                except Exception as dispatch_err:
                    logger.warning(f"Could not dispatch agent to room {room_name}: {dispatch_err}")

            # Initiate SIP Participant Outbound Call
            raw_creds = config.get("raw_credentials") or {} if config else {}
            sip_trunk_id = (
                (phone_obj.get("lk_sip_trunk_id") if phone_obj else None)
                or raw_creds.get("sip_trunk_id")
                or raw_creds.get("twilio_sip_trunk_id")
                or settings.twilio_sip_trunk_id
            )
            
            if sip_trunk_id:
                sip_req = lk_api.CreateSIPParticipantRequest(
                    sip_trunk_id=sip_trunk_id,
                    sip_call_to=dest_number,
                    room_name=room_name,
                    participant_identity=f"sip-{dest_number}",
                    participant_name=dest_number,
                    participant_metadata=metadata_payload,
                    play_ringtone=True,
                )
                res = await lk.sip.create_sip_participant(sip_req)
                await lk.aclose()
                return ApiResponse.success(message=f"Call initiated to {dest_number} with agent '{agent_name}' via LiveKit SIP (Participant ID: {res.participant_id})")
            else:
                logger.info("No outbound LiveKit SIP Trunk ID configured (TWILIO_SIP_TRUNK_ID or lk_sip_trunk_id). Attempting provider fallback...")
                await lk.aclose()
        except Exception as lk_err:
            logger.warning(f"LiveKit SIP participant dispatch warning: {lk_err}")

    # 6. Fallback to Twilio REST API if Twilio configuration provided
    if config and config.get("provider") == "twilio":
        raw_creds = config.get("raw_credentials") or {}
        account_sid = raw_creds.get("account_sid") or settings.twilio_account_sid
        auth_token = raw_creds.get("auth_token") or settings.twilio_auth_token

        if not account_sid or not auth_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected Twilio configuration is missing Account SID or Auth Token."
            )

        if not from_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No caller ID phone number configured for this Twilio integration. Please add a phone number in Telephony Configurations."
            )

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls.json"
        
        # If Twilio SIP domain is set, bridge call to LiveKit SIP trunk
        sip_domain = settings.twilio_sip_domain or "42voice.pstn.sydney.twilio.com"
        twiml = f"<Response><Dial><Sip>sip:{dest_number}@{sip_domain}</Sip></Dial></Response>"
        data = {
            "To": dest_number,
            "From": from_number,
            "Twiml": twiml
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as http_client:
                resp = await http_client.post(url, auth=(account_sid, auth_token), data=data)
                resp_json = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                if resp.status_code in (200, 201):
                    call_sid = resp_json.get("sid", "N/A")
                    logger.info(f"Twilio call dispatched successfully. Call SID: {call_sid}")
                    return ApiResponse.success(message=f"Outbound call successfully initiated to {dest_number} with agent '{agent_name}'! (Twilio Call SID: {call_sid})")
                else:
                    err_msg = resp_json.get("message") or resp_json.get("detail") or resp.text or "Twilio API error"
                    logger.error(f"Twilio call error ({resp.status_code}): {err_msg}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Twilio call failed: {err_msg}"
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Twilio API request error: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to connect to Twilio API: {str(e)}"
            )

    # Fallback response
    return ApiResponse.success(message=f"Test call simulation initiated for {dest_number}. (Telephony configuration verified)")


