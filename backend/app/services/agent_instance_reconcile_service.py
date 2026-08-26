from datetime import datetime, timezone
from typing import Any, cast
from uuid import UUID

from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.agent_module import AgentInstance, AgentModule, TenantAgentModule
from app.schemas.license import AgentModuleState, LicenseStatus, LicenseStatusResponse
from app.services.audit_service import record_audit_event


async def reconcile_agent_instances_for_license_status(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    license_status: LicenseStatusResponse,
    actor_id: UUID | None = None,
    request_id: str | None = None,
    reason: str,
    module_keys: list[str] | None = None,
) -> int:
    """Disable active Agent instances that are no longer runnable.

    Runnable means the License is active, the module is still licensed, and the
    tenant has explicitly enabled the module. This keeps the management UI,
    runtime checks, and commercial authorization state aligned after module or
    License changes.
    """
    runnable_module_keys = await _runnable_module_keys(
        session,
        tenant_id=tenant_id,
        license_status=license_status,
    )
    instances = await _active_agent_instances(
        session,
        tenant_id=tenant_id,
        module_keys=module_keys,
    )
    now = datetime.now(timezone.utc)
    disabled_count = 0
    for instance in instances:
        if instance.module_key in runnable_module_keys:
            continue
        previous_status = instance.status
        instance.status = "disabled"
        instance.updated_at = now
        instance.metadata_json = {
            **(instance.metadata_json or {}),
            "runtime_disabled_at": now.isoformat(),
            "runtime_disabled_gate": "license_module_reconcile",
            "runtime_disabled_reason": reason,
        }
        disabled_count += 1
        await record_audit_event(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            request_id=request_id,
            action="agent.instance.runtime_disable",
            resource_type="agent_instance",
            resource_id=instance.id,
            details={
                "agent_key": instance.agent_key,
                "module_key": instance.module_key,
                "previous_status": previous_status,
                "next_status": instance.status,
                "reason": reason,
                "license_status": license_status.status.value,
            },
        )
    return disabled_count


async def _runnable_module_keys(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    license_status: LicenseStatusResponse,
) -> set[str]:
    if license_status.status != LicenseStatus.ACTIVE:
        return set()
    allowed_modules = set(license_status.allowed_modules)
    if not allowed_modules:
        return set()

    module_result = await session.execute(
        select(AgentModule).where(
            cast(Any, AgentModule.module_key).in_(allowed_modules),
            cast(Any, AgentModule.is_active).is_(True),
        )
    )
    modules_by_id = {module.id: module for module in module_result.scalars().all()}
    if not modules_by_id:
        return set()

    tenant_result = await session.execute(
        select(TenantAgentModule).where(
            cast(ColumnElement[bool], TenantAgentModule.tenant_id == tenant_id),
            cast(Any, TenantAgentModule.module_id).in_(list(modules_by_id.keys())),
        )
    )
    runnable: set[str] = set()
    for tenant_module in tenant_result.scalars().all():
        if tenant_module.state != AgentModuleState.ENABLED.value:
            continue
        module = modules_by_id.get(tenant_module.module_id)
        if module is not None:
            runnable.add(module.module_key)
    return runnable


async def _active_agent_instances(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    module_keys: list[str] | None,
) -> list[AgentInstance]:
    query = select(AgentInstance).where(
        cast(ColumnElement[bool], AgentInstance.tenant_id == tenant_id),
        cast(ColumnElement[bool], AgentInstance.status == "active"),
    )
    if module_keys is not None:
        query = query.where(cast(Any, AgentInstance.module_key).in_(module_keys))
    result = await session.execute(query)
    return list(result.scalars().all())
