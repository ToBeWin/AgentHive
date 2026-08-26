from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.install_identity import get_install_identity
from app.models.license import License, LicenseActivation
from app.schemas.license import LicenseStatus
from app.services.license_service import DEFAULT_ALLOWED_FEATURES, DEFAULT_ALLOWED_MODULES, MAINTENANCE_UNTIL


DEMO_LICENSE_KEY = "agenthive-demo-enterprise-active-key"


async def seed_demo_license(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    customer_name: str,
    activated_by: UUID,
) -> License:
    identity = get_install_identity()
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(License).where(
            License.tenant_id == tenant_id,
            License.license_key_hash == sha256(DEMO_LICENSE_KEY.encode()).hexdigest(),
        )
    )
    license_record = result.scalar_one_or_none()
    if license_record is None:
        license_record = License(
            tenant_id=tenant_id,
            license_key_hash=sha256(DEMO_LICENSE_KEY.encode()).hexdigest(),
            license_type="enterprise",
            customer_name=customer_name,
            status=LicenseStatus.ACTIVE.value,
            deployment_id=identity.deployment_id,
            install_id=identity.install_id,
            machine_fingerprint_hash=identity.machine_fingerprint_hash,
            allowed_modules=list(DEFAULT_ALLOWED_MODULES),
            allowed_features=list(DEFAULT_ALLOWED_FEATURES),
            max_users=500,
            max_agents=50,
            max_kb_size_gb=Decimal("50.0"),
            maintenance_until=MAINTENANCE_UNTIL,
            expires_at=None,
            activated_at=now,
            signature_payload={"demo_seed": True, "license_key": "demo-enterprise"},
        )
        session.add(license_record)
        await session.flush()
    else:
        license_record.status = LicenseStatus.ACTIVE.value
        license_record.deployment_id = identity.deployment_id
        license_record.install_id = identity.install_id
        license_record.machine_fingerprint_hash = identity.machine_fingerprint_hash
        license_record.allowed_modules = list(DEFAULT_ALLOWED_MODULES)
        license_record.allowed_features = list(DEFAULT_ALLOWED_FEATURES)
        license_record.max_users = 500
        license_record.max_agents = 50
        license_record.max_kb_size_gb = Decimal("50.0")
        license_record.maintenance_until = MAINTENANCE_UNTIL
        license_record.expires_at = None
        license_record.activated_at = license_record.activated_at or now

    await _ensure_demo_activation(
        session,
        tenant_id=tenant_id,
        license_record=license_record,
        activated_by=activated_by,
    )
    return license_record


async def _ensure_demo_activation(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    license_record: License,
    activated_by: UUID,
) -> None:
    identity = get_install_identity()
    result = await session.execute(
        select(LicenseActivation).where(
            LicenseActivation.tenant_id == tenant_id,
            LicenseActivation.license_id == license_record.id,
            LicenseActivation.status == LicenseStatus.ACTIVE.value,
        )
    )
    activation = result.scalar_one_or_none()
    if activation is not None:
        activation.deployment_id = identity.deployment_id
        activation.install_id = identity.install_id
        activation.machine_fingerprint_hash = identity.machine_fingerprint_hash
        activation.activated_by = activated_by
        return

    session.add(
        LicenseActivation(
            tenant_id=tenant_id,
            license_id=license_record.id,
            deployment_id=identity.deployment_id,
            install_id=identity.install_id,
            machine_fingerprint_hash=identity.machine_fingerprint_hash,
            activation_type="demo_seed",
            status=LicenseStatus.ACTIVE.value,
            activated_by=activated_by,
            activated_at=datetime.now(timezone.utc),
            request_payload={"demo_seed": True},
        )
    )
    await session.flush()
