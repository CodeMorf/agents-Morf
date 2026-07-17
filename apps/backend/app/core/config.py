from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Agents Morf"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    public_url: str = "http://localhost"
    secret_key: str = "development-secret-change-me"
    encryption_key: str | None = None
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    cors_origins: list[str] | str = Field(default_factory=lambda: ["http://localhost:5173"])

    database_url: str = "sqlite+aiosqlite:///./agents_morf.db"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "agents_morf_context"
    auto_create_schema: bool = True
    # Idempotent official catalog seed on API boot (safe; no per-tenant agents created).
    auto_seed_agent_templates: bool = True

    default_organization_name: str = "CodeMorf"
    default_provider: str = "groq"
    default_model: str = "llama-3.1-8b-instant"

    # Phase 2: public company self-registration (staging can enable; prod may disable)
    allow_public_registration: bool = True
    registration_default_plan: str = "trial"
    # When true (staging), forgot-password / invite responses may include one-time tokens
    # because outbound email is not wired yet. Never enable on public internet long-term.
    return_auth_tokens_in_response: bool = True
    password_reset_expire_minutes: int = 60
    invite_expire_hours: int = 72

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4.1-mini"
    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str | None = "llama-3.1-8b-instant"
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    anthropic_api_key: str | None = None
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_model: str = "claude-3-5-haiku-latest"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"

    # Hybrid routing: production chat never falls back to local Ollama by default.
    allow_local_chat_fallback: bool = False
    local_cpu_threshold_percent: float = 60.0
    local_inference_timeout_seconds: int = 25
    local_max_parallel_inferences: int = 1

    embedding_provider: Literal["ollama", "openai_compatible", "disabled"] = "ollama"
    embedding_base_url: str = "http://localhost:11434"
    embedding_api_key: str | None = None
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int | None = None

    grok_build_enabled: bool = False
    grok_build_binary: str = "grok"
    grok_build_cwd: str = "/workspace"
    grok_build_model: str = "grok-build"
    grok_build_timeout_seconds: int = 300

    memory_auto_extract: bool = True
    memory_max_context_chars: int = 6000
    knowledge_max_context_chars: int = 10000
    knowledge_max_file_bytes: int = 10_485_760
    training_max_examples: int = 6
    tool_max_rounds: int = 3
    tool_default_timeout_seconds: int = 30
    tool_allowed_hosts: list[str] | str = Field(default_factory=list)
    tool_allow_http: bool = False
    tool_allow_private_networks: bool = False
    # Platform web search (all agents). Uses DuckDuckGo by default (no key).
    web_search_enabled: bool = True
    web_search_max_results: int = 6
    web_fetch_enabled: bool = True
    web_fetch_max_chars: int = 8000

    @field_validator("cors_origins", "tool_allowed_hosts", mode="before")
    @classmethod
    def split_csv_values(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
