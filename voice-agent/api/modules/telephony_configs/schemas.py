"""
Schemas for Telephony Configurations (Twilio & Vobiz).
"""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


# --- Provider Field Metadata Schemas ---

class ProviderFieldOption(BaseModel):
    label: str
    value: str


class VisibleWhenRule(BaseModel):
    field: str
    equals: Any


class ProviderFieldMetadata(BaseModel):
    name: str
    label: str
    type: Literal["text", "password", "textarea", "number", "boolean", "select"] = "text"
    required: bool = True
    sensitive: bool = False
    description: Optional[str] = None
    placeholder: Optional[str] = None
    section: Optional[str] = None
    options: Optional[List[ProviderFieldOption]] = None
    visible_when: Optional[VisibleWhenRule] = None


class TelephonyProviderMetadata(BaseModel):
    provider: str
    display_name: str
    docs_url: Optional[str] = None
    fields: List[ProviderFieldMetadata]


class TelephonyProviderMetadataResponse(BaseModel):
    providers: List[TelephonyProviderMetadata]


# --- Provider-specific Configuration Requests ---

class TwilioConfigurationRequest(BaseModel):
    provider: Literal["twilio"] = "twilio"
    account_sid: str = Field(..., description="Twilio Account SID")
    auth_token: str = Field(..., description="Twilio Auth Token")
    amd_enabled: bool = Field(default=False, description="Detect whether outbound calls are answered by a person or machine.")


class VobizConfigurationRequest(BaseModel):
    provider: Literal["vobiz"] = "vobiz"
    auth_id: str = Field(..., description="Vobiz Account ID")
    auth_token: str = Field(..., description="Vobiz Auth Token")
    application_id: Optional[str] = Field(default=None, description="Vobiz Application ID")


# --- Telephony Configuration CRUD Schemas ---

class TelephonyConfigurationCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    is_default_outbound: bool = False
    config: Dict[str, Any]


class TelephonyConfigurationUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    config: Optional[Dict[str, Any]] = None


class TelephonyConfigurationListItem(BaseModel):
    id: str
    name: str
    provider: str
    is_default_outbound: bool
    phone_number_count: int = 0
    created_at: str
    updated_at: str


class TelephonyConfigurationListResponse(BaseModel):
    configurations: List[TelephonyConfigurationListItem]


class TelephonyConfigurationDetail(BaseModel):
    id: str
    name: str
    provider: str
    is_default_outbound: bool
    credentials: Dict[str, Any]
    created_at: str
    updated_at: str


# --- Phone Number CRUD Schemas ---

class PhoneNumberCreateRequest(BaseModel):
    address: str = Field(..., min_length=1)
    address_type: str = Field(default="pstn")
    country_code: Optional[str] = None
    label: Optional[str] = None
    is_active: bool = True
    is_default_caller_id: bool = False
    inbound_agent_id: Optional[str] = None


class PhoneNumberUpdateRequest(BaseModel):
    address: Optional[str] = None
    address_type: Optional[str] = None
    country_code: Optional[str] = None
    label: Optional[str] = None
    is_active: Optional[bool] = None
    inbound_agent_id: Optional[str] = None


class PhoneNumberResponse(BaseModel):
    id: str
    telephony_configuration_id: str
    address: str
    address_type: str
    country_code: Optional[str] = None
    label: Optional[str] = None
    is_active: bool
    is_default_caller_id: bool
    inbound_agent_id: Optional[str] = None
    inbound_agent_name: Optional[str] = None
    created_at: str
    updated_at: str


class PhoneNumberListResponse(BaseModel):
    phone_numbers: List[PhoneNumberResponse]


class InitiateCallRequest(BaseModel):
    agent_id: Optional[str] = None
    phone_number: str
    telephony_configuration_id: Optional[str] = None
    from_phone_number_id: Optional[str] = None

