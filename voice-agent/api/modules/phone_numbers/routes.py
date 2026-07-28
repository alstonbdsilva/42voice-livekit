import uuid
import logging
import json
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel, Field

from api import database
from api.utils.api_response import ApiResponse
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


@router.post("/register", dependencies=[Depends(require_roles(["SUPER_ADMIN"]))])
async def register_number(req_body: RegisterPhoneNumberRequest):
    """
    Superadmin registers a purchased DID.
    Optionally provisions with LiveKit unless draft is true.
    """
    import re
    # Strip spaces, dashes, parens
    stripped = re.sub(r"[\s\-\(\)]", "", req_body.number.strip())
    # Handle country code followed by leading zero (e.g. +6409... -> +649...)
    match = re.match(r"^(\+?\d{1,3})0(\d{7,})$", stripped)
    if match:
        prefix = match.group(1)
        rest = match.group(2)
        if not prefix.startswith("+"):
            prefix = "+" + prefix
        clean_number = f"{prefix}{rest}"
        logger.info(f"Normalized phone number from {req_body.number} to E.164 format: {clean_number}")
    else:
        clean_number = stripped
        if not clean_number.startswith("+") and clean_number.isdigit():
            clean_number = "+" + clean_number
    
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
    clean_number = number.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    logger.info(f"Looking up phone routing for incoming SIP caller number: {clean_number}")
    
    # Try serving from Redis cache first
    cached_lookup = phone_sync_service.get_cached_lookup(clean_number)
    if cached_lookup:
        logger.info(f"Cache HIT: Serving phone routing from Redis cache for: {clean_number}")
        return cached_lookup
        
    # Query database matching the number (exclude soft-deleted ones)
    rows = await database.query(
        """SELECT * FROM phone_numbers 
           WHERE (REPLACE(REPLACE(REPLACE(REPLACE(number, ' ', ''), '-', ''), '(', ''), ')', '') = $1
              OR number = $2) AND status != 'deleted'""",
        [clean_number, number.strip()]
    )
    
    if not rows:
        logger.warning(f"Inbound routing lookup: phone number {number} not found in database.")
        result: Dict[str, Any] = {
            "exists": False,
            "has_credits": False,
            "client_id": None,
            "agent_id": None,
            "agent_name": None,
            "agent_type": None,
            "prompt": "This phone number is not configured in the system.",
            "error": "PHONE_NUMBER_NOT_FOUND"
        }
        # Cache negative lookup briefly
        phone_sync_service.set_cached_lookup(clean_number, result, ttl=300)
        return result
        
    num_record = rows[0]
    client_uuid = num_record["client_id"]
    reseller_uuid = num_record["reseller_id"]
    agent_uuid = num_record["agent_id"]
    
    # CRITICAL: Verify agent is assigned. Unassigned phone numbers cannot accept calls.
    if not agent_uuid:
        logger.warning(f"Inbound call rejected: phone number {number} has no assigned agent (Unassigned state).")
        result = {
            "exists": True,
            "has_credits": False,
            "client_id": str(client_uuid) if client_uuid else None,
            "agent_id": None,
            "agent_name": None,
            "agent_type": None,
            "prompt": "Welcome to 42 voice and we will get back to you.",
            "error": "UNASSIGNED_PHONE_NUMBER"
        }
        phone_sync_service.set_cached_lookup(clean_number, result)
        return result
    
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
            
    # Resolve linked agent details
    agent_rows = await database.query("SELECT * FROM agents WHERE id = $1", [agent_uuid])
    if not agent_rows:
        logger.error(f"Agent {agent_uuid} referenced by phone number {number} not found in database.")
        result = {
            "exists": True,
            "has_credits": False,
            "client_id": str(client_uuid) if client_uuid else None,
            "agent_id": str(agent_uuid),
            "agent_name": None,
            "agent_type": None,
            "prompt": "The assigned agent is not available.",
            "error": "AGENT_NOT_FOUND"
        }
        phone_sync_service.set_cached_lookup(clean_number, result)
        return result
    
    agent_record = agent_rows[0]
    agent_name = agent_record["name"]
    agent_type = agent_record["call_type"] or "general"
    prompt = agent_record["activity_description"] or agent_record["use_case"] or f"You are {agent_name}. Help the caller."
            
    result = {
        "exists": True,
        "has_credits": has_credits,
        "minutes_balance": minutes_balance,
        "client_id": str(client_uuid) if client_uuid else None,
        "agent_id": str(agent_uuid),
        "agent_name": agent_name,
        "agent_type": agent_type,
        "prompt": prompt
    }
    
    # Cache the successful routing lookup
    phone_sync_service.set_cached_lookup(clean_number, result)
    return result


@router.get("/livekit-status", dependencies=[Depends(require_roles(["SUPER_ADMIN", "FINANCE_ADMIN"]))])
async def get_livekit_status():
    """
    Get live SIP trunks and dispatch rules from LiveKit server.
    Only accessible by Superadmins.
    """
    status_data = await livekit_sip_service.get_sip_status()
    return ApiResponse.success(data=status_data)


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
