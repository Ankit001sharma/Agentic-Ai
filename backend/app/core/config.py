"""Centralized configuration loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Auth
    sentinel_api_key: str = Field(default="demo-key", alias="SENTINEL_API_KEY")

    # vLLM (primary LLM brain; OpenAI-compatible)
    vllm_base_url: str = Field(default="http://localhost:8000/v1", alias="VLLM_BASE_URL")
    vllm_api_key: str = Field(default="EMPTY", alias="VLLM_API_KEY")
    vllm_planner_model: str = Field(
        default="meta-llama/Llama-3.1-8B-Instruct", alias="VLLM_PLANNER_MODEL"
    )
    vllm_assistant_model: str = Field(
        default="meta-llama/Llama-3.1-8B-Instruct", alias="VLLM_ASSISTANT_MODEL"
    )
    vllm_critic_model: str = Field(
        default="meta-llama/Llama-3.1-8B-Instruct", alias="VLLM_CRITIC_MODEL"
    )
    vllm_judge_model: str = Field(
        default="meta-llama/Llama-3.1-8B-Instruct", alias="VLLM_JUDGE_MODEL"
    )
    vllm_vision_model: str | None = Field(default=None, alias="VLLM_VISION_MODEL")
    vllm_tool_calling_mode: str = Field(default="auto", alias="VLLM_TOOL_CALLING_MODE")
    allow_cloud_fallback: bool = Field(default=False, alias="ALLOW_CLOUD_FALLBACK")

    # Legacy / cloud (optional; used only if allow_cloud_fallback is True)
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    default_model: str = Field(default="gpt-4o-mini", alias="DEFAULT_MODEL")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.1:8b", alias="OLLAMA_MODEL")

    # Agentic pipeline (v2)
    agentic_mode: bool = Field(default=True, alias="AGENTIC_MODE")
    max_supervisor_steps: int = Field(default=8, alias="MAX_SUPERVISOR_STEPS")
    supervisor_mode: str = Field(
        default="react_primary",
        alias="SUPERVISOR_MODE",
        description="react_primary (Nemotron-first) | legacy_parallel_crew",
    )
    agent_prescan: str = Field(
        default="full_threat",
        alias="AGENT_PRESCAN",
        description="full_threat | minimal | none — deterministic scan before LLM loop",
    )
    supervisor_max_steps: int = Field(default=16, alias="SUPERVISOR_MAX_STEPS")
    memory_recall_top_k: int = Field(default=5, alias="MEMORY_RECALL_TOP_K")
    max_reflections: int = Field(default=2, alias="MAX_REFLECTIONS")
    max_output_retries: int = Field(default=2, alias="MAX_OUTPUT_RETRIES")

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

    # Risk thresholds (0-100)
    risk_allow_max: int = Field(default=30, alias="RISK_ALLOW_MAX")
    risk_mask_max: int = Field(default=70, alias="RISK_MASK_MAX")
    risk_escalate_max: int = Field(default=90, alias="RISK_ESCALATE_MAX")

    # HITL
    review_timeout_seconds: int = Field(default=30, alias="REVIEW_TIMEOUT_SECONDS")

    # Code sandbox
    code_sandbox_url: str = Field(
        default="http://code-sandbox:8888", alias="CODE_SANDBOX_URL"
    )
    # Web search (optional; stub if unset)
    web_search_url: str = Field(default="", alias="WEB_SEARCH_URL")
    # Assistant workspace
    assistant_workspace: str = Field(
        default="/tmp/sentinel_assistant", alias="ASSISTANT_WORKSPACE"
    )

    # Frontend allowed origins
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")

    # Vision
    vision_describe_enabled: bool = Field(default=True, alias="VISION_DESCRIBE_ENABLED")
    vision_model: str = Field(default="", alias="VISION_MODEL")
    vision_timeout: float = Field(default=20.0, alias="VISION_TIMEOUT")
    vision_max_tokens: int = Field(default=400, alias="VISION_MAX_TOKENS")


@lru_cache
def get_settings() -> Settings:
    return Settings()
