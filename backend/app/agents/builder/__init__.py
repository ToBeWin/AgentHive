"""Low-code Agent Builder — config schema, validator, renderer, engine.

The Builder turns a JSON configuration submitted by a tenant admin into a
runnable Agent. The configuration is stored inside the existing
``AgentInstance.config["builder_config"]`` JSON column so no new database
table is required; a dedicated ``ConfigurableAgent`` reads the configuration
from the runtime context and renders it into a LangGraph-style chat flow at
run time.

Pipeline:
    config  ─►  validator  ─►  renderer  ─►  ConfigurableAgent.run()
             (policy/budget      (config →
              constraints)       system_prompt + tools)

Security model:
- ``deployment_id`` must pass the principal's LLM policies (model policy
  engine) and the deployment must be ``ACTIVE`` for the tenant.
- ``max_tokens`` / ``temperature`` / ``max_cost_per_request`` cannot exceed
  the limit defined by the matching allow-policy.
- ``knowledge_base_ids`` must be visible to the principal (existing
  ``knowledge_base`` service already enforces this when the agent runs).
- ``mcp_server_keys`` must reference active MCP servers owned by the
  tenant (validated against ``mcp_service``).
- Fallback chain (``fallback_deployment_ids``) is validated the same way as
  the primary deployment.
"""

from __future__ import annotations

from .config import (
    AgentBuilderConfig,
    AgentBuilderConfigIssue,
    AgentBuilderConfigIssueSeverity,
    AgentBuilderPreviewRequest,
    AgentBuilderRenderOutput,
    AgentBuilderValidationReport,
    ResponseStyle,
    SupportedLanguage,
)
from .engine import (
    BuilderValidationError,
    compile_builder_config,
    preview_builder_config,
    validate_builder_config,
)
from .renderer import render_builder_config
from .validator import validate_config_against_policies

__all__ = [
    "AgentBuilderConfig",
    "AgentBuilderConfigIssue",
    "AgentBuilderConfigIssueSeverity",
    "AgentBuilderPreviewRequest",
    "AgentBuilderRenderOutput",
    "AgentBuilderValidationReport",
    "BuilderValidationError",
    "ResponseStyle",
    "SupportedLanguage",
    "compile_builder_config",
    "preview_builder_config",
    "render_builder_config",
    "validate_builder_config",
    "validate_config_against_policies",
]
