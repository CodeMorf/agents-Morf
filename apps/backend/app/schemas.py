import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(ORMModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_active: bool
    is_superuser: bool


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=160, pattern=r"^[a-z0-9-]+$")


class OrganizationOut(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    status: str
    plan: str
    timezone: str
    locale: str
    created_at: datetime


class AgentCreate(BaseModel):
    name: str
    description: str = ""
    system_prompt: str
    model: str | None = None
    provider_id: uuid.UUID | None = None
    temperature: Decimal = Decimal("0.30")
    max_tokens: int = 1200
    tools: dict[str, Any] = Field(default_factory=dict)


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    provider_id: uuid.UUID | None = None
    temperature: Decimal | None = None
    max_tokens: int | None = None
    enabled: bool | None = None
    tools: dict[str, Any] | None = None


class AgentOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str
    system_prompt: str
    model: str | None
    provider_id: uuid.UUID | None
    temperature: Decimal
    max_tokens: int
    enabled: bool
    tools: dict[str, Any]
    created_at: datetime


class ProviderCreate(BaseModel):
    name: str
    kind: Literal["openai_compatible", "gemini", "anthropic", "ollama"]
    base_url: str
    model: str
    api_key: str | None = None
    enabled: bool = True
    priority: int = 100
    settings: dict[str, Any] = Field(default_factory=dict)


class ProviderOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    kind: str
    base_url: str
    model: str
    enabled: bool
    priority: int
    settings: dict[str, Any]
    created_at: datetime


class LeadCreate(BaseModel):
    name: str
    email: EmailStr | None = None
    phone: str | None = None
    status: str = "new"
    score: int = Field(default=0, ge=0, le=100)
    source: str = "agent"
    notes: str = ""


class LeadOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    email: str | None
    phone: str | None
    status: str
    score: int
    source: str
    notes: str
    created_at: datetime


class ReservationCreate(BaseModel):
    customer_name: str
    customer_email: EmailStr | None = None
    customer_phone: str | None = None
    starts_at: datetime
    party_size: int = Field(default=1, ge=1, le=100)
    status: str = "requested"
    notes: str = ""


class ReservationOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    customer_name: str
    customer_email: str | None
    customer_phone: str | None
    starts_at: datetime
    party_size: int
    status: str
    notes: str
    created_at: datetime


class MenuItemCreate(BaseModel):
    name: str
    description: str = ""
    category: str = "general"
    price: Decimal = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    allergens: str = ""
    available: bool = True


class MenuItemOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str
    category: str
    price: Decimal
    currency: str
    allergens: str
    available: bool


class OrderCreate(BaseModel):
    customer_name: str
    customer_email: EmailStr | None = None
    customer_phone: str | None = None
    currency: str = "USD"
    items: list[dict[str, Any]] = Field(default_factory=list)
    notes: str = ""


class OrderOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    customer_name: str
    customer_email: str | None
    customer_phone: str | None
    status: str
    currency: str
    total: Decimal
    items: list[dict[str, Any]]
    notes: str
    created_at: datetime


class CallCreate(BaseModel):
    phone_number: str
    purpose: str
    script: str = ""
    provider: str = "unconfigured"


class CallOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    phone_number: str
    purpose: str
    script: str
    status: str
    provider: str
    external_id: str | None
    created_at: datetime


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    agent_id: uuid.UUID | None = None
    messages: list[ChatMessage]
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    conversation_id: uuid.UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[dict[str, Any]]
    usage: dict[str, int] = Field(default_factory=dict)
    provider: str
    conversation_id: uuid.UUID


class EmailTestRequest(BaseModel):
    to: EmailStr
    subject: str = "Agents Morf email test"
