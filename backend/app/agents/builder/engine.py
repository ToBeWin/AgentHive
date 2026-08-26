"""Builder engine — orchestrate validate → render → compile / preview.

The engine is the only entry point the API layer calls. It owns the side
effects (DB access, audit) and exposes two flows:

- ``validate_builder_config`` — pure validation, returns the report.
- ``preview_builder_config`` — validate + render, returns the rendered
  output alongside the validation report. Does not persist anything.
- ``compile_builder_config`` — validate + render + persist into an
  ``AgentInstance`` (config["builder_config"]). Used by the create / update
  endpoints.

A ``BuilderValidationError`` is raised when compilation is attempted on a
config with ``ERROR`` issues, so the API layer can return 422.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.builder.config import (
    AgentBuilderConfig,
    AgentBuilderPreviewRequest,
    AgentBuilderRenderOutput,
    AgentBuilderValidationReport,
)
from app.agents.builder.renderer import render_builder_config
from app.agents.builder.validator import validate_config_against_policies
from app.api.deps import Principal


class BuilderValidationError(Exception):
    """Raised when a config cannot be compiled because of ERROR issues."""

    def __init__(self, report: AgentBuilderValidationReport) -> None:
        self.report = report
        error_messages = [
            f"{issue.code}: {issue.message}" for issue in report.issues if issue.severity == "error"
        ]
        super().__init__("Builder config validation failed: " + "; ".join(error_messages))


async def validate_builder_config(
    session: AsyncSession,
    principal: Principal,
    config: AgentBuilderConfig,
) -> AgentBuilderValidationReport:
    return await validate_config_against_policies(session, principal, config)


async def preview_builder_config(
    session: AsyncSession,
    principal: Principal,
    request: AgentBuilderPreviewRequest,
) -> tuple[AgentBuilderRenderOutput, AgentBuilderValidationReport]:
    report = await validate_builder_config(session, principal, request.config)
    rendered = render_builder_config(request.config)
    return rendered, report


async def compile_builder_config(
    session: AsyncSession,
    principal: Principal,
    config: AgentBuilderConfig,
) -> AgentBuilderRenderOutput:
    """Validate then render a config. Raises on ERROR issues.

    Returns the rendered output so callers can persist it inside the
    AgentInstance config and surface the rendered prompt to the caller.
    """
    report = await validate_builder_config(session, principal, config)
    if not report.ok:
        raise BuilderValidationError(report)
    return render_builder_config(config)


def builder_config_to_instance_metadata(
    config: AgentBuilderConfig,
    rendered: AgentBuilderRenderOutput,
) -> dict[str, Any]:
    """Flatten a config + rendered output into the JSON stored on
    AgentInstance.config["builder_config"].

    Stored as a single nested dict so reads from the runtime are a single
    lookup and the original config can be reconstructed for the editor.
    """
    return {
        "config": config.model_dump(mode="json"),
        "rendered": rendered.model_dump(mode="json"),
    }
