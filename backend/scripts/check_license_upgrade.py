import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from uuid import UUID

from sqlmodel import select

from app.core.database import AsyncSessionLocal, engine
from app.models.tenant import Tenant
from app.schemas.license import LicenseStatus, LicenseStatusResponse
from app.services.license_service import get_license_status_for_tenant


@dataclass(frozen=True)
class TenantLicenseUpgradeCheck:
    tenant_id: UUID
    tenant_slug: str
    tenant_name: str
    status: LicenseStatus
    customer_name: str
    license_type: str
    maintenance_until: datetime | None
    expires_at: datetime | None
    verification_issues: list[str]
    failures: list[str]

    @property
    def passed(self) -> bool:
        return not self.failures


def evaluate_license_upgrade_status(
    license_status: LicenseStatusResponse,
    *,
    now: datetime,
) -> list[str]:
    failures: list[str] = []
    if license_status.status != LicenseStatus.ACTIVE:
        failures.append(f"license_status_{license_status.status.value}")
    if license_status.verification_issues:
        failures.extend(f"verification_issue_{issue}" for issue in license_status.verification_issues)
    if license_status.maintenance_until is None:
        failures.append("maintenance_window_missing")
    elif _as_aware_utc(license_status.maintenance_until) <= now:
        failures.append("maintenance_window_expired")
    if license_status.expires_at is not None and _as_aware_utc(license_status.expires_at) <= now:
        failures.append("license_expired")
    return failures


async def collect_upgrade_checks(*, now: datetime) -> list[TenantLicenseUpgradeCheck]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Tenant).where(Tenant.is_active.is_(True)).order_by(Tenant.created_at))
        tenants = list(result.scalars().all())
        checks: list[TenantLicenseUpgradeCheck] = []
        for tenant in tenants:
            license_status = await get_license_status_for_tenant(session, tenant_id=tenant.id)
            checks.append(
                TenantLicenseUpgradeCheck(
                    tenant_id=tenant.id,
                    tenant_slug=tenant.slug,
                    tenant_name=tenant.name,
                    status=license_status.status,
                    customer_name=license_status.customer_name,
                    license_type=license_status.license_type,
                    maintenance_until=license_status.maintenance_until,
                    expires_at=license_status.expires_at,
                    verification_issues=list(license_status.verification_issues),
                    failures=evaluate_license_upgrade_status(license_status, now=now),
                )
            )
        return checks


async def main() -> None:
    parser = argparse.ArgumentParser(description="Check whether the current AgentHive license permits upgrade.")
    parser.add_argument("--target-version", default=os.environ.get("AGENTHIVE_VERSION", "unknown"))
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    try:
        checks = await collect_upgrade_checks(now=now)
    except Exception as exc:
        await engine.dispose()
        raise SystemExit(f"License upgrade precheck failed: {exc.__class__.__name__}: {exc}") from exc

    print("AgentHive license upgrade precheck")
    print(f"  target_version: {args.target_version}")
    print(f"  checked_at:     {now.isoformat()}")
    print(f"  tenants:        {len(checks)}")

    if not checks:
        await engine.dispose()
        raise SystemExit("No active tenant found. Initialize AgentHive before running production upgrades.")

    failed = False
    for check in checks:
        print(f"  - tenant: {check.tenant_slug} ({check.tenant_name})")
        print(f"    customer:          {check.customer_name}")
        print(f"    license_type:      {check.license_type}")
        print(f"    status:            {check.status.value}")
        print(f"    maintenance_until: {_format_datetime(check.maintenance_until)}")
        print(f"    expires_at:        {_format_datetime(check.expires_at)}")
        if check.verification_issues:
            print(f"    verification:      {', '.join(check.verification_issues)}")
        if check.failures:
            failed = True
            print(f"    upgrade_allowed:   false ({', '.join(check.failures)})")
        else:
            print("    upgrade_allowed:   true")

    await engine.dispose()
    if failed:
        raise SystemExit(
            "AgentHive upgrade is not authorized for the current license state. "
            "Activate a renewed license or extend maintenance before upgrading."
        )


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "not_set"
    return _as_aware_utc(value).isoformat()


if __name__ == "__main__":
    asyncio.run(main())
