import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import MemoryKind, MemoryScope


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """Public company registration — creates organization + first owner."""

    organization_name: str = Field(min_length=2, max_length=160)
    organization_slug: str | None = Field(
        default=None,
        pattern=r"^[a-z0-9][a-z0-9-]{1,158}[a-z0-9]$",
        description="Optional. Auto-generated from organization_name when omitted.",
    )
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    full_name: str = Field(default="", max_length=160)
    timezone: str = "UTC"
    locale: str = "es"


class RegisterResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserOut"
    organization: "OrganizationOut"
    message: str = "Organization registered successfully"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str
    reset_token: str | None = None  # only when return_auth_tokens_in_response


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10)
    password: str = Field(min_length=12, max_length=128)


class AcceptInviteRequest(BaseModel):
    token: str = Field(min_length=10)
    password: str = Field(min_length=12, max_length=128)
    full_name: str = Field(default="", max_length=160)


class MemberInviteRequest(BaseModel):
    email: EmailStr
    role: Literal[
        "organization_admin",
        "developer",
        "operator",
        "viewer",
    ] = "developer"
    full_name: str = Field(default="", max_length=160)


class MemberRoleUpdate(BaseModel):
    role: Literal[
        "organization_owner",
        "organization_admin",
        "developer",
        "operator",
        "viewer",
    ]


class MemberOut(BaseModel):
    membership_id: uuid.UUID
    user_id: uuid.UUID
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class InviteOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    role: str
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    invite_token: str | None = None  # only on create when tokens returned


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(ORMModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_active: bool
    is_superuser: bool


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,158}[a-z0-9]$")
    plan: str = "trial"
    timezone: str = "UTC"
    locale: str = "en"


class OrganizationOut(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    status: str
    plan: str
    timezone: str
    locale: str
    settings: dict[str, Any]


class ProviderCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    kind: Literal["openai_compatible", "gemini", "anthropic", "ollama", "grok_build"]
    base_url: str = ""
    model: str = Field(min_length=1, max_length=160)
    api_key: str | None = None
    enabled: bool = True
    priority: int = 100
    settings: dict[str, Any] = Field(default_factory=dict)


class ProviderOut(ORMModel):
    id: uuid.UUID
    name: str
    kind: str
    base_url: str
    model: str
    enabled: bool
    priority: int
    settings: dict[str, Any]


class AgentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,158}[a-z0-9]$")
    description: str = ""
    system_prompt: str = Field(min_length=10)
    instructions: str = ""
    provider_id: uuid.UUID | None = None
    model: str | None = None
    temperature: Decimal = Field(default=Decimal("0.30"), ge=0, le=2)
    max_tokens: int = Field(default=1200, ge=64, le=128000)
    enabled: bool = True
    memory_enabled: bool = True
    memory_top_k: int = Field(default=8, ge=0, le=30)
    knowledge_enabled: bool = True
    auto_tool_execution: bool = False
    tool_approval_mode: Literal["caller", "always", "never"] = "caller"
    settings: dict[str, Any] = Field(default_factory=dict)


class AgentUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    instructions: str | None = None
    provider_id: uuid.UUID | None = None
    model: str | None = None
    temperature: Decimal | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=64, le=128000)
    enabled: bool | None = None
    memory_enabled: bool | None = None
    memory_top_k: int | None = Field(default=None, ge=0, le=30)
    knowledge_enabled: bool | None = None
    auto_tool_execution: bool | None = None
    tool_approval_mode: Literal["caller", "always", "never"] | None = None
    settings: dict[str, Any] | None = None


class AgentOut(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str
    system_prompt: str
    instructions: str
    provider_id: uuid.UUID | None
    model: str | None
    temperature: Decimal
    max_tokens: int
    enabled: bool
    memory_enabled: bool
    memory_top_k: int
    knowledge_enabled: bool
    auto_tool_execution: bool
    tool_approval_mode: str
    current_version: int
    settings: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AgentVersionOut(ORMModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    version: int
    label: str
    snapshot: dict[str, Any]
    published: bool
    created_at: datetime


class ToolCreate(BaseModel):
    name: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_.-]{1,119}$")
    description: str = ""
    transport: Literal["http", "client"] = "http"
    execution_mode: Literal["client", "server"] = "client"
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "POST"
    url: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    credentials: str | None = None
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    requires_approval: bool = True
    enabled: bool = True
    settings: dict[str, Any] = Field(default_factory=dict)


class ToolOut(ORMModel):
    id: uuid.UUID
    name: str
    description: str
    transport: str
    execution_mode: str
    method: str
    url: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    headers: dict[str, Any]
    timeout_seconds: int
    requires_approval: bool
    enabled: bool
    settings: dict[str, Any]


class AgentToolLink(BaseModel):
    tool_id: uuid.UUID
    enabled: bool = True


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]
    execution_mode: str = "client"
    requires_approval: bool = True
    status: str = "pending"


class ToolExecutionOut(ORMModel):
    id: uuid.UUID
    tool_id: uuid.UUID | None
    conversation_id: uuid.UUID | None
    status: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    error: str
    latency_ms: int
    created_at: datetime


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = ""
    enabled: bool = True
    settings: dict[str, Any] = Field(default_factory=dict)


class KnowledgeBaseOut(ORMModel):
    id: uuid.UUID
    name: str
    description: str
    enabled: bool
    settings: dict[str, Any]
    created_at: datetime


class DocumentTextCreate(BaseModel):
    title: str = Field(min_length=1, max_length=260)
    content: str = Field(min_length=1)
    source_type: str = "text"
    mime_type: str = "text/plain"
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentOut(ORMModel):
    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    title: str
    source_type: str
    mime_type: str
    status: str
    chunk_count: int
    error: str
    metadata_json: dict[str, Any]
    created_at: datetime


class MemoryCreate(BaseModel):
    agent_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    end_user_id: str | None = Field(default=None, max_length=200)
    scope: MemoryScope = MemoryScope.agent
    kind: MemoryKind = MemoryKind.fact
    key: str = Field(default="", max_length=220)
    content: str = Field(min_length=1)
    importance: float = Field(default=0.5, ge=0, le=1)
    tags: list[str] = Field(default_factory=list)
    source: str = "manual"
    expires_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryOut(ORMModel):
    id: uuid.UUID
    agent_id: uuid.UUID | None
    conversation_id: uuid.UUID | None
    end_user_id: str | None
    scope: MemoryScope
    kind: MemoryKind
    key: str
    content: str
    importance: float
    tags: list[str]
    source: str
    active: bool
    expires_at: datetime | None
    metadata_json: dict[str, Any]
    created_at: datetime


class MemorySearchRequest(BaseModel):
    query: str = Field(min_length=1)
    agent_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    end_user_id: str | None = None
    limit: int = Field(default=8, ge=1, le=30)


class TrainingDatasetCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = ""


class TrainingDatasetOut(ORMModel):
    id: uuid.UUID
    name: str
    description: str
    status: str
    created_at: datetime


class TrainingExampleCreate(BaseModel):
    agent_id: uuid.UUID | None = None
    input_text: str = Field(min_length=1)
    expected_output: str = Field(min_length=1)
    context: str = ""
    tags: list[str] = Field(default_factory=list)
    weight: float = Field(default=1.0, ge=0.1, le=10)
    enabled: bool = True


class TrainingExampleOut(ORMModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    agent_id: uuid.UUID | None
    input_text: str
    expected_output: str
    context: str
    tags: list[str]
    weight: float
    enabled: bool
    created_at: datetime


class EvaluationRequest(BaseModel):
    agent_id: uuid.UUID
    dataset_id: uuid.UUID
    limit: int = Field(default=20, ge=1, le=100)


class FeedbackCreate(BaseModel):
    agent_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    message_id: uuid.UUID | None = None
    end_user_id: str | None = Field(default=None, max_length=200)
    rating: int = Field(default=0, ge=-1, le=1)
    category: str = Field(default="general", max_length=80)
    comment: str = Field(default="", max_length=5000)
    correction: str = Field(default="", max_length=20000)
    source: str = Field(default="api", max_length=80)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FeedbackOut(ORMModel):
    id: uuid.UUID
    agent_id: uuid.UUID | None
    conversation_id: uuid.UUID | None
    message_id: uuid.UUID | None
    end_user_id: str | None
    rating: int
    category: str
    comment: str
    correction: str
    source: str
    promoted_to_training: bool
    metadata_json: dict[str, Any]
    created_at: datetime


class FeedbackPromoteRequest(BaseModel):
    dataset_id: uuid.UUID | None = None
    input_text: str | None = Field(default=None, max_length=20000)
    tags: list[str] = Field(default_factory=lambda: ["feedback", "correction"])


API_KEY_SCOPES = (
    "chat:write",
    "feedback:write",
    "agents:read",
    "memory:write",
    "knowledge:read",
    "*",
)


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    scopes: list[str] = Field(default_factory=lambda: ["chat:write", "feedback:write"])
    expires_at: datetime | None = None


class ApiKeyCreated(BaseModel):
    id: uuid.UUID
    name: str
    key: str
    prefix: str
    scopes: list[str]
    expires_at: datetime | None


class ApiKeyOut(ORMModel):
    id: uuid.UUID
    name: str
    prefix: str
    scopes: list[str]
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None
    tool_call_id: str | None = None


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    agent_id: uuid.UUID | None = None
    agent: str | None = None
    messages: list[ChatMessage] = Field(min_length=1)
    conversation_id: uuid.UUID | None = None
    external_conversation_id: str | None = None
    end_user_id: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=128000)
    stream: bool = False
    remember: bool = True
    force_local: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatChoiceMessage(BaseModel):
    role: str = "assistant"
    content: str
    tool_calls: list[ToolCall] = Field(default_factory=list)


class ChatChoice(BaseModel):
    index: int = 0
    message: ChatChoiceMessage
    finish_reason: str = "stop"


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    provider: str
    conversation_id: uuid.UUID
    assistant_message_id: uuid.UUID
    choices: list[ChatChoice]
    usage: dict[str, Any] = Field(default_factory=dict)
    memory_hits: int = 0
    knowledge_hits: int = 0
    request_id: str = ""
    latency_ms: int = 0
    fallback_used: bool = False
    provider_errors: list[str] = Field(default_factory=list)
