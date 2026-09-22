"""
Bridge an agent worker into the actual inbound SIP room created for a call
placed through the Twilio REST fallback.

When ``initiate_call`` falls back to the Twilio REST API, Twilio dials the
LiveKit SIP ingress endpoint directly (``sip:<caller_id>@<host>``). LiveKit
matches the inbound trunk for the caller's DID and, via the number's SIP
dispatch rule (individual rule with ``room_prefix="sip-"``), creates a NEW
room named like ``sip-_+<caller_id>_<random>`` and joins the phone there as a
SIP participant.

Any worker dispatched to the original ``call-...`` room during the earlier
native LiveKit-outbound-SIP attempt is left behind in an empty room while the
phone sits in the ``sip-...`` room, so the caller hears silence.

This module makes the final dispatch deterministic:

1. Discover the exact ``sip-`` room for this caller (polls until the room
   appears, which happens once LiveKit processes the bridged child SIP leg).
2. Ensure exactly ONE agent dispatch exists for that room - reusing a dispatch
   already created by the dispatch rule's ``room_config.agents`` and skipping
   when the agent is already connected, so duplicates are never created.
3. Dispatch with the outbound-call metadata so the worker loads the correct
   agent directly (no dependency on SIP header forwarding alone).
"""

import asyncio
import logging
from typing import List, Optional

from livekit import api as lk_api

from api.utils.phone import normalize_phone_number
from config import get_settings

logger = logging.getLogger("voice-agent.api.telephony_configs.inbound_sip_bridge")

ROOM_PREFIX = "sip-"

SIP_CALLED_NUMBER_KEYS = (
    "sip.trunkPhoneNumber",
    "sip.toUser",
    "sip.to",
    "sip.phoneNumber",
)


def _caller_variants(caller_id: str) -> List[str]:
    variants: List[str] = []
    raw = (caller_id or "").strip()
    normalized = normalize_phone_number(raw)
    candidates = [raw, normalized, raw.replace("+", "")]
    for candidate in candidates:
        if not candidate:
            continue
        if candidate not in variants:
            variants.append(candidate)
    return variants


async def _participant_confirms_call(
    lk: lk_api.LiveKitAPI, room_name: str, caller_id: str
) -> bool:
    expected: set = set()
    for variant in _caller_variants(caller_id):
        expected.add(normalize_phone_number(variant))
    expected.discard("")
    try:
        resp = await lk.room.list_participants(
            lk_api.ListParticipantsRequest(room=room_name)
        )
    except Exception as err:
        logger.warning(f"[SIP_BRIDGE] participant check failed for '{room_name}': {err}")
        return False
    participants = resp.participants or []
    if not participants:
        return False
    for participant in participants:
        attributes = dict(getattr(participant, "attributes", None) or {})
        for key in SIP_CALLED_NUMBER_KEYS:
            value = attributes.get(key)
            if not value:
                continue
            normalized = normalize_phone_number(str(value))
            if normalized in expected:
                return True
    return False


async def discover_inbound_sip_room(
    lk: lk_api.LiveKitAPI,
    caller_id: str,
    max_attempts: int = 40,
    poll_interval: float = 2.0,
) -> Optional[str]:
    signatures = {f"_{variant}_" for variant in _caller_variants(caller_id) if variant}
    for attempt in range(1, max_attempts + 1):
        try:
            resp = await lk.room.list_rooms(lk_api.ListRoomsRequest())
        except Exception as err:
            logger.warning(f"[SIP_BRIDGE] room poll #{attempt} failed: {err}")
            await asyncio.sleep(poll_interval)
            continue

        candidates: List[str] = []
        for room in (resp.rooms or []):
            room_name = getattr(room, "name", "") or ""
            if not room_name.startswith(ROOM_PREFIX):
                continue
            if not any(signature in room_name for signature in signatures):
                continue
            candidates.append(room_name)

        if not candidates:
            await asyncio.sleep(poll_interval)
            continue

        for room_name in candidates:
            if await _participant_confirms_call(lk, room_name, caller_id):
                logger.info(f"[SIP_BRIDGE] PHONE/SIP ROOM={room_name}")
                return room_name

        logger.info(f"[SIP_BRIDGE] PHONE/SIP ROOM={candidates[0]}")
        return candidates[0]

    logger.warning(f"[SIP_BRIDGE] no inbound SIP room found for caller '{caller_id}'")
    return None


async def ensure_agent_dispatch_for_room(
    lk: lk_api.LiveKitAPI,
    room_name: str,
    agent_name: str,
    metadata: str,
) -> Optional[str]:
    try:
        existing = await lk.agent_dispatch.list_dispatch(room_name)
        for dispatch in existing or []:
            if (getattr(dispatch, "agent_name", "") or "") != agent_name:
                continue
            state = getattr(dispatch, "state", None)
            deleted_at = getattr(state, "deleted_at", 0) if state is not None else 0
            if not deleted_at:
                logger.info(
                    f"[SIP_BRIDGE] dispatch {getattr(dispatch, 'id', '?')} already exists for "
                    f"agent '{agent_name}' in room '{room_name}'; skipping duplicate"
                )
                return getattr(dispatch, "id", None)
    except Exception as err:
        logger.warning(f"[SIP_BRIDGE] list_dispatch failed for '{room_name}': {err}")

    try:
        resp = await lk.room.list_participants(
            lk_api.ListParticipantsRequest(room=room_name)
        )
        for participant in (resp.participants or []):
            if (getattr(participant, "identity", "") or "") == agent_name:
                logger.info(
                    f"[SIP_BRIDGE] agent '{agent_name}' already present in room '{room_name}'; skipping"
                )
                return None
    except Exception as err:
        logger.warning(f"[SIP_BRIDGE] participant check failed for '{room_name}': {err}")

    created = await lk.agent_dispatch.create_dispatch(
        lk_api.CreateAgentDispatchRequest(
            agent_name=agent_name,
            room=room_name,
            metadata=metadata or "",
        )
    )
    dispatch_id = getattr(created, "id", None)
    logger.info(f"[SIP_BRIDGE] WORKER ROOM={room_name} dispatch_id={dispatch_id}")
    return dispatch_id


async def ensure_inbound_sip_agent_dispatch(
    caller_id: str,
    metadata: str,
    agent_name: Optional[str] = None,
    max_attempts: int = 40,
    poll_interval: float = 2.0,
) -> Optional[str]:
    settings = get_settings()
    agent = agent_name or settings.livekit_agent_name
    if not agent:
        logger.warning("[SIP_BRIDGE] no agent name configured; skipping")
        return None
    if not (
        settings.livekit_url
        and settings.livekit_api_key
        and settings.livekit_api_secret
    ):
        logger.warning("[SIP_BRIDGE] LiveKit not configured; skipping inbound SIP bridge")
        return None

    lk = None
    try:
        lk = lk_api.LiveKitAPI(
            settings.livekit_url,
            settings.livekit_api_key,
            settings.livekit_api_secret,
        )
        room_name = await discover_inbound_sip_room(
            lk, caller_id, max_attempts=max_attempts, poll_interval=poll_interval
        )
        if not room_name:
            return None
        return await ensure_agent_dispatch_for_room(
            lk, room_name, agent, metadata or ""
        )
    finally:
        if lk is not None:
            try:
                await lk.aclose()
            except Exception:
                pass