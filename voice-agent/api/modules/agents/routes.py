import logging
import uuid
import boto3
import httpx
import time
from datetime import datetime
from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from config import get_settings
from api.utils.api_response import ApiResponse
from api.modules.agents.services import AgentService
from api.middlewares.auth import get_current_user

logger = logging.getLogger("voice-agent.api.agents.routes")

router = APIRouter()
agent_service = AgentService()


class PreviewVoiceRequest(BaseModel):
    voiceId: str
    text: Optional[str] = "Hello! I am your AI voice assistant. How can I help you today?"
    modelId: str
    stability: Optional[float] = 0.5
    similarityBoost: Optional[float] = 0.75


# --- Request Models ---

class UpdateAgentRequest(BaseModel):
    status: Optional[str] = Field(None, pattern="^(active|paused|testing)$")
    name: Optional[str] = None
    useCase: Optional[str] = None
    activityDescription: Optional[str] = None
    callType: Optional[str] = None
    resellerIds: Optional[List[str]] = None
    clientIds: Optional[List[str]] = None
    voiceName: Optional[str] = None
    voiceGender: Optional[str] = None
    ttsProvider: Optional[str] = None
    ttsModel: Optional[str] = None
    ttsVoiceId: Optional[str] = None
    ttsVoiceName: Optional[str] = None
    guardrails: Optional[Dict[str, Any]] = None
    customGuardrails: Optional[str] = None
    knowledgeItems: Optional[List[Dict[str, Any]]] = None
    toolIds: Optional[List[str]] = None


class CreateAgentRequest(BaseModel):
    name: str = Field(..., min_length=1)
    callType: str = Field(default="inbound")
    useCase: Optional[str] = ""
    activityDescription: Optional[str] = ""
    resellerIds: Optional[List[str]] = []
    clientIds: Optional[List[str]] = []
    voiceName: Optional[str] = "aria"
    voiceGender: Optional[str] = "female"
    ttsProvider: Optional[str] = None
    ttsModel: Optional[str] = None
    ttsVoiceId: Optional[str] = None
    ttsVoiceName: Optional[str] = None
    guardrails: Optional[Dict[str, Any]] = {}
    customGuardrails: Optional[str] = ""
    knowledgeItems: Optional[List[Dict[str, Any]]] = []
    toolIds: Optional[List[str]] = []


# --- Route Endpoints ---
# All agent endpoints require authentication

@router.post("/upload")
async def upload_agent_file(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Upload a knowledge base file to S3 and return the S3 details.
    """
    settings = get_settings()
    try:
        # Get S3 client
        endpoint_url = f"https://s3.{settings.aws_region}.amazonaws.com" if settings.aws_region else None
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
            endpoint_url=endpoint_url
        )
        
        # Generate unique key in S3
        unique_id = uuid.uuid4().hex
        s3_key = f"knowledge_base/{unique_id}_{file.filename}"
        
        # Upload
        s3_client.upload_fileobj(
            file.file,
            settings.s3_bucket_name,
            s3_key,
            ExtraArgs={"ContentType": file.content_type or "application/octet-stream"}
        )
        
        s3_url = f"https://{settings.s3_bucket_name}.s3.{settings.aws_region}.amazonaws.com/{s3_key}"
        
        return ApiResponse.success(
            status_code=200,
            message="File uploaded successfully",
            data={
                "s3Key": s3_key,
                "s3Url": s3_url,
                "filename": file.filename,
                "contentType": file.content_type
            }
        )
    except Exception as e:
        logger.error(f"Failed to upload file to S3: {e}")
        return ApiResponse.error(
            status_code=500,
            message=f"Failed to upload file to S3: {str(e)}",
            code="S3_UPLOAD_FAILED"
        )


@router.post("")
async def create(req_body: CreateAgentRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    user_context = {
        "role": current_user["role"],
        "id": current_user["id"],
        "client_id": current_user.get("client_id"),
        "reseller_id": current_user.get("reseller_id")
    }
    agent = await agent_service.create_agent(req_body.model_dump(), user_context)
    if not agent:
        return ApiResponse.error(
            status_code=500,
            message="Failed to create agent",
            code="AGENT_CREATION_FAILED"
        )
    return ApiResponse.success(
        status_code=201,
        message="Agent created successfully",
        data=agent
    )

@router.get("")
async def get_all(current_user: Dict[str, Any] = Depends(get_current_user)):
    # Build filter context from user claims
    filter_data = {
        "role": current_user["role"],
        "userId": current_user["id"],
        "clientId": current_user["client_id"],
        "resellerId": current_user["reseller_id"]
    }
    agents = await agent_service.get_all_agents(filter_data)
    return ApiResponse.success(
        status_code=200,
        message="Agents retrieved successfully",
        data=agents
    )


@router.get("/{agent_id}")
async def get_one(agent_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    agent = await agent_service.get_agent_by_id(agent_id)
    if not agent:
        return ApiResponse.error(
            status_code=404,
            message="Agent not found",
            code="AGENT_NOT_FOUND"
        )
    return ApiResponse.success(
        status_code=200,
        message="Agent retrieved successfully",
        data=agent
    )


@router.patch("/{agent_id}")
async def update(agent_id: str, req_body: UpdateAgentRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    agent = await agent_service.get_agent_by_id(agent_id)
    if not agent:
        return ApiResponse.error(
            status_code=404,
            message="Agent not found",
            code="AGENT_NOT_FOUND"
        )

    # Filter only configuration detail fields for update_agent_details
    detail_fields = {"name", "useCase", "activityDescription", "callType", "voiceName", "voiceGender", "ttsProvider", "ttsModel", "ttsVoiceId", "ttsVoiceName", "guardrails", "customGuardrails", "knowledgeItems", "toolIds"}
    update_data = req_body.model_dump(exclude_unset=True)
    details_to_update = {k: v for k, v in update_data.items() if k in detail_fields}
    print("DEBUG DETAILS TO UPDATE:", details_to_update)

    if details_to_update:
        agent = await agent_service.update_agent_details(agent_id, details_to_update)

    if req_body.status:
        agent = await agent_service.update_agent_status(agent_id, req_body.status)

    if req_body.resellerIds is not None or req_body.clientIds is not None:
        agent = await agent_service.update_agent_assignments(agent_id, req_body.resellerIds, req_body.clientIds)

    return ApiResponse.success(
        status_code=200,
        message="Agent updated successfully",
        data=agent
    )


ELEVENLABS_MODELS = [
    {"id": "eleven_multilingual_v2", "name": "Multilingual v2 (Recommended)"},
    {"id": "eleven_flash_v2_5", "name": "Flash v2.5 (Ultra Fast)"},
    {"id": "eleven_flash_v2", "name": "Flash v2"},
    {"id": "eleven_turbo_v2_5", "name": "Turbo v2.5 (Lowest Latency)"},
    {"id": "eleven_turbo_v2", "name": "Turbo v2"},
]

CARTESIA_MODELS = [
    {"id": "sonic-3", "name": "Sonic 3"},
]

_voice_cache: Dict[str, Any] = {
    "data": None,
    "timestamp": 0.0,
}

_cartesia_voice_cache: Dict[str, Any] = {
    "data": None,
    "timestamp": 0.0,
}

# Cartesia REST voice catalog. `Cartesia-Version` selects the API spec version;
# the parser tolerates both the paged `{data, has_more, next_page}` shape and the
# legacy bare-array shape so the header value is the single tuning point if an
# account requires an older spec date.
_CARTESIA_API_VERSION = "2026-03-01"
_CARTESIA_VOICES_URL = "https://api.cartesia.ai/voices"


def _normalize_cartesia_gender(gender: Optional[str]) -> str:
    g = str(gender or "").strip().lower()
    if g in ("masculine", "male"):
        return "male"
    if g in ("gender_neutral", "non-binary", "neutral"):
        return "non-binary"
    return "female"


async def _fetch_cartesia_voices(api_key: str) -> Dict[str, Any]:
    """
    Fetch the Cartesia voice catalog via the REST /voices API.

    Returns a payload dict (provider/status/errorMessage/hasApiKey/voices/models)
    matching the FE voice-selector contract. The API key is never exposed and
    voices are normalized into the same shape as the ElevenLabs catalog.
    """
    headers: Dict[str, str] = {
        "Authorization": f"Bearer {api_key}",
        "Cartesia-Version": _CARTESIA_API_VERSION,
    }
    voices_list: List[Dict[str, Any]] = []
    starting_after: Optional[str] = None

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Bounded pagination: max 10 pages to avoid infinite loops
        for _ in range(10):
            params: Dict[str, Any] = {"limit": 100}
            if starting_after:
                params["starting_after"] = starting_after
            res = await client.get(_CARTESIA_VOICES_URL, params=params, headers=headers)

            if res.status_code in (401, 403):
                error_detail = (res.json() or {}).get("message", res.text) if res.text else res.text
                logger.warning(
                    f"Cartesia voice catalog auth error (HTTP {res.status_code}): {error_detail}"
                )
                return {
                    "provider": "cartesia",
                    "status": "auth_error",
                    "errorMessage": "Cartesia API authentication/permission error. "
                    f"(HTTP {res.status_code})",
                    "hasApiKey": True,
                    "voices": [],
                    "models": CARTESIA_MODELS,
                }

            if res.status_code == 429:
                logger.warning("Cartesia voice catalog rate limited (HTTP 429)")
                return {
                    "provider": "cartesia",
                    "status": "rate_limited",
                    "errorMessage": "Cartesia API rate limit exceeded. Please try again later.",
                    "hasApiKey": True,
                    "voices": [],
                    "models": CARTESIA_MODELS,
                }

            if res.status_code != 200:
                logger.warning(
                    f"Cartesia voice catalog error (HTTP {res.status_code}): {res.text[:300]}"
                )
                return {
                    "provider": "cartesia",
                    "status": "provider_error",
                    "errorMessage": f"Cartesia API returned HTTP {res.status_code}.",
                    "hasApiKey": True,
                    "voices": [],
                    "models": CARTESIA_MODELS,
                }

            data = res.json()
            if isinstance(data, dict) and isinstance(data.get("data"), list):
                items = data["data"]
                has_more = bool(data.get("has_more"))
            elif isinstance(data, list):
                items = data
                has_more = False
            else:
                items = []
                has_more = False

            for v in items:
                if not isinstance(v, dict):
                    continue
                vid = v.get("id")
                if not vid:
                    continue
                name = v.get("name") or vid
                gender = _normalize_cartesia_gender(v.get("gender"))
                description = v.get("description") or v.get("tagline") or ""
                language = v.get("language")
                locales = v.get("locales")
                if not language and isinstance(locales, list) and locales and isinstance(locales[0], dict):
                    language = locales[0].get("locale")
                is_custom = bool(v.get("is_owner"))
                voices_list.append({
                    "voice_id": vid,
                    "name": name,
                    "gender": gender,
                    "category": "custom" if is_custom else "premade",
                    "accent": v.get("country") or "",
                    "description": description,
                    "preview_url": v.get("preview_file_url"),
                    "is_custom": is_custom,
                    "language": language,
                })

            if not has_more or not items:
                break
            starting_after = items[-1].get("id") if isinstance(items[-1], dict) else None
            if not starting_after:
                break

    return {
        "provider": "cartesia",
        "status": "success" if voices_list else "empty",
        "errorMessage": None if voices_list else "No Cartesia voices found for this account.",
        "hasApiKey": True,
        "voices": voices_list,
        "models": CARTESIA_MODELS,
    }


async def _fetch_elevenlabs_voices(
    api_key: str,
    search: Optional[str] = None,
    page_size: Optional[int] = 30,
    next_page_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fetch ElevenLabs voices via the v2 catalog API with bounded pagination.

    Returns a payload dict (provider/status/errorMessage/hasApiKey/voices/models)
    matching the FE voice-selector contract. The API key is never exposed.
    """
    page_size = max(1, min(int(page_size if page_size else 30), 100))
    voices_list: List[Dict[str, Any]] = []
    params: Dict[str, Any] = {"page_size": page_size}
    if search:
        params["search"] = search.strip()
    if next_page_token:
        params["next_page_token"] = next_page_token

    async with httpx.AsyncClient(timeout=10.0) as client:
        headers: Dict[str, str] = {"xi-api-key": api_key}
        # Bounded pagination: max 10 pages to avoid infinite loops
        for _ in range(10):
            res = await client.get(
                "https://api.elevenlabs.io/v2/voices",
                params=params,
                headers=headers,
            )

            if res.status_code in (401, 403):
                error_detail = ""
                try:
                    error_detail = res.json().get("detail", {}).get("message", res.text)
                except Exception:
                    error_detail = res.text
                logger.warning(
                    f"ElevenLabs voice catalog auth error (HTTP {res.status_code}): {error_detail}"
                )
                return {
                    "provider": "elevenlabs",
                    "status": "auth_error",
                    "errorMessage": "ElevenLabs API authentication/permission error. "
                    f"(HTTP {res.status_code})",
                    "hasApiKey": True,
                    "voices": [],
                    "models": ELEVENLABS_MODELS,
                }

            if res.status_code == 429:
                logger.warning("ElevenLabs voice catalog rate limited (HTTP 429)")
                return {
                    "provider": "elevenlabs",
                    "status": "rate_limited",
                    "errorMessage": "ElevenLabs API rate limit exceeded. Please try again later.",
                    "hasApiKey": True,
                    "voices": [],
                    "models": ELEVENLABS_MODELS,
                }

            if res.status_code != 200:
                logger.warning(
                    f"ElevenLabs voice catalog error (HTTP {res.status_code}): {res.text[:300]}"
                )
                return {
                    "provider": "elevenlabs",
                    "status": "provider_error",
                    "errorMessage": f"ElevenLabs API returned HTTP {res.status_code}.",
                    "hasApiKey": True,
                    "voices": [],
                    "models": ELEVENLABS_MODELS,
                }

            data = res.json()
            for v in data.get("voices", []) or []:
                labels = v.get("labels") or {}
                gender = str(labels.get("gender") or "").strip().lower()
                if gender not in ("male", "female", "non-binary"):
                    gender = "female" if "female" in str(v.get("name", "")).lower() else "male"
                accent = labels.get("accent")
                accent = accent if isinstance(accent, str) and accent else "american"
                voices_list.append({
                    "voice_id": v.get("voice_id"),
                    "name": v.get("name"),
                    "gender": gender,
                    "category": v.get("category", "premade"),
                    "accent": accent,
                    "description": labels.get("description")
                    or labels.get("use_case")
                    or f"{accent.capitalize()} {gender} voice",
                    "preview_url": v.get("preview_url"),
                    "is_custom": v.get("category") not in ("premade", "high_quality"),
                })

            has_more = bool(data.get("has_more"))
            token = data.get("next_page_token")
            if not has_more or not token:
                break
            params["next_page_token"] = token

    return {
        "provider": "elevenlabs",
        "status": "success" if voices_list else "empty",
        "errorMessage": None if voices_list else "No voices found in ElevenLabs account.",
        "hasApiKey": True,
        "voices": voices_list,
        "models": ELEVENLABS_MODELS,
    }


@router.get("/tts/catalog")
@router.get("/elevenlabs/voices")
async def get_tts_voices(
    provider: str = "elevenlabs",
    search: Optional[str] = None,
    page_size: Optional[int] = 30,
    next_page_token: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Fetch TTS voices dynamically for the specified provider (elevenlabs | cartesia)
    with explicit error and availability states, v2 catalog pagination and caching.
    """
    prov = (provider or "elevenlabs").strip().lower()

    if prov == "cartesia":
        settings = get_settings()
        api_key = getattr(settings, "cartesia_api_key", None)

        if not api_key or api_key == "your_cartesia_api_key_here":
            return ApiResponse.success(
                status_code=200,
                message="CARTESIA_API_KEY is not configured",
                data={
                    "provider": "cartesia",
                    "status": "key_missing",
                    "errorMessage": "CARTESIA_API_KEY is not configured on the backend server.",
                    "hasApiKey": False,
                    "voices": [],
                    "models": CARTESIA_MODELS,
                }
            )

        # In-memory cache (5 minute TTL) for the default catalog request only
        can_cache = not (search or next_page_token)
        now = time.time()
        cached_data = _cartesia_voice_cache.get("data")
        if can_cache and cached_data and (now - _cartesia_voice_cache.get("timestamp", 0.0)) < 300:
            return ApiResponse.success(
                status_code=200,
                message="Cartesia voices retrieved from cache",
                data=cached_data,
            )

        try:
            payload = await _fetch_cartesia_voices(str(api_key))
            if can_cache:
                _cartesia_voice_cache["data"] = payload
                _cartesia_voice_cache["timestamp"] = now
            return ApiResponse.success(
                status_code=200,
                message="Cartesia voices retrieved successfully",
                data=payload,
            )
        except Exception as e:
            logger.warning(f"Could not fetch dynamic Cartesia voices: {e}")
            return ApiResponse.success(
                status_code=200,
                message=f"Could not fetch dynamic Cartesia voices: {e}",
                data={
                    "provider": "cartesia",
                    "status": "provider_error",
                    "errorMessage": f"Connection error: {e}",
                    "hasApiKey": True,
                    "voices": [],
                    "models": CARTESIA_MODELS,
                }
            )

    settings = get_settings()
    api_key = getattr(settings, "elevenlabs_api_key", None)

    if not api_key or api_key == "YOUR_ELEVENLABS_API_KEY":
        return ApiResponse.success(
            status_code=200,
            message="ELEVENLABS_API_KEY is not configured",
            data={
                "provider": "elevenlabs",
                "status": "key_missing",
                "errorMessage": "ELEVENLABS_API_KEY is not configured on the backend server.",
                "hasApiKey": False,
                "voices": [],
                "models": ELEVENLABS_MODELS,
            }
        )

    # In-memory cache (5 minute TTL) for the default catalog request only
    can_cache = not (search or next_page_token)
    now = time.time()
    cached_data = _voice_cache.get("data")
    if can_cache and cached_data and (now - _voice_cache.get("timestamp", 0.0)) < 300:
        return ApiResponse.success(
            status_code=200,
            message="ElevenLabs voices retrieved from cache",
            data=cached_data,
        )

    try:
        payload = await _fetch_elevenlabs_voices(
            api_key=str(api_key),
            search=search,
            page_size=page_size,
            next_page_token=next_page_token,
        )
        if can_cache:
            _voice_cache["data"] = payload
            _voice_cache["timestamp"] = now
        return ApiResponse.success(
            status_code=200,
            message="ElevenLabs voices retrieved successfully",
            data=payload,
        )
    except Exception as e:
        logger.warning(f"Could not fetch dynamic ElevenLabs voices: {e}")
        return ApiResponse.success(
            status_code=200,
            message=f"Could not fetch dynamic ElevenLabs voices: {e}",
            data={
                "provider": "elevenlabs",
                "status": "provider_error",
                "errorMessage": f"Connection error: {e}",
                "hasApiKey": True,
                "voices": [],
                "models": ELEVENLABS_MODELS,
            }
        )


@router.post("/elevenlabs/preview")
async def preview_elevenlabs_voice(
    req: PreviewVoiceRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Generate live audio TTS preview using ElevenLabs API.
    """
    settings = get_settings()
    api_key = getattr(settings, "elevenlabs_api_key", None)
    
    if not api_key or api_key == "YOUR_ELEVENLABS_API_KEY":
        return ApiResponse.error(
            status_code=400,
            message="ELEVENLABS_API_KEY is not configured on the backend server.",
            code="ELEVENLABS_KEY_MISSING"
        )
    
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{req.voiceId}"
        headers: dict[str, str] = {
            "xi-api-key": str(api_key),
            "Content-Type": "application/json"
        }
        payload = {
            "text": req.text or "Hello! I am your AI voice assistant. How can I help you today?",
            "model_id": req.modelId,
            "voice_settings": {
                "stability": req.stability if req.stability is not None else 0.5,
                "similarity_boost": req.similarityBoost if req.similarityBoost is not None else 0.75
            }
        }
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                logger.error(f"ElevenLabs TTS preview error {resp.status_code}: {resp.text}")
                return ApiResponse.error(
                    status_code=resp.status_code,
                    message=f"ElevenLabs API error: {resp.text}",
                    code="ELEVENLABS_API_ERROR"
                )
            
            return Response(content=resp.content, media_type="audio/mpeg")
    except Exception as e:
        logger.error(f"Failed to generate ElevenLabs voice preview: {e}")
        return ApiResponse.error(
            status_code=500,
            message=f"Failed to generate voice preview: {str(e)}",
            code="PREVIEW_GENERATION_FAILED"
        )



