"""
Model configuration Pydantic schemas.
"""
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class CreateModelConfigRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    
    stt_provider: str = Field(default="deepgram")
    stt_model: Optional[str] = None
    stt_credential_source: str = Field(default="platform")
    stt_credential_id: Optional[str] = None
    stt_options: Dict[str, Any] = Field(default_factory=dict)
    
    llm_provider: str = Field(default="openai")
    llm_model: Optional[str] = None
    llm_credential_source: str = Field(default="platform")
    llm_credential_id: Optional[str] = None
    llm_options: Dict[str, Any] = Field(default_factory=dict)
    
    tts_provider: str = Field(default="openai")
    tts_model: Optional[str] = None
    tts_voice: Optional[str] = None
    tts_credential_source: str = Field(default="platform")
    tts_credential_id: Optional[str] = None
    tts_options: Dict[str, Any] = Field(default_factory=dict)


class UpdateModelConfigRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None
    
    stt_provider: Optional[str] = None
    stt_model: Optional[str] = None
    stt_credential_source: Optional[str] = None
    stt_credential_id: Optional[str] = None
    stt_options: Optional[Dict[str, Any]] = None
    
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_credential_source: Optional[str] = None
    llm_credential_id: Optional[str] = None
    llm_options: Optional[Dict[str, Any]] = None
    
    tts_provider: Optional[str] = None
    tts_model: Optional[str] = None
    tts_voice: Optional[str] = None
    tts_credential_source: Optional[str] = None
    tts_credential_id: Optional[str] = None
    tts_options: Optional[Dict[str, Any]] = None


class ModelConfigResponse(BaseModel):
    id: str
    client_id: str
    user_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    status: str
    
    stt_provider: str
    stt_model: Optional[str] = None
    stt_credential_source: str
    stt_credential_id: Optional[str] = None
    stt_options: Dict[str, Any]
    
    llm_provider: str
    llm_model: Optional[str] = None
    llm_credential_source: str
    llm_credential_id: Optional[str] = None
    llm_options: Dict[str, Any]
    
    tts_provider: str
    tts_model: Optional[str] = None
    tts_voice: Optional[str] = None
    tts_credential_source: str
    tts_credential_id: Optional[str] = None
    tts_options: Dict[str, Any]
    
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
