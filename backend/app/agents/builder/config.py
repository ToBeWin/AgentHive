"""Builder config schema — declarative Agent configuration authored by tenants.

Mirrors the shape documented in AGENTS.md §7.6 (low-code Agent Builder). The
schema is intentionally permissive on optional fields so the validator can
attach helpful issues instead of crashing on partial configs.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class ResponseStyle(str, Enum):
    FORMAL = "formal"
    FRIENDLY = "friendly"
    CONCISE = "concise"


class SupportedLanguage(str, Enum):
    ZH = "zh"
    EN = "en"
    AUTO = "auto"


class AgentBuilderConfigIssueSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


class AgentBuilderConfig(BaseModel):
    """Declarative configuration for a low-code Agent."""

    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    avatar_url: str | None = Field(default=None, max_length=500)

    # LLM routing — primary + fallback chain. ``deployment_id`` is the
    # canonical reference; ``model_key`` / ``routing_key`` are kept for
    # backwards-compatibility with configs authored before deployments
    # existed.
    deployment_id: UUID | None = None
    fallback_deployment_ids: list[UUID] = Field(default_factory=list)
    model_key: str | None = Field(default=None, max_length=120)
    routing_key: str | None = Field(default=None, max_length=120)

    # Generation parameters. ``None`` means "inherit policy default".
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=8192)
    max_cost_per_request: float | None = Field(default=None, ge=0.0)

    # Persona & behaviour.
    system_prompt: str = Field(min_length=1, max_length=8000)
    response_style: ResponseStyle = ResponseStyle.FORMAL
    language: SupportedLanguage = SupportedLanguage.AUTO

    # Bound resources.
    knowledge_base_ids: list[UUID] = Field(default_factory=list)
    mcp_server_keys: list[str] = Field(default_factory=list)

    # Escalation / safety.
    confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    escalation_message: str | None = Field(default=None, max_length=1000)
    greeting_message: str | None = Field(default=None, max_length=2000)
    fallback_message: str | None = Field(default=None, max_length=2000)

    # Free-form metadata surfaced to the runtime (tags, owner hints, etc.).
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _ensure_routing_target(self) -> AgentBuilderConfig:
        if self.deployment_id is None and not self.model_key and not self.routing_key:
            raise ValueError(
                "At least one of deployment_id, model_key, or routing_key must be set."
            )
        if self.confidence_threshold is not None and not self.escalation_message:
            raise ValueError("escalation_message is required when confidence_threshold is set.")
        return self

    @field_validator("fallback_deployment_ids")
    @classmethod
    def _dedupe_fallbacks(cls, value: list[UUID]) -> list[UUID]:
        # Preserve order while removing duplicates.
        seen: set[UUID] = set()
        unique: list[UUID] = []
        for deployment_id in value:
            if deployment_id in seen:
                continue
            seen.add(deployment_id)
            unique.append(deployment_id)
        return unique


class AgentBuilderConfigIssue(BaseModel):
    severity: AgentBuilderConfigIssueSeverity
    code: str
    message: str
    field: str | None = None


class AgentBuilderValidationReport(BaseModel):
    ok: bool
    issues: list[AgentBuilderConfigIssue] = Field(default_factory=list)


class AgentBuilderPreviewRequest(BaseModel):
    """Preview request: render a config into a prompt + metadata snapshot
    without persisting anything."""

    config: AgentBuilderConfig


class AgentBuilderRenderOutput(BaseModel):
    """Output of the renderer — the materialized prompt + metadata the
    ConfigurableAgent will use at run time."""

    system_prompt: str
    user_prompt_template: str
    response_style: ResponseStyle
    language: SupportedLanguage
    greeting_message: str | None
    fallback_message: str
    escalation_message: str | None
    confidence_threshold: float | None
    bound_knowledge_base_ids: list[UUID]
    bound_mcp_server_keys: list[str]
    runtime_metadata: dict[str, Any]
