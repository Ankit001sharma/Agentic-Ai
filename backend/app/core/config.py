"""Centralized configuration loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.llm.vllm_url import normalize_openai_compatible_base


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Auth
    sentinel_api_key: str = Field(default="demo-key", alias="SENTINEL_API_KEY")

    # vLLM (primary LLM backend; OpenAI-compatible)
    vllm_base_url: str = Field(
        default="https://miniorangeai.miniorange.in",
        alias="VLLM_BASE_URL",
        description="OpenAI-compatible base (no /v1 suffix). Use http://host:8000 or https://host.",
    )
    vllm_api_key: str = Field(
        default="",
        alias="VLLM_API_KEY",
        description="Optional; omit if the upstream LLM requires no key.",
    )
    vllm_judge_model: str = Field(
        default="nvidia/nemotron-3-nano", alias="VLLM_JUDGE_MODEL"
    )
    vllm_planner_model: str = Field(
        default="nvidia/nemotron-3-nano",
        alias="VLLM_PLANNER_MODEL",
        description="Default LLM used by the planner / Stage 8 / generic vLLM completions.",
    )
    vllm_assistant_model: str = Field(
        default="",
        alias="VLLM_ASSISTANT_MODEL",
        description="Optional override for the assistant role (falls back to planner).",
    )
    vllm_critic_model: str = Field(
        default="",
        alias="VLLM_CRITIC_MODEL",
        description="Optional override for the critic role (falls back to judge / planner).",
    )
    vllm_vision_model: str | None = Field(default=None, alias="VLLM_VISION_MODEL")
    vllm_tool_calling_mode: str = Field(default="auto", alias="VLLM_TOOL_CALLING_MODE")
    allow_cloud_fallback: bool = Field(default=False, alias="ALLOW_CLOUD_FALLBACK")

    # Intent LLM — Stage 5 (optional separate base URL for a smaller/faster model)
    vllm_intent_model: str | None = Field(
        default=None,
        alias="VLLM_INTENT_MODEL",
        description="If unset, falls back to mistral_model",
    )
    vllm_intent_base_url: str | None = Field(
        default=None,
        alias="VLLM_INTENT_BASE_URL",
        description="If unset, uses VLLM_BASE_URL",
    )

    @field_validator("vllm_base_url", mode="before")
    @classmethod
    def _normalize_vllm_base_url(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        return normalize_openai_compatible_base(v)

    @field_validator("vllm_intent_base_url", mode="before")
    @classmethod
    def _normalize_vllm_intent_base_url(cls, v: object) -> object:
        if v is None:
            return None
        if not isinstance(v, str):
            return v
        s = v.strip()
        if not s:
            return None
        return normalize_openai_compatible_base(s)

    intent_max_tokens: int = Field(default=128, alias="INTENT_MAX_TOKENS")
    intent_llm_timeout: float = Field(default=3.0, alias="INTENT_LLM_TIMEOUT")
    intent_prompt_max_chars: int = Field(default=2048, alias="INTENT_PROMPT_MAX_CHARS")
    intent_temperature: float = Field(default=0.0, alias="INTENT_TEMPERATURE")

    # Groq cloud (https://console.groq.com/keys — set this to use Groq instead of vLLM)
    groq_api_key: str = Field(
        default="",
        alias="GROQ_API_KEY",
        description=(
            "Groq cloud API key (https://console.groq.com/keys). When set, Groq takes "
            "priority over vLLM for all LLM calls. Set GROQ_MODEL / GROQ_INTENT_MODEL to "
            "choose which Groq model to use."
        ),
    )
    groq_model: str = Field(
        default="groq/llama-3.3-70b-versatile",
        alias="GROQ_MODEL",
        description="Primary Groq model for completions, Stage 8 function calls, and Stage 14 responses.",
    )
    groq_intent_model: str = Field(
        default="groq/llama3-8b-8192",
        alias="GROQ_INTENT_MODEL",
        description="Fast Groq model for Stage 5 intent extraction (lower latency small model).",
    )

    # Cloud fallbacks (used only if ALLOW_CLOUD_FALLBACK=true)
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    mistral_api_key: str = Field(
        default="",
        alias="MISTRAL_API_KEY",
        description=(
            "Mistral cloud API key (https://console.mistral.ai/api-keys). When set, "
            "Stage 5 routes intent extraction to the Mistral cloud using MISTRAL_MODEL "
            "(e.g. mistral/mistral-small-latest)."
        ),
    )
    default_model: str = Field(default="gpt-4o-mini", alias="DEFAULT_MODEL")

    # Storage
    database_url: str = Field(
        default="postgresql+asyncpg://sentinel:sentinel@localhost:5432/sentinelguard",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # OPA
    opa_url: str = Field(default="http://localhost:8181", alias="OPA_URL")

    # SIEM
    siem_webhook_url: str = Field(default="", alias="SIEM_WEBHOOK_URL")

    # Risk thresholds (0–100)
    risk_allow_max: int = Field(default=30, alias="RISK_ALLOW_MAX")
    risk_mask_max: int = Field(default=70, alias="RISK_MASK_MAX")
    risk_escalate_max: int = Field(default=90, alias="RISK_ESCALATE_MAX")

    # HITL (Stage 10 human review)
    review_timeout_seconds: int = Field(default=30, alias="REVIEW_TIMEOUT_SECONDS")
    high_impact_review_timeout: int = Field(default=300, alias="HIGH_IMPACT_REVIEW_TIMEOUT")

    # Code sandbox (Stage 11 — internal only)
    code_sandbox_url: str = Field(
        default="http://code-sandbox:8888", alias="CODE_SANDBOX_URL"
    )

    # Web search (Stage 11 — optional; stub if unset)
    web_search_url: str = Field(default="", alias="WEB_SEARCH_URL")

    # Frontend allowed origins
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")

    # Vision enrichment (pre-scan attachment processing)
    vision_describe_enabled: bool = Field(default=True, alias="VISION_DESCRIBE_ENABLED")
    vision_model: str = Field(default="", alias="VISION_MODEL")
    vision_timeout: float = Field(default=20.0, alias="VISION_TIMEOUT")
    vision_max_tokens: int = Field(default=400, alias="VISION_MAX_TOKENS")

    # Config YAML paths (relative to backend working directory)
    tools_yaml_path: str = Field(default="tools.yaml", alias="TOOLS_YAML_PATH")
    risk_yaml_path: str = Field(default="risk.yaml", alias="RISK_YAML_PATH")

    # Mistral intent model (Stage 5)
    mistral_model: str = Field(
        default="mistral/mistral-small-latest",
        alias="MISTRAL_MODEL",
        description=(
            "LiteLLM model string for Stage 5 intent detector. For Mistral cloud use "
            "mistral/<model> (e.g. mistral/mistral-small-latest, mistral/open-mistral-7b)."
        ),
    )
    mistral_base_url: str | None = Field(
        default=None,
        alias="MISTRAL_BASE_URL",
        description="Optional custom base URL for self-hosted Mistral. Cloud Mistral does NOT need this.",
    )
    mistral_timeout: float = Field(default=15.0, alias="MISTRAL_TIMEOUT")
    mistral_max_tokens: int = Field(default=256, alias="MISTRAL_MAX_TOKENS")

    # Nemotron function-call model (Stage 8)
    nemotron_model: str = Field(
        default="nvidia/nemotron-mini-4b-instruct",
        alias="NEMOTRON_MODEL",
        description="LiteLLM model string for Stage 8 function-call generator",
    )
    nemotron_timeout: float = Field(default=15.0, alias="NEMOTRON_TIMEOUT")
    nemotron_max_tokens: int = Field(default=512, alias="NEMOTRON_MAX_TOKENS")

    # Short-term memory / Redis STM (Stage 1)
    stm_ttl_seconds: int = Field(default=1800, alias="STM_TTL_SECONDS")  # 30 min
    stm_max_turns: int = Field(default=5, alias="STM_MAX_TURNS")

    # MiniOrange knowledge-base tool (Stage 11 — optional)
    miniorange_data_dir: str = Field(
        default="",
        alias="MINIORANGE_DATA_DIR",
        description="Absolute path to directory containing miniorange_docs.json and guides.json. Synthesis uses the configured vLLM endpoint (no separate API key needed).",
    )

    # External tool API keys (Stage 11)
    resend_api_key: str = Field(default="", alias="RESEND_API_KEY")
    resend_from_email: str = Field(default="noreply@example.com", alias="RESEND_FROM_EMAIL")
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    slack_bot_token: str = Field(default="", alias="SLACK_BOT_TOKEN")
    github_token: str = Field(default="", alias="GITHUB_TOKEN")

    # Tool execution timeouts (seconds)
    tool_default_timeout: float = Field(default=10.0, alias="TOOL_DEFAULT_TIMEOUT")
    tool_email_timeout: float = Field(default=10.0, alias="TOOL_EMAIL_TIMEOUT")
    tool_github_timeout: float = Field(default=15.0, alias="TOOL_GITHUB_TIMEOUT")
    tool_slack_timeout: float = Field(default=10.0, alias="TOOL_SLACK_TIMEOUT")
    tool_search_timeout: float = Field(default=30.0, alias="TOOL_SEARCH_TIMEOUT")

    # Qdrant (vector DB — jailbreak similarity + docs search)
    qdrant_url: str = Field(default="http://qdrant:6333", alias="QDRANT_URL")

    # Langfuse observability (optional)
    langfuse_enabled: bool = Field(default=False, alias="LANGFUSE_ENABLED")
    langfuse_public_key: str = Field(default="", alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(default="", alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(default="http://localhost:3001", alias="LANGFUSE_HOST")


@lru_cache
def get_settings() -> Settings:
    return Settings()
