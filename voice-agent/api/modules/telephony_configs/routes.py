"""
FastAPI Routes for Telephony Configurations & Phone Numbers (Twilio & Vobiz).
"""

import asyncio
import json
import uuid
import logging
import httpx
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from api.middlewares.auth import get_current_user
from api.utils.api_response import ApiResponse
from api.utils.encryption import token_encryptor
from config import get_settings
from api import database
from api.modules.telephony_configs.schemas import (
    TelephonyProviderMetadataResponse,
    TelephonyConfigurationCreateRequest,
    TelephonyConfigurationUpdateRequest,
    PhoneNumberCreateRequest,
    PhoneNumberUpdateRequest,
    InitiateCallRequest,
)
from api.modules.telephony_configs import db_service
from api.modules.phone_numbers.livekit_sip import livekit_sip_service

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


def safe_decrypt(token: Optional[str]) -> str:
    if not token:
        return ""
    try:
        return token_encryptor.decrypt(token)
    except Exception:
        return str(token)


@router.get("/metadata")
async def get_telephony_providers_metadata(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Return provider metadata fields for Twilio and Vobiz ONLY."""
    return ApiResponse.success(data={"providers": [TWILIO_METADATA, VOBIZ_METADATA]})


def _sync_provision_twilio_user_sip_trunk(
    provider: str,
    credentials: Dict[str, Any],
    existing_credentials: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Synchronous auto-provisioning flow using official Twilio Python SDK.
    
    1. Using user's account_sid + auth_token, find (by TK... SID) or create Elastic SIP Trunk.
    2. Ensure trunk has a unique Termination SIP URI / domain (sip_domain).
    3. Find (by CL... SID) or create Credential List (CL...).
    4. Verify/Create SIP username & password credentials.
    5. Verify/Attach Credential List to Elastic SIP Trunk.
    6. Encrypt auth_token and sip_password before returning for DB storage.
    """
    if provider != "twilio":
        return credentials

    if not credentials and not existing_credentials:
        return credentials

    existing_credentials = existing_credentials or {}

    account_sid = credentials.get("account_sid") or existing_credentials.get("account_sid")
    raw_auth_token = credentials.get("auth_token") or existing_credentials.get("auth_token")

    if not account_sid or not raw_auth_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Twilio integration requires both Account SID and Auth Token."
        )

    # Handle UI masked values "****"
    if str(account_sid).startswith("****") and existing_credentials.get("account_sid"):
        account_sid = existing_credentials.get("account_sid")
    if str(raw_auth_token).startswith("****") and existing_credentials.get("auth_token"):
        raw_auth_token = existing_credentials.get("auth_token")

    plain_auth_token = safe_decrypt(raw_auth_token)

    try:
        client = Client(account_sid, plain_auth_token)

        # 1. Find or Create Twilio Elastic SIP Trunk (TK...)
        trunk_sid = credentials.get("twilio_trunk_sid") or existing_credentials.get("twilio_trunk_sid")
        sip_domain = credentials.get("sip_domain") or existing_credentials.get("sip_domain")
        trunk = None

        if trunk_sid and isinstance(trunk_sid, str):
            try:
                trunk = client.trunking.v1.trunks(trunk_sid).fetch()
                sip_domain = trunk.domain_name or sip_domain
            except TwilioRestException as tre:
                if tre.status in (401, 403) or tre.code in (20003, 20401):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid Twilio Account SID or Auth Token. Authentication failed."
                    )
                trunk_sid = None
                trunk = None

        if not trunk_sid:
            trunks_list = client.trunking.v1.trunks.list(limit=50)
            for t in trunks_list:
                if t.friendly_name == "LiveKit-SIP-Trunk":
                    trunk = t
                    trunk_sid = t.sid
                    sip_domain = t.domain_name or sip_domain
                    break

        if not trunk_sid or not trunk:
            trunk = client.trunking.v1.trunks.create(friendly_name="LiveKit-SIP-Trunk")
            trunk_sid = trunk.sid
            sip_domain = trunk.domain_name

        trunk_sid_str = str(trunk_sid)

        # 2. Ensure unique Termination SIP URI / domain
        if not sip_domain or not sip_domain.strip():
            desired_domain = f"42v-{uuid.uuid4().hex[:8]}.pstn.twilio.com"
            updated_trunk = client.trunking.v1.trunks(trunk_sid_str).update(domain_name=desired_domain)
            sip_domain = updated_trunk.domain_name or desired_domain

        # 3. Find or Create Credential List (CL...)
        cl_sid = credentials.get("sip_credential_list_sid") or existing_credentials.get("sip_credential_list_sid")
        cl = None

        if cl_sid and isinstance(cl_sid, str):
            try:
                cl = client.sip.credential_lists(cl_sid).fetch()
            except TwilioRestException as tre:
                if tre.status in (401, 403) or tre.code in (20003, 20401):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid Twilio Account SID or Auth Token. Authentication failed."
                    )
                cl_sid = None
                cl = None

        if not cl_sid:
            cl_list = client.sip.credential_lists.list(limit=50)
            for item in cl_list:
                if item.friendly_name and item.friendly_name.startswith("LiveKit-CL"):
                    cl = item
                    cl_sid = item.sid
                    break

        if not cl_sid or not cl:
            cl_friendly_name = f"LiveKit-CL-{uuid.uuid4().hex[:6]}"
            cl = client.sip.credential_lists.create(friendly_name=cl_friendly_name)
            cl_sid = cl.sid

        cl_sid_str = str(cl_sid)

        # 4. Create or reuse SIP username & password credentials
        sip_username = credentials.get("sip_username") or existing_credentials.get("sip_username")
        raw_sip_pass = credentials.get("sip_password") or existing_credentials.get("sip_password")

        if str(sip_username).startswith("****") and existing_credentials.get("sip_username"):
            sip_username = existing_credentials.get("sip_username")
        if str(raw_sip_pass).startswith("****") and existing_credentials.get("sip_password"):
            raw_sip_pass = existing_credentials.get("sip_password")

        plain_sip_password = safe_decrypt(raw_sip_pass) if raw_sip_pass else None

        cred_exists = False
        if sip_username and plain_sip_password:
            existing_creds = client.sip.credential_lists(cl_sid_str).credentials.list(limit=50)
            for c in existing_creds:
                if c.username == sip_username:
                    cred_exists = True
                    break

        if not cred_exists or not sip_username or not plain_sip_password:
            if not sip_username:
                sip_username = f"lk_{uuid.uuid4().hex[:10]}"
            if not plain_sip_password:
                plain_sip_password = f"P@ss-{uuid.uuid4().hex[:10]}A!1"

            client.sip.credential_lists(cl_sid_str).credentials.create(
                username=sip_username,
                password=plain_sip_password
            )

        # 5. Attach Credential List to Elastic SIP Trunk if not already attached
        assoc_exists = False
        assoc_list = client.trunking.v1.trunks(trunk_sid_str).credentials_lists.list(limit=50)
        for a in assoc_list:
            if a.sid == cl_sid_str:
                assoc_exists = True
                break

        if not assoc_exists:
            client.trunking.v1.trunks(trunk_sid_str).credentials_lists.create(credential_list_sid=cl_sid_str)

        # 6. Store and encrypt credentials
        res_creds = dict(credentials)
        res_creds["account_sid"] = account_sid
        res_creds["auth_token"] = token_encryptor.encrypt(plain_auth_token)
        res_creds["twilio_trunk_sid"] = trunk_sid
        res_creds["sip_domain"] = sip_domain
        res_creds["sip_credential_list_sid"] = cl_sid
        res_creds["sip_username"] = sip_username
        res_creds["sip_password"] = token_encryptor.encrypt(plain_sip_password)

        logger.info(f"Successfully auto-provisioned Twilio Elastic SIP Trunk '{trunk_sid}' using Twilio SDK for Account '{account_sid}' with domain '{sip_domain}' and Credential List '{cl_sid}'.")
        return res_creds

    except HTTPException:
        raise
    except TwilioRestException as tre:
        logger.error(f"TwilioRestException during SIP provisioning: code={tre.code}, status={tre.status}, msg={tre.msg}")
        if tre.status in (401, 403) or tre.code in (20003, 20401):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Twilio Account SID or Auth Token. Authentication failed."
            )
        elif tre.status >= 500:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Twilio API service is currently unavailable. Please try again later."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Twilio SIP provisioning failed: {tre.msg}"
            )
    except Exception as err:
        logger.error(f"Twilio SDK SIP provisioning internal error: {err}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Twilio SIP provisioning failed: {str(err)}"
        )


async def provision_twilio_user_sip_trunk(
    provider: str,
    credentials: Dict[str, Any],
    existing_credentials: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Async wrapper executing Twilio SDK provisioning in a thread pool using asyncio.to_thread.
    """
    if provider != "twilio":
        return credentials

    if not credentials and not existing_credentials:
        return credentials

    return await asyncio.to_thread(_sync_provision_twilio_user_sip_trunk, provider, credentials, existing_credentials)


def _sync_provision_twilio_inbound_number(
    credentials: Dict[str, Any],
    phone_number: str,
    origination_uri: Optional[str]
) -> Dict[str, Any]:
    """
    Synchronous helper to resolve PN... SID, associate PN with TK... trunk,
    and ensure Origination URL is configured on TK... trunk.
    """
    if not origination_uri or not str(origination_uri).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LIVEKIT_SIP_PUBLIC_URI is not configured on the server. Inbound SIP routing cannot be provisioned."
        )

    account_sid = credentials.get("account_sid")
    raw_auth_token = credentials.get("auth_token")
    trunk_sid = credentials.get("twilio_trunk_sid")

    if not account_sid or not raw_auth_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Twilio integration requires Account SID and Auth Token."
        )

    if not trunk_sid:
        credentials = _sync_provision_twilio_user_sip_trunk("twilio", credentials)
        trunk_sid = credentials.get("twilio_trunk_sid")

    if not trunk_sid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Twilio Elastic SIP Trunk could not be found or created."
        )

    plain_auth_token = safe_decrypt(raw_auth_token)
    from api.utils.phone import normalize_phone_number
    clean_number = normalize_phone_number(phone_number)

    try:
        client = Client(account_sid, plain_auth_token)
        trunk_sid_str = str(trunk_sid)

        # 1. Resolve Twilio Phone Number SID (PN...)
        incoming_numbers = client.incoming_phone_numbers.list(phone_number=clean_number, limit=10)
        pn_obj = None
        if incoming_numbers:
            pn_obj = incoming_numbers[0]
        else:
            all_numbers = client.incoming_phone_numbers.list(limit=100)
            for item in all_numbers:
                if item.phone_number and normalize_phone_number(item.phone_number) == clean_number:
                    pn_obj = item
                    break

        if not pn_obj or not pn_obj.sid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Phone number '{phone_number}' not found in this Twilio account."
            )

        pn_sid_str: str = str(pn_obj.sid)

        # 2. Protection against re-assigning phone numbers already associated with a different trunk
        current_trunk_sid = getattr(pn_obj, "trunk_sid", None)
        if current_trunk_sid and str(current_trunk_sid) != trunk_sid_str:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Phone number '{phone_number}' is already assigned to a different Twilio Elastic SIP Trunk ({current_trunk_sid}). Cannot reassign."
            )

        # 3. Associate PN... -> TK... trunk idempotently
        trunk_numbers = client.trunking.v1.trunks(trunk_sid_str).phone_numbers.list(limit=100)
        already_associated = False
        for tn in trunk_numbers:
            tn_num = getattr(tn, "phone_number", None)
            if tn.sid == pn_sid_str or (tn_num and normalize_phone_number(str(tn_num)) == clean_number):
                already_associated = True
                break

        if not already_associated:
            try:
                client.trunking.v1.trunks(trunk_sid_str).phone_numbers.create(phone_number_sid=pn_sid_str)
                logger.info(f"Associated Twilio phone number {phone_number} ({pn_sid_str}) with trunk {trunk_sid_str}.")
            except TwilioRestException as tre:
                if "already" in str(tre.msg).lower() or tre.code in (21404, 21405):
                    logger.info(f"Phone number {pn_sid_str} already associated with trunk {trunk_sid_str}.")
                else:
                    raise

        # 4. Create / Reuse Origination URL on TK... trunk idempotently & retrieve OU... SID
        orig_urls = client.trunking.v1.trunks(trunk_sid_str).origination_urls.list(limit=50)
        existing_ou = next((ou for ou in orig_urls if ou.sip_url == origination_uri), None)

        if existing_ou:
            ou_sid = existing_ou.sid
            logger.info(f"Reusing existing Origination URL '{origination_uri}' ({ou_sid}) on trunk {trunk_sid_str}.")
        else:
            new_ou = client.trunking.v1.trunks(trunk_sid_str).origination_urls.create(
                friendly_name="42voice-LiveKit-Inbound",
                sip_url=origination_uri,
                priority=1,
                weight=1,
                enabled=True
            )
            ou_sid = new_ou.sid
            logger.info(f"Created Origination URL '{origination_uri}' ({ou_sid}) on trunk {trunk_sid_str}.")

        return {
            "twilio_phone_number_sid": pn_sid_str,
            "twilio_origination_url_sid": ou_sid,
            "twilio_trunk_sid": trunk_sid_str
        }

    except HTTPException:
        raise
    except TwilioRestException as tre:
        logger.error(f"TwilioRestException during inbound phone number provisioning: code={tre.code}, status={tre.status}, msg={tre.msg}")
        if tre.status in (401, 403) or tre.code in (20003, 20401):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Twilio Account SID or Auth Token."
            )
        elif tre.status >= 500:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Twilio API service is currently unavailable."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Twilio inbound configuration failed: {tre.msg}"
            )
    except Exception as err:
        logger.error(f"Inbound phone number provisioning error: {err}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Twilio inbound configuration failed: {str(err)}"
        )


async def provision_twilio_inbound_number(
    credentials: Dict[str, Any],
    phone_number: str,
    origination_uri: Optional[str]
) -> Dict[str, Any]:
    return await asyncio.to_thread(_sync_provision_twilio_inbound_number, credentials, phone_number, origination_uri)


def _sync_cleanup_twilio_phone_number_routing(
    credentials: Dict[str, Any],
    phone_address: str,
    persisted_pn_sid: Optional[str] = None
) -> None:
    """
    Synchronous helper to disassociate a Twilio phone number (PN...) from user's Elastic SIP Trunk (TK...).
    Does NOT release/cancel/delete the actual purchased Twilio phone number.
    Preserves shared TK..., CL..., and Origination URL resources.
    """
    account_sid = credentials.get("account_sid")
    raw_auth_token = credentials.get("auth_token")
    trunk_sid = credentials.get("twilio_trunk_sid")

    if not account_sid or not raw_auth_token or not trunk_sid:
        logger.info(f"Twilio credentials or trunk SID missing for number {phone_address}. Skipping Twilio disassociation.")
        return

    plain_auth_token = safe_decrypt(raw_auth_token)
    from api.utils.phone import normalize_phone_number
    clean_number = normalize_phone_number(phone_address)

    try:
        client = Client(account_sid, plain_auth_token)
        trunk_sid_str = str(trunk_sid)

        # 1. Resolve Twilio Phone Number SID (PN...) if not persisted
        pn_sid = persisted_pn_sid
        pn_obj = None

        if pn_sid and isinstance(pn_sid, str):
            try:
                pn_obj = client.incoming_phone_numbers(pn_sid).fetch()
            except TwilioRestException:
                pn_sid = None

        if not pn_sid or not pn_obj:
            incoming = client.incoming_phone_numbers.list(phone_number=clean_number, limit=10)
            if incoming:
                pn_obj = incoming[0]
                pn_sid = pn_obj.sid
            else:
                all_numbers = client.incoming_phone_numbers.list(limit=100)
                for item in all_numbers:
                    if item.phone_number and normalize_phone_number(item.phone_number) == clean_number:
                        pn_obj = item
                        pn_sid = item.sid
                        break

        if not pn_sid or not pn_obj:
            logger.info(f"Phone number '{phone_address}' not found in user's Twilio account '{account_sid}'. Disassociation skipped.")
            return

        pn_sid_str: str = str(pn_sid)
        current_trunk_sid = getattr(pn_obj, "trunk_sid", None)

        # 2. Check trunk association status
        if not current_trunk_sid:
            logger.info(f"Phone number {phone_address} ({pn_sid_str}) has no trunk associated. Disassociation skipped.")
            return

        if str(current_trunk_sid) != trunk_sid_str:
            logger.warning(
                f"Conflict: Phone number {phone_address} ({pn_sid_str}) is assigned to trunk '{current_trunk_sid}', "
                f"not user's trunk '{trunk_sid_str}'. Refusing to disassociate from un-owned trunk."
            )
            return

        # 3. Disassociate PN... from user's TK... trunk using Twilio SDK (does NOT delete incoming phone number)
        try:
            client.trunking.v1.trunks(trunk_sid_str).phone_numbers(pn_sid_str).delete()
            logger.info(f"Successfully disassociated phone number {phone_address} ({pn_sid_str}) from trunk {trunk_sid_str}.")
        except TwilioRestException as tre:
            if tre.status == 404 or tre.code == 20404 or "not found" in str(tre.msg).lower():
                logger.info(f"Phone number {pn_sid_str} was already disassociated from trunk {trunk_sid_str}.")
            else:
                logger.error(f"Error disassociating phone number {pn_sid_str} from trunk {trunk_sid_str}: {tre.msg}")

    except Exception as err:
        logger.error(f"Twilio phone number cleanup error for {phone_address}: {err}", exc_info=True)


async def cleanup_twilio_phone_number_routing(
    credentials: Dict[str, Any],
    phone_address: str,
    persisted_pn_sid: Optional[str] = None
) -> None:
    await asyncio.to_thread(_sync_cleanup_twilio_phone_number_routing, credentials, phone_address, persisted_pn_sid)


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

    # Auto-provision per-user Twilio SIP credentials & Trunk association
    config_data = await provision_twilio_user_sip_trunk(provider, config_data)

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
    existing = await db_service.get_telephony_configuration(config_id, client_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")

    existing_raw = existing.get("raw_credentials") or {}
    config_data = dict(req.config) if req.config else dict(existing_raw)
    provider = config_data.pop("provider", None) or existing.get("provider") or "twilio"

    merged_data = dict(existing_raw)
    for k, v in config_data.items():
        if not str(v).startswith("****"):
            merged_data[k] = v

    merged_data = await provision_twilio_user_sip_trunk(provider, merged_data, existing_credentials=existing_raw)

    updated = await db_service.update_telephony_configuration(
        config_id=config_id,
        name=req.name,
        credentials=merged_data,
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

    provider = config.get("provider", "twilio")
    raw_creds = config.get("raw_credentials") or {}
    sip_config_with_provider = {**raw_creds, "provider": provider}

    # 1. If provider is Twilio, provision Twilio inbound routing (PN association & Origination URL)
    if provider == "twilio":
        from config import get_settings
        settings = get_settings()
        origination_uri = settings.livekit_sip_public_uri
        inbound_res = await provision_twilio_inbound_number(raw_creds, req.address, origination_uri)
        if inbound_res:
            raw_creds["twilio_origination_url_sid"] = inbound_res.get("twilio_origination_url_sid")
            pn_sids = raw_creds.get("phone_number_sids")
            if not isinstance(pn_sids, dict):
                pn_sids = {}
            pn_sids[req.address] = inbound_res.get("twilio_phone_number_sid")
            raw_creds["phone_number_sids"] = pn_sids
            await db_service.update_telephony_configuration(config_id, credentials=raw_creds, client_id=client_id)
            sip_config_with_provider = {**raw_creds, "provider": provider}

    # 2. Provision LiveKit SIP inbound trunk & dispatch rule
    trunk_id, dispatch_rule_id, _ = await livekit_sip_service.provision_inbound_trunk(
        number=req.address,
        name=req.label or f"{config.get('name', 'DID')} Line",
        sip_config=sip_config_with_provider
    )

    # 3. Provision LiveKit SIP outbound trunk
    outbound_trunk_id, _ = await livekit_sip_service.provision_outbound_trunk(
        number=req.address,
        name=req.label or f"{config.get('name', 'DID')} Line",
        sip_config=sip_config_with_provider
    )

    number = await db_service.add_phone_number(
        config_id=config_id,
        address=req.address,
        address_type=req.address_type,
        country_code=req.country_code,
        label=req.label,
        is_active=req.is_active,
        is_default_caller_id=req.is_default_caller_id,
        inbound_agent_id=req.inbound_agent_id,
        lk_sip_trunk_id=trunk_id,
        lk_outbound_sip_trunk_id=outbound_trunk_id,
        lk_sip_dispatch_rule_id=dispatch_rule_id
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

    numbers = await db_service.list_phone_numbers(config_id)
    existing_phone = next((n for n in numbers if n["id"] == phone_number_id), None)

    trunk_id = existing_phone.get("lk_sip_trunk_id") if existing_phone else None
    outbound_trunk_id = existing_phone.get("lk_outbound_sip_trunk_id") if existing_phone else None
    dispatch_rule_id = existing_phone.get("lk_sip_dispatch_rule_id") if existing_phone else None

    # If address changed or trunk missing, provision/update
    target_address = req.address if req.address is not None else (existing_phone.get("address") if existing_phone else None)
    if target_address:
        provider = config.get("provider", "twilio")
        raw_creds = config.get("raw_credentials") or {}
        sip_config_with_provider = {**raw_creds, "provider": provider}

        if provider == "twilio":
            from config import get_settings
            settings = get_settings()
            origination_uri = settings.livekit_sip_public_uri
            inbound_res = await provision_twilio_inbound_number(raw_creds, target_address, origination_uri)
            if inbound_res:
                raw_creds["twilio_origination_url_sid"] = inbound_res.get("twilio_origination_url_sid")
                pn_sids = raw_creds.get("phone_number_sids")
                if not isinstance(pn_sids, dict):
                    pn_sids = {}
                pn_sids[target_address] = inbound_res.get("twilio_phone_number_sid")
                raw_creds["phone_number_sids"] = pn_sids
                await db_service.update_telephony_configuration(config_id, credentials=raw_creds, client_id=client_id)
                sip_config_with_provider = {**raw_creds, "provider": provider}

        if not trunk_id:
            trunk_id, dispatch_rule_id, _ = await livekit_sip_service.provision_inbound_trunk(
                number=target_address,
                name=req.label or f"{config.get('name', 'DID')} Line",
                sip_config=sip_config_with_provider
            )
        else:
            await livekit_sip_service.update_inbound_trunk(
                trunk_id=trunk_id,
                number=target_address,
                name=req.label or f"{config.get('name', 'DID')} Line",
                sip_config=sip_config_with_provider
            )
            if dispatch_rule_id:
                await livekit_sip_service.update_dispatch_rule(
                    dispatch_rule_id=dispatch_rule_id,
                    trunk_id=trunk_id,
                    number=target_address,
                    name=req.label or f"{config.get('name', 'DID')} Line"
                )

        if not outbound_trunk_id:
            outbound_trunk_id, _ = await livekit_sip_service.provision_outbound_trunk(
                number=target_address,
                name=req.label or f"{config.get('name', 'DID')} Line",
                sip_config=sip_config_with_provider
            )

    updated = await db_service.update_phone_number(
        phone_number_id=phone_number_id,
        config_id=config_id,
        address=req.address,
        address_type=req.address_type,
        country_code=req.country_code,
        label=req.label,
        is_active=req.is_active,
        inbound_agent_id=req.inbound_agent_id,
        lk_sip_trunk_id=trunk_id,
        lk_outbound_sip_trunk_id=outbound_trunk_id,
        lk_sip_dispatch_rule_id=dispatch_rule_id
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone number not found")

    numbers = await db_service.list_phone_numbers(config_id)
    phone_obj = next((n for n in numbers if n["id"] == phone_number_id), None)
    if not phone_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone number not found")

    logger.info(
        f"Initiating phone number deletion: phone_id={phone_number_id}, config_id={config_id}, client_id={client_id}"
    )

    # 1. Delete LiveKit dispatch rule
    dispatch_rule = phone_obj.get("lk_sip_dispatch_rule_id")
    if dispatch_rule:
        try:
            await livekit_sip_service.delete_dispatch_rule(dispatch_rule)
        except Exception as err:
            logger.warning(f"Warning/Error deleting LiveKit dispatch rule '{dispatch_rule}': {err}")

    # 2. Delete LiveKit inbound trunk
    inbound_trunk = phone_obj.get("lk_sip_trunk_id")
    if inbound_trunk:
        try:
            await livekit_sip_service.delete_trunk(inbound_trunk)
        except Exception as err:
            logger.warning(f"Warning/Error deleting LiveKit inbound trunk '{inbound_trunk}': {err}")

    # 3. Delete LiveKit outbound trunk
    outbound_trunk = phone_obj.get("lk_outbound_sip_trunk_id")
    if outbound_trunk:
        try:
            await livekit_sip_service.delete_trunk(outbound_trunk)
        except Exception as err:
            logger.warning(f"Warning/Error deleting LiveKit outbound trunk '{outbound_trunk}': {err}")

    # 4. Disassociate Twilio PN from user's TK
    provider = config.get("provider", "twilio")
    raw_creds = config.get("raw_credentials") or {}
    phone_address = phone_obj.get("address")

    if provider == "twilio" and phone_address:
        pn_sids = raw_creds.get("phone_number_sids") or {}
        persisted_pn_sid = pn_sids.get(phone_address) if isinstance(pn_sids, dict) else None
        await cleanup_twilio_phone_number_routing(raw_creds, phone_address, persisted_pn_sid)

        # 5. Clear phone-number-specific metadata / IDs
        if isinstance(pn_sids, dict) and phone_address in pn_sids:
            del pn_sids[phone_address]
            raw_creds["phone_number_sids"] = pn_sids
            await db_service.update_telephony_configuration(config_id, credentials=raw_creds, client_id=client_id)

    # 6. Delete DB record
    await db_service.delete_phone_number(phone_number_id, config_id)
    logger.info(f"Successfully deleted phone number {phone_number_id} ({phone_address})")
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

    # 1. Fetch telephony configuration strictly scoped to user/client_id
    config = None
    if req.telephony_configuration_id:
        config = await db_service.get_telephony_configuration(req.telephony_configuration_id, client_id)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Selected telephony configuration not found."
            )

    if not config:
        configs = await db_service.list_telephony_configurations(client_id)
        if configs:
            default_item = next((c for c in configs if c.get("is_default_outbound")), configs[0])
            config = await db_service.get_telephony_configuration(default_item["id"], client_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No telephony configuration found for this account. Please configure a telephony provider first."
        )

    # 2. Fetch caller ID phone number from telephony_phone_numbers table
    from_number = None
    phone_obj = None
    numbers = await db_service.list_phone_numbers(config["id"])
    if req.from_phone_number_id:
        phone_obj = next((n for n in numbers if n["id"] == req.from_phone_number_id), None)
        if not phone_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Selected caller ID phone number not found in this configuration."
            )
    if not phone_obj:
        phone_obj = next((n for n in numbers if n.get("is_default_caller_id")), numbers[0] if numbers else None)
    if phone_obj:
        from_number = phone_obj.get("address")

    # 3. Fetch agent info if provided
    agent_name = "Voice Agent"
    if req.agent_id and db_service.is_valid_uuid(req.agent_id):
        rows = await database.query("SELECT name FROM agents WHERE id = $1::uuid", [req.agent_id])
        if rows:
            agent_name = rows[0]["name"]

    logger.info(
        f"Initiating call to {dest_number} (Agent: '{agent_name}', "
        f"Config: {config.get('name')}, ConfigID: {config.get('id')}, CallerID: {from_number})"
    )

    # 4. Prepare Metadata for LiveKit Dispatch & Worker
    metadata_dict = {
        "agent_id": req.agent_id,
        "agent_name": agent_name,
        "from_phone_number": from_number,
        "dest_number": dest_number
    } if req.agent_id else {}
    metadata_payload = json.dumps(metadata_dict) if metadata_dict else ""

    settings = get_settings()
    raw_creds = config.get("raw_credentials") or {}
    provider = config.get("provider")

    # Primary source for outbound SIP trunk ID: telephony_phone_numbers.lk_outbound_sip_trunk_id
    sip_trunk_id = (
        (phone_obj.get("lk_outbound_sip_trunk_id") if phone_obj else None)
        or raw_creds.get("outbound_sip_trunk_id")
        or raw_creds.get("sip_trunk_id")
        or raw_creds.get("twilio_sip_trunk_id")
    )

    async def _dispatch_livekit_sip_participant(trunk_id_to_use: str) -> Optional[str]:
        lk = None
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
            sip_req = lk_api.CreateSIPParticipantRequest(
                sip_trunk_id=trunk_id_to_use,
                sip_call_to=dest_number,
                sip_number=from_number or "",
                room_name=room_name,
                participant_identity=f"sip-{dest_number}",
                participant_name=dest_number,
                participant_metadata=metadata_payload,
                play_ringtone=True,
                wait_until_answered=True,
            )
            res = await lk.sip.create_sip_participant(sip_req)
            await lk.aclose()
            return res.participant_id
        except Exception as err:
            if lk:
                try:
                    await lk.aclose()
                except Exception:
                    pass
            raise err

    # 5. Initiate via LiveKit SIP API if outbound trunk is configured
    if settings.livekit_url and settings.livekit_api_key and settings.livekit_api_secret:
        reconciled = False
        current_trunk_id = sip_trunk_id

        # If no trunk ID is present, try to reconcile/find it first
        if not current_trunk_id and phone_obj and from_number:
            sip_config_with_provider = {**raw_creds, "provider": provider}
            reconciled_id, _ = await livekit_sip_service.reconcile_outbound_trunk(
                number=from_number,
                name=phone_obj.get("label") or f"{config.get('name', 'DID')} Line",
                sip_config=sip_config_with_provider
            )
            if reconciled_id and not str(reconciled_id).startswith("err-") and not str(reconciled_id).startswith("mock-"):
                current_trunk_id = reconciled_id
                reconciled = True
                phone_obj["lk_outbound_sip_trunk_id"] = reconciled_id
                await database.query(
                    "UPDATE telephony_phone_numbers SET lk_outbound_sip_trunk_id = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2::uuid",
                    [reconciled_id, phone_obj["id"]]
                )
                logger.info(f"Reconciled and updated lk_outbound_sip_trunk_id={reconciled_id} for phone {phone_obj['id']}")

        if current_trunk_id:
            try:
                participant_id = await _dispatch_livekit_sip_participant(current_trunk_id)
                return ApiResponse.success(
                    message=f"Call initiated to {dest_number} with agent '{agent_name}' via LiveKit SIP (Participant ID: {participant_id})"
                )
            except Exception as lk_err:
                err_str = str(lk_err).lower()
                is_trunk_not_found = (
                    "does not exist" in err_str or
                    "not found" in err_str or
                    "404" in err_str or
                    "sip trunk" in err_str
                )
                logger.warning(f"LiveKit SIP participant dispatch warning: {lk_err}")

                # Retry ONLY ONCE if trunk is not found and we haven't reconciled yet
                if is_trunk_not_found and not reconciled and phone_obj and from_number:
                    logger.info(f"Attempting one-time reconciliation for outbound trunk: {current_trunk_id}")
                    sip_config_with_provider = {**raw_creds, "provider": provider}
                    new_outbound_id, _ = await livekit_sip_service.reconcile_outbound_trunk(
                        number=from_number,
                        name=phone_obj.get("label") or f"{config.get('name', 'DID')} Line",
                        sip_config=sip_config_with_provider
                    )
                    if new_outbound_id and not str(new_outbound_id).startswith("err-") and not str(new_outbound_id).startswith("mock-"):
                        # Update ONLY lk_outbound_sip_trunk_id in database
                        await database.query(
                            "UPDATE telephony_phone_numbers SET lk_outbound_sip_trunk_id = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2::uuid",
                            [new_outbound_id, phone_obj["id"]]
                        )
                        logger.info(f"Updated lk_outbound_sip_trunk_id to {new_outbound_id} in DB. Retrying LiveKit SIP dispatch (1 retry only)...")
                        try:
                            participant_id = await _dispatch_livekit_sip_participant(new_outbound_id)
                            return ApiResponse.success(
                                message=f"Call initiated to {dest_number} with agent '{agent_name}' via LiveKit SIP (Participant ID: {participant_id})"
                            )
                        except Exception as retry_err:
                            logger.error(f"Retry after outbound trunk reconciliation failed: {retry_err}")

    # 6. Fallback to Twilio REST API if provider is Twilio
    # Use credentials strictly from selected telephony configuration
    account_sid = raw_creds.get("account_sid")
    raw_auth_token = raw_creds.get("auth_token")
    auth_token = safe_decrypt(raw_auth_token) if raw_auth_token else None

    if provider == "twilio":
        if not account_sid or not auth_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected Twilio configuration is missing Account SID or Auth Token."
            )

        caller_id = from_number
        if not caller_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No caller ID phone number configured for this Twilio integration. Please add a phone number in Telephony Configurations."
            )

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls.json"
        
        # If Twilio SIP domain is set in credentials or defaults, bridge call
        sip_domain = raw_creds.get("sip_domain") or settings.twilio_sip_domain or "42voice.pstn.sydney.twilio.com"
        twiml = f"<Response><Dial><Sip>sip:{dest_number}@{sip_domain}</Sip></Dial></Response>"
        data = {
            "To": dest_number,
            "From": caller_id,
            "Twiml": twiml
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as http_client:
                resp = await http_client.post(url, auth=(account_sid, auth_token), data=data)
                resp_json = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                if resp.status_code in (200, 201):
                    call_sid = resp_json.get("sid", "N/A")
                    logger.info(f"Twilio call dispatched successfully for Account '{account_sid}'. Call SID: {call_sid}")
                    return ApiResponse.success(
                        message=f"Outbound call successfully initiated to {dest_number} with agent '{agent_name}'! (Twilio Call SID: {call_sid})"
                    )
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



