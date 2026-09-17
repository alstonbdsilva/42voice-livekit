import json
import uuid
from typing import List, Dict, Any, Optional
from api import database


def is_valid_uuid(val: Any) -> bool:
    if not val:
        return False
    try:
        uuid.UUID(str(val))
        return True
    except Exception:
        return False


def parse_credentials(val: Any) -> Dict[str, Any]:
    if not val:
        return {}
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {}


def mask_sensitive(val: Optional[str]) -> str:
    if not val:
        return ""
    if len(val) <= 4:
        return "****"
    return "*" * (len(val) - 4) + val[-4:]


def mask_credentials(provider: str, credentials: Dict[str, Any]) -> Dict[str, Any]:
    masked = dict(credentials)
    if provider == "twilio":
        if "account_sid" in masked:
            masked["account_sid"] = mask_sensitive(str(masked["account_sid"]))
        if "auth_token" in masked:
            masked["auth_token"] = mask_sensitive(str(masked["auth_token"]))
    elif provider == "vobiz":
        if "auth_id" in masked:
            masked["auth_id"] = mask_sensitive(str(masked["auth_id"]))
        if "auth_token" in masked:
            masked["auth_token"] = mask_sensitive(str(masked["auth_token"]))
    return masked


async def list_telephony_configurations(client_id: Optional[str] = None) -> List[Dict[str, Any]]:
    sql = """
        SELECT c.id, c.name, c.provider, c.is_default_outbound, c.created_at, c.updated_at,
               (SELECT COUNT(*) FROM telephony_phone_numbers p WHERE p.telephony_configuration_id = c.id) as phone_number_count
        FROM telephony_configurations c
    """
    params = []
    if client_id and is_valid_uuid(client_id):
        sql += " WHERE c.client_id = $1::uuid "
        params.append(client_id)
    sql += " ORDER BY c.created_at DESC"

    rows = await database.query(sql, params)
    result = []
    for r in rows:
        result.append({
            "id": str(r["id"]),
            "name": r["name"],
            "provider": r["provider"],
            "is_default_outbound": r["is_default_outbound"],
            "phone_number_count": int(r["phone_number_count"]),
            "created_at": r["created_at"].isoformat() if r["created_at"] else "",
            "updated_at": r["updated_at"].isoformat() if r["updated_at"] else ""
        })
    return result


async def get_telephony_configuration(config_id: str, client_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not is_valid_uuid(config_id):
        return None
    sql = "SELECT id, name, provider, credentials, is_default_outbound, client_id, created_at, updated_at FROM telephony_configurations WHERE id = $1::uuid"
    params = [config_id]
    if client_id and is_valid_uuid(client_id):
        sql += " AND client_id = $2::uuid"
        params.append(client_id)
    
    rows = await database.query(sql, params)
    if not rows:
        return None
    r = rows[0]
    raw_creds = parse_credentials(r["credentials"])
    return {
        "id": str(r["id"]),
        "name": r["name"],
        "provider": r["provider"],
        "is_default_outbound": r["is_default_outbound"],
        "credentials": mask_credentials(r["provider"], raw_creds),
        "raw_credentials": raw_creds,
        "created_at": r["created_at"].isoformat() if r["created_at"] else "",
        "updated_at": r["updated_at"].isoformat() if r["updated_at"] else ""
    }


async def clear_default_outbound(client_id: Optional[str] = None):
    if client_id and is_valid_uuid(client_id):
        await database.query("UPDATE telephony_configurations SET is_default_outbound = false WHERE client_id = $1::uuid AND is_default_outbound = true", [client_id])
    else:
        await database.query("UPDATE telephony_configurations SET is_default_outbound = false WHERE is_default_outbound = true")


async def create_telephony_configuration(
    name: str,
    provider: str,
    credentials: Dict[str, Any],
    is_default_outbound: bool = False,
    client_id: Optional[str] = None
) -> Dict[str, Any]:
    existing = await list_telephony_configurations(client_id)
    if len(existing) == 0:
        is_default_outbound = True
    elif is_default_outbound:
        await clear_default_outbound(client_id)

    client_uuid = client_id if (client_id and is_valid_uuid(client_id)) else None
    sql = """
        INSERT INTO telephony_configurations (name, provider, credentials, is_default_outbound, client_id)
        VALUES ($1, $2, $3::jsonb, $4, $5::uuid)
        RETURNING id, name, provider, credentials, is_default_outbound, created_at, updated_at
    """
    rows = await database.query(sql, [name, provider, json.dumps(credentials), is_default_outbound, client_uuid])
    r = rows[0]
    raw_creds = parse_credentials(r["credentials"]) or credentials
    return {
        "id": str(r["id"]),
        "name": r["name"],
        "provider": r["provider"],
        "is_default_outbound": r["is_default_outbound"],
        "credentials": mask_credentials(r["provider"], raw_creds),
        "created_at": r["created_at"].isoformat() if r["created_at"] else "",
        "updated_at": r["updated_at"].isoformat() if r["updated_at"] else ""
    }


async def update_telephony_configuration(
    config_id: str,
    name: Optional[str] = None,
    credentials: Optional[Dict[str, Any]] = None,
    client_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    if not is_valid_uuid(config_id):
        return None
    existing = await get_telephony_configuration(config_id, client_id)
    if not existing:
        return None

    new_name = name if name is not None else existing["name"]
    new_creds = parse_credentials(existing["raw_credentials"])
    if credentials is not None:
        for k, v in credentials.items():
            if str(v).startswith("****"):
                continue  # keep existing if masked
            new_creds[k] = v

    sql = """
        UPDATE telephony_configurations
        SET name = $1, credentials = $2::jsonb, updated_at = CURRENT_TIMESTAMP
        WHERE id = $3::uuid
        RETURNING id, name, provider, credentials, is_default_outbound, created_at, updated_at
    """
    rows = await database.query(sql, [new_name, json.dumps(new_creds), config_id])
    if not rows:
        return None
    r = rows[0]
    return {
        "id": str(r["id"]),
        "name": r["name"],
        "provider": r["provider"],
        "is_default_outbound": r["is_default_outbound"],
        "credentials": mask_credentials(r["provider"], new_creds),
        "created_at": r["created_at"].isoformat() if r["created_at"] else "",
        "updated_at": r["updated_at"].isoformat() if r["updated_at"] else ""
    }


async def set_default_telephony_configuration(config_id: str, client_id: Optional[str] = None) -> bool:
    if not is_valid_uuid(config_id):
        return False
    existing = await get_telephony_configuration(config_id, client_id)
    if not existing:
        return False
    await clear_default_outbound(client_id)
    await database.query("UPDATE telephony_configurations SET is_default_outbound = true WHERE id = $1::uuid", [config_id])
    return True


async def delete_telephony_configuration(config_id: str, client_id: Optional[str] = None) -> bool:
    if not is_valid_uuid(config_id):
        return False
    existing = await get_telephony_configuration(config_id, client_id)
    if not existing:
        return False
    await database.query("DELETE FROM telephony_configurations WHERE id = $1::uuid", [config_id])
    return True


# --- Phone Numbers DB operations ---

async def list_phone_numbers(config_id: str) -> List[Dict[str, Any]]:
    if not is_valid_uuid(config_id):
        return []
    sql = """
        SELECT p.id, p.telephony_configuration_id, p.address, p.address_type, p.country_code, p.label,
               p.is_active, p.is_default_caller_id, p.inbound_agent_id, p.created_at, p.updated_at,
               a.name as inbound_agent_name
        FROM telephony_phone_numbers p
        LEFT JOIN agents a ON p.inbound_agent_id = a.id
        WHERE p.telephony_configuration_id = $1::uuid
        ORDER BY p.created_at ASC
    """
    rows = await database.query(sql, [config_id])
    result = []
    for r in rows:
        result.append({
            "id": str(r["id"]),
            "telephony_configuration_id": str(r["telephony_configuration_id"]),
            "address": r["address"],
            "address_type": r["address_type"],
            "country_code": r["country_code"],
            "label": r["label"],
            "is_active": r["is_active"],
            "is_default_caller_id": r["is_default_caller_id"],
            "inbound_agent_id": str(r["inbound_agent_id"]) if r["inbound_agent_id"] else None,
            "inbound_agent_name": r["inbound_agent_name"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else "",
            "updated_at": r["updated_at"].isoformat() if r["updated_at"] else ""
        })
    return result


async def add_phone_number(
    config_id: str,
    address: str,
    address_type: str = "pstn",
    country_code: Optional[str] = None,
    label: Optional[str] = None,
    is_active: bool = True,
    is_default_caller_id: bool = False,
    inbound_agent_id: Optional[str] = None
) -> Dict[str, Any]:
    if not is_valid_uuid(config_id):
        raise ValueError("Invalid configuration ID")
    existing_nums = await list_phone_numbers(config_id)
    if len(existing_nums) == 0:
        is_default_caller_id = True
    elif is_default_caller_id:
        await database.query("UPDATE telephony_phone_numbers SET is_default_caller_id = false WHERE telephony_configuration_id = $1::uuid", [config_id])

    agent_uuid = inbound_agent_id if (inbound_agent_id and is_valid_uuid(inbound_agent_id)) else None
    sql = """
        INSERT INTO telephony_phone_numbers (telephony_configuration_id, address, address_type, country_code, label, is_active, is_default_caller_id, inbound_agent_id)
        VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8::uuid)
        RETURNING id, telephony_configuration_id, address, address_type, country_code, label, is_active, is_default_caller_id, inbound_agent_id, created_at, updated_at
    """
    rows = await database.query(sql, [config_id, address, address_type, country_code, label, is_active, is_default_caller_id, agent_uuid])
    r = rows[0]
    return {
        "id": str(r["id"]),
        "telephony_configuration_id": str(r["telephony_configuration_id"]),
        "address": r["address"],
        "address_type": r["address_type"],
        "country_code": r["country_code"],
        "label": r["label"],
        "is_active": r["is_active"],
        "is_default_caller_id": r["is_default_caller_id"],
        "inbound_agent_id": str(r["inbound_agent_id"]) if r["inbound_agent_id"] else None,
        "created_at": r["created_at"].isoformat() if r["created_at"] else "",
        "updated_at": r["updated_at"].isoformat() if r["updated_at"] else ""
    }


async def update_phone_number(
    phone_number_id: str,
    config_id: str,
    address: Optional[str] = None,
    address_type: Optional[str] = None,
    country_code: Optional[str] = None,
    label: Optional[str] = None,
    is_active: Optional[bool] = None,
    inbound_agent_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    if not is_valid_uuid(phone_number_id) or not is_valid_uuid(config_id):
        return None
    sql = "SELECT * FROM telephony_phone_numbers WHERE id = $1::uuid AND telephony_configuration_id = $2::uuid"
    rows = await database.query(sql, [phone_number_id, config_id])
    if not rows:
        return None
    r = rows[0]

    new_addr = address if address is not None else r["address"]
    new_type = address_type if address_type is not None else r["address_type"]
    new_cc = country_code if country_code is not None else r["country_code"]
    new_label = label if label is not None else r["label"]
    new_active = is_active if is_active is not None else r["is_active"]

    if inbound_agent_id is not None:
        new_agent = inbound_agent_id if is_valid_uuid(inbound_agent_id) else None
    else:
        new_agent = str(r["inbound_agent_id"]) if r["inbound_agent_id"] else None

    update_sql = """
        UPDATE telephony_phone_numbers
        SET address = $1, address_type = $2, country_code = $3, label = $4, is_active = $5, inbound_agent_id = $6::uuid, updated_at = CURRENT_TIMESTAMP
        WHERE id = $7::uuid
        RETURNING id, telephony_configuration_id, address, address_type, country_code, label, is_active, is_default_caller_id, inbound_agent_id, created_at, updated_at
    """
    res = await database.query(update_sql, [new_addr, new_type, new_cc, new_label, new_active, new_agent, phone_number_id])
    if not res:
        return None
    updated = res[0]
    return {
        "id": str(updated["id"]),
        "telephony_configuration_id": str(updated["telephony_configuration_id"]),
        "address": updated["address"],
        "address_type": updated["address_type"],
        "country_code": updated["country_code"],
        "label": updated["label"],
        "is_active": updated["is_active"],
        "is_default_caller_id": updated["is_default_caller_id"],
        "inbound_agent_id": str(updated["inbound_agent_id"]) if updated["inbound_agent_id"] else None,
        "created_at": updated["created_at"].isoformat() if updated["created_at"] else "",
        "updated_at": updated["updated_at"].isoformat() if updated["updated_at"] else ""
    }


async def set_default_caller_id(phone_number_id: str, config_id: str) -> bool:
    if not is_valid_uuid(phone_number_id) or not is_valid_uuid(config_id):
        return False
    await database.query("UPDATE telephony_phone_numbers SET is_default_caller_id = false WHERE telephony_configuration_id = $1::uuid", [config_id])
    await database.query("UPDATE telephony_phone_numbers SET is_default_caller_id = true WHERE id = $1::uuid AND telephony_configuration_id = $2::uuid", [phone_number_id, config_id])
    return True


async def delete_phone_number(phone_number_id: str, config_id: str) -> bool:
    if not is_valid_uuid(phone_number_id) or not is_valid_uuid(config_id):
        return False
    await database.query("DELETE FROM telephony_phone_numbers WHERE id = $1::uuid AND telephony_configuration_id = $2::uuid", [phone_number_id, config_id])
    return True
