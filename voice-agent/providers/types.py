"""
Provider platform types and data definitions.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ProviderCapability(str, Enum):
    STT = "stt"
    LLM = "llm"
    TTS = "tts"


class CredentialSource(str, Enum):
    PLATFORM = "platform"
    BYO = "byo"


@dataclass(frozen=True)
class ProviderDescriptor:
    capability: ProviderCapability
    provider: str
    supported_models: List[str] = field(default_factory=list)
    supported_options: List[str] = field(default_factory=list)
    supports_byo: bool = True


@dataclass(frozen=True)
class ResolvedProviderConfig:
    capability: ProviderCapability
    provider: str
    model: Optional[str] = None
    voice: Optional[str] = None
    credential_source: CredentialSource = CredentialSource.PLATFORM
    credential_id: Optional[str] = None
    safe_options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RealtimeModelBundle:
    """
    Call-scoped model instances and non-secret configuration metadata.
    Contains NO plaintext secrets or API keys.
    """
    stt: Any
    llm: Any
    tts: Any

    model_configuration_id: Optional[str] = None

    stt_provider: str = "deepgram"
    stt_model: Optional[str] = None
    stt_credential_source: str = "platform"

    llm_provider: str = "openai"
    llm_model: Optional[str] = None
    llm_credential_source: str = "platform"

    tts_provider: str = "openai"
    tts_model: Optional[str] = None
    tts_voice: Optional[str] = None
    tts_credential_source: str = "platform"

    def to_safe_metadata(self) -> Dict[str, Any]:
        """Convert to safe metadata dict for logging or WorkflowRun record."""
        return {
            "model_configuration_id": self.model_configuration_id,
            "stt_provider": self.stt_provider,
            "stt_model": self.stt_model,
            "stt_credential_source": self.stt_credential_source,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "llm_credential_source": self.llm_credential_source,
            "tts_provider": self.tts_provider,
            "tts_model": self.tts_model,
            "tts_voice": self.tts_voice,
            "tts_credential_source": self.tts_credential_source,
        }
