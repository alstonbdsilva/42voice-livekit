import os
import uuid
import logging
import json
import asyncio
import httpx
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel, Field

from api import database
from api.utils.phone import normalize_phone_number, get_phone_number_variants
from api.utils.api_response import ApiResponse
from config import get_settings
from api.middlewares.auth import get_current_user, require_roles
from api.modules.phone_numbers.livekit_sip import livekit_sip_service
from api.modules.phone_numbers.sync_service import phone_sync_service

router = APIRouter()
logger = logging.getLogger("voice-agent.api.phone_numbers")

# --- Request Models ---

class CapabilitiesDto(BaseModel):
    voice: bool = True
    sms: bool = True

class RegisterPhoneNumberRequest(BaseModel):
    number: str = Field(..., min_length=1)
    name: Optional[str] = ""
    provider: str = Field(..., pattern="^(Twilio|CITL)$")
    monthlyCost: float = 0.00
    setupCost: float = 0.00
    capabilities: CapabilitiesDto
    sipConfig: Optional[Dict[str, Any]] = None
    allocation: str = Field("pool", pattern="^(pool|me|client|reseller)$")
    assignedId: Optional[str] = None
    draft: bool = False

class LeasePhoneNumberRequest(BaseModel):
    name: Optional[str] = ""
    agentId: Optional[str] = None

class AssignAgentRequest(BaseModel):
    agentId: Optional[str] = None

class EditPhoneNumberRequest(BaseModel):
    name: Optional[str] = None
    monthlyCost: Optional[float] = None
    setupCost: Optional[float] = None
    sipConfig: Optional[Dict[str, Any]] = None


# --- Endpoints ---

@router.get("")
async def get_all_numbers(
    status: Optional[str] = None, 
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get registered phone numbers.
    Filters:
    - Superadmin: sees all numbers.
    - Reseller: sees their leased numbers + available numbers.
    - Client: sees their leased numbers.
    - status query parameter filters by status.
    """
    role = current_user.get("role")
    user_id = current_user.get("id")
    client_id = current_user.get("client_id")
    reseller_id = current_user.get("reseller_id")
    
    query_str = "SELECT * FROM phone_numbers WHERE status != 'deleted'"
    params: List[Any] = []
    
    # Apply role scoping
    if role in ["SUPER_ADMIN", "FINANCE_ADMIN"]:
        pass  # sees all
    elif role == "RESELLER":
        if reseller_id:
            query_str += " AND (reseller_id = $1 OR status = 'available')"
            params.append(uuid.UUID(str(reseller_id)))
        else:
            query_str += " AND status = 'available'"
    elif role == "CLIENT":
        if client_id:
            query_str += " AND (client_id = $1 OR status = 'available')"
            params.append(uuid.UUID(str(client_id)))
        else:
            query_str += " AND status = 'available'"
    else:
        query_str += " AND 1=0"
        
    # Apply status filter
    if status:
        if params:
            query_str += f" AND status = ${len(params) + 1}"
        else:
            query_str += " AND status = $1"
        params.append(status)
        
    query_str += " ORDER BY created_at DESC"
    
    try:
        rows = await database.query(query_str, params)
        
        # Format columns for JSON responses
        formatted = []
        for r in rows:
            formatted.append({
                "id": str(r["id"]),
                "number": r["number"],
                "name": r["name"],
                "provider": r["provider"],
                "monthlyCost": f"${r['monthly_cost']:.2f}",
                "setupCost": f"${r['setup_cost']:.2f}",
                "status": r["status"],
                "capabilities": json.loads(r["capabilities"]) if isinstance(r["capabilities"], str) else r["capabilities"],
                "clientId": str(r["client_id"]) if r["client_id"] else None,
                "resellerId": str(r["reseller_id"]) if r["reseller_id"] else None,
                "agentId": str(r["agent_id"]) if r["agent_id"] else "",
                "sipConfig": json.loads(r["sip_config"]) if isinstance(r["sip_config"], str) else r["sip_config"],
                "lkSipTrunkId": r["lk_sip_trunk_id"],
                "lkSipDispatchRuleId": r["lk_sip_dispatch_rule_id"],
                "createdAt": r["created_at"].isoformat() if r["created_at"] else None
            })
            
        return ApiResponse.success(data=formatted)
    except Exception as e:
        logger.error(f"Failed to fetch phone numbers: {e}")
        return ApiResponse.error(500, f"Failed to retrieve phone numbers: {e}", "FETCH_NUMBERS_FAILED")


@router.get("/available")
async def get_available_twilio_numbers(
    country: str = "US",
    type: str = "Local",
    areaCode: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Query available Twilio phone numbers dynamically using backend Twilio credentials.
    Fetches real-time pricing dynamically from Twilio Pricing API.
    """
    settings = get_settings()
    account_sid = os.getenv("TWILIO_ACCOUNT_SID") or settings.twilio_account_sid
    auth_token = os.getenv("TWILIO_AUTH_TOKEN") or settings.twilio_auth_token

    country_code = country.upper()
    type_clean = type.lower()
    if type_clean in ["tollfree", "toll_free", "toll-free"]:
        number_type = "TollFree"
    elif type_clean == "mobile":
        number_type = "Mobile"
    else:
        number_type = "Local"

    if account_sid and auth_token:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                params = {"PageSize": 30, "VoiceEnabled": "true", "SmsEnabled": "true"}
                if areaCode and areaCode.strip():
                    params["AreaCode"] = areaCode.strip()

                url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/AvailablePhoneNumbers/{country_code}/{number_type}.json"
                pricing_url = f"https://pricing.twilio.com/v1/PhoneNumbers/Countries/{country_code}"

                resp, pricing_resp = await asyncio.gather(
                    client.get(url, auth=(account_sid, auth_token), params=params),
                    client.get(pricing_url, auth=(account_sid, auth_token)),
                    return_exceptions=True
                )

                dynamic_cost_str = None
                price_unit = None
                currency_symbol = ""
                
                if isinstance(pricing_resp, httpx.Response) and pricing_resp.status_code == 200:
                    p_data = pricing_resp.json()
                    price_unit = p_data.get("price_unit")
                    if price_unit:
                        p_unit_upper = price_unit.upper()
                        currency_symbol = "£" if p_unit_upper == "GBP" else ("€" if p_unit_upper == "EUR" else "$" if p_unit_upper == "USD" else f"{price_unit} ")
                    
                    target_type_str = "toll free" if number_type == "TollFree" else number_type.lower()
                    pn_prices = p_data.get("phone_number_prices", [])
                    for p in pn_prices:
                        if p.get("number_type", "").lower() == target_type_str:
                            raw_price = p.get("current_price") or p.get("base_price")
                            if raw_price is not None:
                                cost_val = float(raw_price)
                                dynamic_cost_str = f"{currency_symbol}{cost_val:.2f}"
                            break

                setup_cost_str = f"{currency_symbol}0.00" if currency_symbol else "$0.00"

                if isinstance(resp, httpx.Response) and resp.status_code == 200:
                    twilio_data = resp.json()
                    numbers_list = twilio_data.get("available_phone_numbers", [])
                    formatted = []
                    for n in numbers_list:
                        locality = n.get("locality") or ""
                        region = n.get("region") or ""
                        rate_center = n.get("rate_center") or ""
                        
                        location_parts = [p for p in [locality, region] if p]
                        location_str = ", ".join(location_parts) if location_parts else (rate_center or country_code)

                        formatted.append({
                            "id": n.get("phone_number"),
                            "number": n.get("friendly_name") or n.get("phone_number"),
                            "rawNumber": n.get("phone_number"),
                            "country": country_code,
                            "location": location_str,
                            "locality": locality,
                            "region": region,
                            "postalCode": n.get("postal_code", ""),
                            "rateCenter": rate_center,
                            "type": number_type,
                            "provider": "Twilio",
                            "monthlyCost": dynamic_cost_str if dynamic_cost_str is not None else "N/A",
                            "priceUnit": price_unit or "",
                            "setupCost": setup_cost_str,
                            "capabilities": {
                                "voice": n.get("capabilities", {}).get("voice", True),
                                "sms": n.get("capabilities", {}).get("SMS", True),
                                "mms": n.get("capabilities", {}).get("MMS", False)
                            }
                        })
                    return ApiResponse.success(data=formatted)
                else:
                    status_code = resp.status_code if isinstance(resp, httpx.Response) else "Error"
                    resp_text = resp.text if isinstance(resp, httpx.Response) else str(resp)
                    logger.warning(f"Twilio API returned status {status_code}: {resp_text}")
        except Exception as e:
            logger.error(f"Failed to fetch available numbers from Twilio API: {e}")

    return ApiResponse.success(data=[])


@router.post("/register", dependencies=[Depends(require_roles(["SUPER_ADMIN"]))])
async def register_number(req_body: RegisterPhoneNumberRequest):
    """
    Superadmin registers a purchased DID.
    Optionally provisions with LiveKit unless draft is true.
    """
    clean_number = normalize_phone_number(req_body.number)
    if not clean_number:
        return ApiResponse.error(400, f"Invalid phone number format: {req_body.number}", "INVALID_PHONE_NUMBER")
    logger.info(f"Normalized phone number from {req_body.number} to E.164 format: {clean_number}")
    
    # Check if number already registered (excluding deleted ones to allow re-registering)
    exists = await database.query("SELECT id FROM phone_numbers WHERE number = $1 AND status != 'deleted'", [clean_number])
    if exists:
        return ApiResponse.error(400, f"Phone number {clean_number} is already registered.", "NUMBER_ALREADY_EXISTS")
        
    # If the number exists as soft-deleted, hard-delete it first to avoid UNIQUE constraint violation on INSERT
    deleted_exists = await database.query("SELECT id FROM phone_numbers WHERE number = $1 AND status = 'deleted'", [clean_number])
    if deleted_exists:
        logger.info(f"Hard-deleting soft-deleted phone number record {clean_number} (ID: {deleted_exists[0]['id']}) to allow clean re-registration")
        await database.query("DELETE FROM phone_numbers WHERE id = $1", [deleted_exists[0]["id"]])
        
    # Validate provider configuration/credentials if not a draft registration
    if not req_body.draft:
        if not phone_sync_service.validate_provider_credentials(req_body.provider, req_body.sipConfig):
            return ApiResponse.error(400, "Invalid SIP configuration. Missing authentication username, password, or domain.", "INVALID_SIP_CREDENTIALS")

    trunk_id = None
    dispatch_rule_id = None
    warning_msg = None
    
    final_status = "available"
    if req_body.draft:
        final_status = "pending_sip"
    else:
        # Provision with LiveKit SIP Service
        sip_params = req_body.sipConfig or {}
        trunk_id, dispatch_rule_id, warning_msg = await livekit_sip_service.provision_inbound_trunk(
            number=clean_number,
            name=req_body.name or f"{req_body.provider} DID Line",
            sip_config=sip_params
        )
        
        # If allocation is set to Me/Client/Reseller, status immediately becomes active
        if req_body.allocation in ["me", "client", "reseller"]:
            final_status = "active"
            
    # Set owner details based on allocation
    client_uuid = None
    reseller_uuid = None
    
    if req_body.allocation == "client" and req_body.assignedId:
        client_uuid = uuid.UUID(req_body.assignedId)
    elif req_body.allocation == "reseller" and req_body.assignedId:
        reseller_uuid = uuid.UUID(req_body.assignedId)
    elif req_body.allocation == "me":
        # System internal use: can be marked active but unassigned to a specific client/reseller
        pass
        
    # capabilities & sip_config serialization
    capabilities_json = json.dumps(req_body.capabilities.model_dump())
    sip_config_json = json.dumps(req_body.sipConfig) if req_body.sipConfig else None
    
    try:
        rows = await database.query(
            """INSERT INTO phone_numbers (
                number, name, provider, monthly_cost, setup_cost, status, capabilities, 
                client_id, reseller_id, sip_config, lk_sip_trunk_id, lk_sip_dispatch_rule_id
               ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
               RETURNING *""",
            [
                clean_number,
                req_body.name or f"{req_body.provider} DID Line",
                req_body.provider,
                req_body.monthlyCost,
                req_body.setupCost,
                final_status,
                capabilities_json,
                client_uuid,
                reseller_uuid,
                sip_config_json,
                trunk_id,
                dispatch_rule_id
            ]
        )
        
        row = rows[0]
        
        # Synchronize and cache configurations
        try:
            synced_row = await phone_sync_service.synchronize_phone_number(str(row["id"]), action="create")
            row = synced_row
        except Exception as sync_err:
            logger.error(f"Post-registration sync failed: {sync_err}")
            warning_msg = f"LiveKit sync warning: {str(sync_err)}"
            
        result = {
            "id": str(row["id"]),
            "number": row["number"],
            "name": row["name"],
            "status": row["status"],
            "warning": warning_msg
        }
        
        return ApiResponse.success(status_code=201, message="Phone number registered successfully", data=result)
    except Exception as e:
        logger.error(f"Database insertion failed for phone number registration: {e}")
        # Clean up LiveKit resources if db failed
        if trunk_id and not req_body.draft:
            await livekit_sip_service.deprovision_inbound_trunk(trunk_id, dispatch_rule_id)
        return ApiResponse.error(500, f"Failed to register phone number: {e}", "REGISTER_FAILED")


@router.post("/{id}/lease")
async def lease_number(id: str, req_body: LeasePhoneNumberRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Rent/lease an available phone number.
    Only client or reseller role can call this.
    """
    role = current_user.get("role")
    client_id = current_user.get("client_id")
    reseller_id = current_user.get("reseller_id")
    
    if role not in ["CLIENT", "RESELLER"]:
        return ApiResponse.error(403, "Only clients and reseller partners can lease numbers.", "UNAUTHORIZED_LEASING")
        
    number_uuid = uuid.UUID(id)
    
    # 1. Verify number exists and is available
    rows = await database.query("SELECT * FROM phone_numbers WHERE id = $1", [number_uuid])
    if not rows:
        return ApiResponse.error(404, "Phone number not found.", "NUMBER_NOT_FOUND")
        
    num_record = rows[0]
    if num_record["status"] != "available":
        return ApiResponse.error(400, "Phone number is not available for leasing.", "NUMBER_UNAVAILABLE")
        
    # 2. Determine target client/reseller id
    client_uuid = uuid.UUID(str(client_id)) if client_id else None
    reseller_uuid = uuid.UUID(str(reseller_id)) if reseller_id else None
    
    agent_uuid = None
    if req_body.agentId:
        agent_uuid = uuid.UUID(req_body.agentId)
        
    try:
        updated = await database.query(
            """UPDATE phone_numbers
               SET status = 'active',
                   client_id = $1,
                   reseller_id = $2,
                   name = COALESCE(NULLIF($3, ''), name),
                   agent_id = $4,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = $5
               RETURNING *""",
            [client_uuid, reseller_uuid, req_body.name, agent_uuid, number_uuid]
        )
        
        row = updated[0]
        # Invalidate cache and publish lease event
        phone_sync_service.publish_configuration_changed(row["number"], action="lease")
        
        return ApiResponse.success(
            message="Phone number leased successfully",
            data={
                "id": str(row["id"]),
                "number": row["number"],
                "name": row["name"],
                "status": row["status"],
                "agentId": str(row["agent_id"]) if row["agent_id"] else ""
            }
        )
    except Exception as e:
        logger.error(f"Lease database transaction failed: {e}")
        return ApiResponse.error(500, f"Leasing transaction failed: {e}", "LEASE_FAILED")


@router.post("/{id}/release")
async def release_number(id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Release a leased number back to the pool, or delete it entirely if Superadmin.
    """
    role = current_user.get("role")
    client_id = current_user.get("client_id")
    reseller_id = current_user.get("reseller_id")
    
    number_uuid = uuid.UUID(id)
    
    rows = await database.query("SELECT * FROM phone_numbers WHERE id = $1 AND status != 'deleted'", [number_uuid])
    if not rows:
        return ApiResponse.error(404, "Phone number not found.", "NUMBER_NOT_FOUND")
        
    num_record = rows[0]
    
    if role in ["SUPER_ADMIN", "FINANCE_ADMIN"]:
        # Superadmin soft-deletes DID completely, freeing it at LiveKit
        logger.info(f"Superadmin soft-deleting phone number: {num_record['number']}")
        
        try:
            # Mark status as 'deleted' (soft delete)
            await database.query(
                "UPDATE phone_numbers SET status = 'deleted', updated_at = CURRENT_TIMESTAMP WHERE id = $1", 
                [number_uuid]
            )
            
            # Deprovision LiveKit SIP resources and invalidate cache
            await phone_sync_service.synchronize_phone_number(str(number_uuid), action="delete")
                
            return ApiResponse.success(message=f"Phone number {num_record['number']} deleted and deprovisioned successfully.")
        except Exception as e:
            logger.error(f"Failed to delete phone number: {e}")
            return ApiResponse.error(500, f"Failed to delete phone number: {e}", "DELETE_FAILED")
            
    else:
        # Tenant Client or Reseller releases number back to the public lease pool
        # Check permissions
        is_client_owner = client_id and num_record["client_id"] and str(num_record["client_id"]) == str(client_id)
        is_reseller_owner = reseller_id and num_record["reseller_id"] and str(num_record["reseller_id"]) == str(reseller_id)
        
        if not (is_client_owner or is_reseller_owner):
            return ApiResponse.error(403, "You do not own this leased phone number.", "FORBIDDEN_RELEASE")
            
        try:
            await database.query(
                """UPDATE phone_numbers
                   SET status = 'available',
                       client_id = NULL,
                       reseller_id = NULL,
                       agent_id = NULL,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = $1""",
                [number_uuid]
            )
            # Invalidate cache and publish release event
            phone_sync_service.publish_configuration_changed(num_record["number"], action="release")
            return ApiResponse.success(message=f"Phone number {num_record['number']} returned to public pool.")
        except Exception as e:
            logger.error(f"Failed to release phone number: {e}")
            return ApiResponse.error(500, f"Failed to release leased number: {e}", "RELEASE_FAILED")


@router.patch("/{id}/assign-agent")
async def assign_agent(id: str, req_body: AssignAgentRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Assign an AI Agent to a leased phone number.
    
    IMPORTANT: An agent MUST be explicitly assigned. Phone numbers cannot remain unassigned.
    If agentId is None/null, the phone number will remain in Unassigned state and will not accept calls.
    """
    role = current_user.get("role")
    client_id = current_user.get("client_id")
    reseller_id = current_user.get("reseller_id")
    
    number_uuid = uuid.UUID(id)
    
    rows = await database.query("SELECT * FROM phone_numbers WHERE id = $1 AND status != 'deleted'", [number_uuid])
    if not rows:
        return ApiResponse.error(404, "Phone number not found.", "NUMBER_NOT_FOUND")
        
    num_record = rows[0]
    
    # Verify ownership
    is_client_owner = client_id and num_record["client_id"] and str(num_record["client_id"]) == str(client_id)
    is_reseller_owner = reseller_id and num_record["reseller_id"] and str(num_record["reseller_id"]) == str(reseller_id)
    is_superadmin = role in ["SUPER_ADMIN", "FINANCE_ADMIN"]
    
    if not (is_client_owner or is_reseller_owner or is_superadmin):
        return ApiResponse.error(403, "You do not have permission to route this phone number.", "FORBIDDEN_ROUTE")
        
    agent_uuid = uuid.UUID(req_body.agentId) if req_body.agentId else None
    
    # If agentId is provided, verify it exists and belongs to the client/reseller context
    if agent_uuid:
        agent_rows = await database.query("SELECT id, client_id, user_id FROM agents WHERE id = $1", [agent_uuid])
        if not agent_rows:
            return ApiResponse.error(404, "Agent not found.", "AGENT_NOT_FOUND")
            
        # Optional validation: verify agent belongs to same client context
        agent_record = agent_rows[0]
        if not is_superadmin and client_id and str(agent_record["client_id"]) != str(client_id):
            return ApiResponse.error(403, "You cannot assign an agent that belongs to another client.", "FORBIDDEN_AGENT_ASSIGNMENT")
    else:
        # If no agent is provided, return validation error
        return ApiResponse.error(400, "No agents found. Please create an agent before assigning a phone number.", "NO_AGENT_PROVIDED")
            
    try:
        await database.query(
            "UPDATE phone_numbers SET agent_id = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2",
            [agent_uuid, number_uuid]
        )
        
        # Publish change event on event bus (invalidates cache)
        phone_sync_service.publish_configuration_changed(num_record["number"], action="assign_agent")
        
        return ApiResponse.success(message="Phone number routing updated successfully.")
    except Exception as e:
        logger.error(f"Failed to assign agent: {e}")
        return ApiResponse.error(500, f"Failed to assign agent: {e}", "ASSIGN_AGENT_FAILED")


@router.get("/lookup")
async def lookup_number(number: str):
    """
    Internal API Endpoint to lookup phone number metadata for incoming LiveKit SIP calls.
    Returns: client_id, agent_id, agent prompt configurations, and credits availability.

    IMPORTANT: Phone numbers MUST have an explicitly assigned agent.
    Unassigned phone numbers are not routed and return an error response.
    """
    try:
        canonical_number = normalize_phone_number(number)
        if not canonical_number:
            logger.error(f"Invalid phone number format received: {number}")
            raise HTTPException(
                status_code=400,
                detail={"error": "INVALID_PHONE_NUMBER", "message": f"Invalid phone number: {number}"}
            )

        number_candidates = get_phone_number_variants(number)
        logger.info(f"Inbound call lookup for {number} (canonical: {canonical_number}, candidates: {number_candidates})")

        # Try serving from Redis cache first
        cached_lookup = phone_sync_service.get_cached_lookup(canonical_number)
        if cached_lookup:
            logger.info(f"Cache HIT for {canonical_number}")
            return cached_lookup

        # Query database matching the number (exclude soft-deleted ones)
        rows = await database.query(
            """SELECT * FROM phone_numbers
               WHERE number = ANY($1::text[]) AND status != 'deleted'""",
            [number_candidates]
        )

        if not rows:
            logger.warning(f"PHONE_NUMBER_NOT_FOUND: {number} (canonical: {canonical_number})")
            raise HTTPException(
                status_code=404,
                detail={"error": "PHONE_NUMBER_NOT_FOUND", "message": f"Phone number {number} not found"}
            )

        num_record = rows[0]
        client_uuid = num_record["client_id"]
        reseller_uuid = num_record["reseller_id"]
        agent_uuid = num_record["agent_id"]

        # CRITICAL: Verify agent is assigned. Unassigned phone numbers cannot accept calls.
        if not agent_uuid:
            logger.warning(f"PHONE_NOT_ASSIGNED: {number} has no assigned agent")
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "PHONE_NOT_ASSIGNED",
                    "message": f"Phone number {number} has no assigned agent",
                    "prompt": "Welcome to 42 voice and we will get back to you."
                }
            )

        # Check Credits Status
        has_credits = True
        minutes_balance = 0

        if client_uuid:
            cl_rows = await database.query("SELECT minutes_balance FROM clients WHERE id = $1", [client_uuid])
            if cl_rows:
                minutes_balance = cl_rows[0]["minutes_balance"]
                has_credits = minutes_balance > 0
        elif reseller_uuid:
            res_rows = await database.query("SELECT minutes_balance FROM resellers WHERE id = $1", [reseller_uuid])
            if res_rows:
                minutes_balance = res_rows[0]["minutes_balance"]
                has_credits = minutes_balance > 0

        if not has_credits:
            logger.warning(f"INSUFFICIENT_CREDITS for phone number {number}. Balance: {minutes_balance}")
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "INSUFFICIENT_CREDITS",
                    "message": f"Account has insufficient call minutes for {number}",
                    "prompt": "We are sorry, but this account has run out of call minutes. Please recharge your balance in the dashboard. Goodbye."
                }
            )

        # Resolve linked agent details
        agent_rows = await database.query("SELECT * FROM agents WHERE id = $1", [agent_uuid])
        if not agent_rows:
            logger.error(f"INTERNAL_ERROR: Agent {agent_uuid} referenced by phone number {number} not found in database.")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "INTERNAL_ERROR",
                    "message": "Assigned agent record is missing",
                    "prompt": "The assigned agent is not available."
                }
            )

        agent_record = agent_rows[0]
        agent_name = agent_record["name"]
        agent_status = agent_record["status"]
        agent_type = agent_record["call_type"] or "general"
        prompt = agent_record["activity_description"] or agent_record["use_case"] or f"You are {agent_name}. Help the caller."

        result = {
            "exists": True,
            "has_credits": has_credits,
            "minutes_balance": minutes_balance,
            "client_id": str(client_uuid) if client_uuid else None,
            "agent_id": str(agent_uuid),
            "agent_name": agent_name,
            "agent_status": agent_status,
            "agent_type": agent_type,
            "prompt": prompt
        }

        # Cache the successful routing lookup
        phone_sync_service.set_cached_lookup(canonical_number, result)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"INTERNAL_ERROR during phone number lookup for {number}: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "INTERNAL_ERROR", "message": f"Lookup failed: {str(e)}"}
        )


@router.get("/livekit-status", dependencies=[Depends(require_roles(["SUPER_ADMIN", "FINANCE_ADMIN"]))])
async def get_livekit_status():
    """
    Get live SIP trunks and dispatch rules from LiveKit server.
    Only accessible by Superadmins.
    """
    status_data = await livekit_sip_service.get_sip_status()
    return ApiResponse.success(data=status_data)


@router.delete("/livekit/trunk/{trunk_id}", dependencies=[Depends(require_roles(["SUPER_ADMIN"]))])
async def delete_livekit_trunk(trunk_id: str):
    """
    Delete a LiveKit SIP Trunk directly from LiveKit server.
    Also disassociates it from any DB phone number.
    """
    success, err = await livekit_sip_service.delete_trunk(trunk_id)
    if not success:
        return ApiResponse.error(500, f"Failed to delete LiveKit trunk: {err}", "DELETE_TRUNK_FAILED")
        
    try:
        await database.query("UPDATE phone_numbers SET lk_sip_trunk_id = NULL WHERE lk_sip_trunk_id = $1", [trunk_id])
    except Exception as e:
        logger.warning(f"Failed to clear db lk_sip_trunk_id reference: {e}")
        
    return ApiResponse.success(message=f"LiveKit SIP Trunk {trunk_id} deleted successfully.")


@router.delete("/livekit/dispatch-rule/{rule_id}", dependencies=[Depends(require_roles(["SUPER_ADMIN"]))])
async def delete_livekit_dispatch_rule(rule_id: str):
    """
    Delete a LiveKit SIP Dispatch Rule directly from LiveKit server.
    Also disassociates it from any DB phone number.
    """
    success, err = await livekit_sip_service.delete_dispatch_rule(rule_id)
    if not success:
        return ApiResponse.error(500, f"Failed to delete LiveKit dispatch rule: {err}", "DELETE_RULE_FAILED")
        
    try:
        await database.query("UPDATE phone_numbers SET lk_sip_dispatch_rule_id = NULL WHERE lk_sip_dispatch_rule_id = $1", [rule_id])
    except Exception as e:
        logger.warning(f"Failed to clear db lk_sip_dispatch_rule_id reference: {e}")
        
    return ApiResponse.success(message=f"LiveKit SIP Dispatch Rule {rule_id} deleted successfully.")



@router.put("/{id}", dependencies=[Depends(require_roles(["SUPER_ADMIN"]))])
async def update_phone_number(id: str, req_body: EditPhoneNumberRequest):
    """
    Superadmin edits registered phone number parameters.
    """
    number_uuid = uuid.UUID(id)
    
    # Check if number exists and is not soft deleted
    rows = await database.query("SELECT * FROM phone_numbers WHERE id = $1 AND status != 'deleted'", [number_uuid])
    if not rows:
        return ApiResponse.error(404, "Phone number not found.", "NUMBER_NOT_FOUND")
        
    num_record = rows[0]
    
    # Construct update parameters dynamically
    updates = []
    params: List[Any] = []
    
    if req_body.name is not None:
        params.append(req_body.name)
        updates.append(f"name = ${len(params)}")
        
    if req_body.monthlyCost is not None:
        params.append(req_body.monthlyCost)
        updates.append(f"monthly_cost = ${len(params)}")
        
    if req_body.setupCost is not None:
        params.append(req_body.setupCost)
        updates.append(f"setup_cost = ${len(params)}")
        
    if req_body.sipConfig is not None:
        # Validate provider credentials
        if not phone_sync_service.validate_provider_credentials(num_record["provider"], req_body.sipConfig):
            return ApiResponse.error(400, "Invalid SIP configuration. Missing authentication username, password, or domain.", "INVALID_SIP_CREDENTIALS")
        params.append(json.dumps(req_body.sipConfig))
        updates.append(f"sip_config = ${len(params)}")
        
    if not updates:
        return ApiResponse.success(message="No fields changed.")
        
    params.append(number_uuid)
    query_str = f"UPDATE phone_numbers SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE id = ${len(params)} RETURNING *"
    
    try:
        updated = await database.query(query_str, params)
        row = updated[0]
        
        # Sync changes to LiveKit and update cache immediately
        try:
            synced_row = await phone_sync_service.synchronize_phone_number(str(number_uuid), action="update")
            row = synced_row
        except Exception as sync_err:
            logger.error(f"LiveKit sync failed during update: {sync_err}")
            
        return ApiResponse.success(
            message="Phone number details updated successfully.",
            data={
                "id": str(row["id"]),
                "number": row["number"],
                "name": row["name"],
                "monthlyCost": f"${row['monthly_cost']:.2f}",
                "setupCost": f"${row['setup_cost']:.2f}"
            }
        )
    except Exception as e:
        logger.error(f"Failed to update phone number: {e}")
        return ApiResponse.error(500, f"Failed to update phone number: {e}", "UPDATE_FAILED")
