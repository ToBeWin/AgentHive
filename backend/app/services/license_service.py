import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import is_development_environment, settings
from app.core.install_identity import InstallIdentity, get_install_identity
from app.core.license_crypto import verify_signed_license
from app.models.agent_module import AgentInstance, AgentModule, TenantAgentModule
from app.models.knowledge import KnowledgeDocument
from app.models.license import License, LicenseActivation
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.license import (
    AgentModuleState,
    AuthorizedFeature,
    AuthorizedModule,
    DeploymentFingerprintResponse,
    LicenseActivationRequest,
    LicenseActivationRequestExport,
    LicenseActivationResponse,
    LicenseDeactivateResponse,
    LicenseModulesResponse,
    LicenseStatus,
    LicenseStatusResponse,
    LicenseVerificationResponse,
)
from app.services.agent_instance_reconcile_service import (
    reconcile_agent_instances_for_license_status,
)
from app.services.audit_service import record_audit_event

DEFAULT_ALLOWED_MODULES = [
    "agent.customer_service",
    "agent.hr_screening",
    "agent.copywriting",
    "agent.image_generation",
    "agent.video_generation",
    "agent.product_design",
    "agent.report_writer",
]
DEFAULT_ALLOWED_FEATURES = [
    "feature.agent_catalog",
    "feature.license_offline_activation",
    "feature.model_budget",
    "feature.media_generation",
    "channel.web_widget",
]
MAINTENANCE_UNTIL = datetime(2027, 6, 8, tzinfo=timezone.utc)


class LicenseRuntimeState:
    def __init__(self) -> None:
        self.status = LicenseStatus.INACTIVE
        self.license_type = "basic"
        self.customer_name = "AgentHive Trial Tenant"
        self.allowed_modules: list[str] = []
        self.allowed_features: list[str] = []
        self.max_users: int | None = None
        self.max_agents: int | None = None
        self.max_kb_size_gb: Decimal | None = None
        self.maintenance_until: datetime | None = None
        self.expires_at: datetime | None = None
        self.activated_at: datetime | None = None


_license_state = LicenseRuntimeState()


@dataclass(frozen=True)
class SupersededLicenseSummary:
    license_id: UUID
    license_type: str
    customer_name: str
    deactivated_activation_count: int


def get_allowed_module_ids() -> list[str]:
    return list(_license_state.allowed_modules)


def get_license_status_value() -> LicenseStatus:
    return _license_state.status


def get_deployment_fingerprint() -> DeploymentFingerprintResponse:
    identity = get_install_identity()
    return DeploymentFingerprintResponse(
        product="AgentHive",
        deployment_id=identity.deployment_id,
        install_id=identity.install_id,
        machine_fingerprint_hash=identity.machine_fingerprint_hash,
        fingerprint_algorithm=identity.fingerprint_algorithm,
        generated_at=datetime.now(timezone.utc),
    )


def get_activation_request(tenant_id: UUID) -> LicenseActivationRequestExport:
    identity = get_install_identity()
    generated_at = datetime.now(timezone.utc)
    request_id = uuid4().hex
    request_document = {
        "schema_version": 1,
        "request_format": "agenthive.offline_activation_request.v1",
        "product": "AgentHive",
        "tenant_id": str(tenant_id),
        "deployment_id": str(identity.deployment_id),
        "install_id": str(identity.install_id),
        "machine_fingerprint_hash": identity.machine_fingerprint_hash,
        "fingerprint_algorithm": identity.fingerprint_algorithm,
        "generated_at": generated_at.isoformat(),
        "request_id": request_id,
    }
    canonical_request = _canonical_activation_request(request_document)
    return LicenseActivationRequestExport(
        product="AgentHive",
        tenant_id=tenant_id,
        deployment_id=identity.deployment_id,
        install_id=identity.install_id,
        machine_fingerprint_hash=identity.machine_fingerprint_hash,
        fingerprint_algorithm=identity.fingerprint_algorithm,
        generated_at=generated_at,
        request_id=request_id,
        request_code=_activation_request_code(canonical_request),
        request_hash=sha256(canonical_request).hexdigest(),
    )


async def get_activation_request_for_tenant(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    actor_id: UUID | None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> LicenseActivationRequestExport:
    activation_request = get_activation_request(tenant_id)
    await record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action="license.activation_request.export",
        resource_type="license",
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details={
            "activation_request_id": activation_request.request_id,
            "activation_request_hash": activation_request.request_hash,
            "request_format": activation_request.request_format,
            "deployment_id": str(activation_request.deployment_id),
            "install_id": str(activation_request.install_id),
            "fingerprint_algorithm": activation_request.fingerprint_algorithm,
            "machine_fingerprint_hash_present": bool(activation_request.machine_fingerprint_hash),
        },
    )
    await session.commit()
    return activation_request


def activate_license(payload: LicenseActivationRequest) -> LicenseActivationResponse:
    normalized_key = payload.license_key.strip().lower()
    now = datetime.now(timezone.utc)

    _license_state.status = _status_from_key(normalized_key)
    _license_state.license_type = "enterprise" if "enterprise" in normalized_key else "standard"
    _license_state.customer_name = "AgentHive Demo Customer"
    _license_state.allowed_modules = list(DEFAULT_ALLOWED_MODULES)
    _license_state.allowed_features = list(DEFAULT_ALLOWED_FEATURES)
    _license_state.max_users = 50
    _license_state.max_agents = 5
    _license_state.max_kb_size_gb = Decimal("5.0")
    _license_state.maintenance_until = MAINTENANCE_UNTIL
    _license_state.expires_at = None
    _license_state.activated_at = now if _license_state.status == LicenseStatus.ACTIVE else None

    if _license_state.status == LicenseStatus.EXPIRED:
        _license_state.maintenance_until = datetime(2025, 6, 8, tzinfo=timezone.utc)
        _license_state.expires_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    if _license_state.status in {LicenseStatus.REVOKED, LicenseStatus.MISMATCH}:
        _license_state.allowed_modules = []
        _license_state.allowed_features = []
        _license_state.max_users = None
        _license_state.max_agents = None
        _license_state.max_kb_size_gb = None

    return LicenseActivationResponse(
        status=_license_state.status,
        message=_activation_message(_license_state.status),
        license=get_license_status(),
    )


def get_license_status() -> LicenseStatusResponse:
    identity = get_install_identity()
    return LicenseStatusResponse(
        status=_license_state.status,
        license_type=_license_state.license_type,
        customer_name=_license_state.customer_name,
        deployment_id=identity.deployment_id,
        install_id=identity.install_id,
        machine_fingerprint_hash=identity.machine_fingerprint_hash,
        runtime_deployment_id=identity.deployment_id,
        runtime_install_id=identity.install_id,
        runtime_machine_fingerprint_hash=identity.machine_fingerprint_hash,
        verification_issues=[]
        if _license_state.status == LicenseStatus.ACTIVE
        else [f"license_status_{_license_state.status.value}"],
        allowed_modules=list(_license_state.allowed_modules),
        allowed_features=list(_license_state.allowed_features),
        maintenance_until=_license_state.maintenance_until,
        expires_at=_license_state.expires_at,
        activated_at=_license_state.activated_at,
        max_users=_license_state.max_users,
        max_agents=_license_state.max_agents,
        max_kb_size_gb=_license_state.max_kb_size_gb,
        module_count=len(_license_state.allowed_modules),
        feature_count=len(_license_state.allowed_features),
    )


def get_license_modules() -> LicenseModulesResponse:
    allowed_modules = set(_license_state.allowed_modules)
    allowed_features = set(_license_state.allowed_features)

    modules = [
        AuthorizedModule(
            id=module_id,
            name=name,
            state=AgentModuleState.INSTALLED
            if module_id in allowed_modules
            else AgentModuleState.NOT_LICENSED,
            licensed=module_id in allowed_modules,
            installed=module_id in allowed_modules,
            enabled=False,
        )
        for module_id, name in _known_module_names().items()
    ]
    features = [
        AuthorizedFeature(id=feature_id, name=name, enabled=feature_id in allowed_features)
        for feature_id, name in _known_feature_names().items()
    ]
    return LicenseModulesResponse(modules=modules, features=features)


def deactivate_license() -> LicenseDeactivateResponse:
    _license_state.status = LicenseStatus.INACTIVE
    _license_state.license_type = "basic"
    _license_state.customer_name = "AgentHive Trial Tenant"
    _license_state.allowed_modules = []
    _license_state.allowed_features = []
    _license_state.max_users = None
    _license_state.max_agents = None
    _license_state.max_kb_size_gb = None
    _license_state.maintenance_until = None
    _license_state.expires_at = None
    _license_state.activated_at = None

    return LicenseDeactivateResponse(
        status=_license_state.status,
        message="License deactivated for this deployment.",
        deactivated_at=datetime.now(timezone.utc),
    )


async def get_license_status_for_tenant(
    session: AsyncSession,
    *,
    tenant_id: UUID,
) -> LicenseStatusResponse:
    try:
        license_record = await _load_current_license(session, tenant_id)
    except (OSError, SQLAlchemyError):
        return _inactive_license_status()
    if license_record is None:
        return _inactive_license_status()
    return _status_from_record(license_record)


async def ensure_license_capacity(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    resource: Literal["users", "agents", "knowledge_storage_bytes"],
    increment: int = 1,
) -> LicenseStatusResponse:
    license_status = await get_license_status_for_tenant(session, tenant_id=tenant_id)
    try:
        current_count = await _count_capacity_resource(
            session,
            tenant_id=tenant_id,
            resource=resource,
        )
    except (OSError, SQLAlchemyError) as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="License capacity storage is unavailable.",
        ) from exc
    _enforce_license_capacity(
        resource=resource,
        current_count=current_count,
        increment=increment,
        license_status=license_status,
    )
    return license_status


async def activate_license_for_tenant(
    session: AsyncSession,
    payload: LicenseActivationRequest,
    *,
    tenant_id: UUID,
    actor_id: UUID | None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> LicenseActivationResponse:
    try:
        tenant = await session.get(Tenant, tenant_id)
    except (OSError, SQLAlchemyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="License storage is unavailable.",
        ) from exc
    try:
        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Tenant must be initialized before activating a license.",
            )

        normalized_key = payload.license_key.strip()
        now = datetime.now(timezone.utc)
        identity = get_install_identity()
        activation_data = _activation_data_from_payload(normalized_key, now, tenant_id=tenant_id)
        activation_status = cast(LicenseStatus, activation_data["status"])
        activation_verification = cast(
            LicenseVerificationResponse | None, activation_data["verification"]
        )
        superseded_licenses: list[SupersededLicenseSummary] = []
        if activation_status == LicenseStatus.ACTIVE:
            superseded_licenses = await _supersede_active_licenses(
                session,
                tenant_id=tenant_id,
                deactivated_at=now,
            )

        license_record = License(
            tenant_id=tenant_id,
            license_key_hash=sha256(normalized_key.encode()).hexdigest(),
            license_type=activation_data["license_type"],
            customer_name=activation_data["customer_name"] or tenant.name,
            status=activation_status.value,
            deployment_id=identity.deployment_id,
            install_id=identity.install_id,
            machine_fingerprint_hash=identity.machine_fingerprint_hash,
            allowed_modules=activation_data["allowed_modules"],
            allowed_features=activation_data["allowed_features"],
            max_users=activation_data["max_users"] or tenant.max_users,
            max_agents=activation_data["max_agents"] or tenant.max_agents,
            max_kb_size_gb=activation_data["max_kb_size_gb"] or tenant.max_kb_size_gb,
            maintenance_until=activation_data["maintenance_until"],
            expires_at=activation_data["expires_at"],
            activated_at=now if activation_status == LicenseStatus.ACTIVE else None,
            signature_payload=activation_data["signature_payload"],
        )
        session.add(license_record)
        await session.flush()

        for superseded in superseded_licenses:
            await record_audit_event(
                session,
                tenant_id=tenant_id,
                actor_id=actor_id,
                action="license.supersede",
                resource_type="license",
                resource_id=superseded.license_id,
                request_id=request_id,
                ip_address=ip_address,
                user_agent=user_agent,
                details={
                    "replacement_license_id": str(license_record.id),
                    "previous_status": LicenseStatus.ACTIVE.value,
                    "next_status": LicenseStatus.INACTIVE.value,
                    "license_type": superseded.license_type,
                    "customer_name": superseded.customer_name,
                    "deactivated_activation_count": superseded.deactivated_activation_count,
                },
            )

        session.add(
            LicenseActivation(
                tenant_id=tenant_id,
                license_id=license_record.id,
                deployment_id=identity.deployment_id,
                install_id=identity.install_id,
                machine_fingerprint_hash=identity.machine_fingerprint_hash,
                activation_type="offline" if payload.activation_code else "online",
                status=activation_status.value,
                activated_by=actor_id,
                activated_at=license_record.activated_at,
                request_payload={
                    "activation_code_present": bool(payload.activation_code),
                    "verification": activation_verification.model_dump(mode="json")
                    if activation_verification
                    else None,
                },
            )
        )
        license_response = _status_from_record(license_record)
        disabled_instance_count = await reconcile_agent_instances_for_license_status(
            session,
            tenant_id=tenant_id,
            license_status=license_response,
            actor_id=actor_id,
            request_id=request_id,
            reason="license_activation",
        )
        await record_audit_event(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="license.activate",
            resource_type="license",
            resource_id=license_record.id,
            status=activation_status.value,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "license_type": license_record.license_type,
                "superseded_license_count": len(superseded_licenses),
                "disabled_agent_instance_count": disabled_instance_count,
                "verification": activation_verification.model_dump(mode="json")
                if activation_verification
                else None,
            },
        )
        await session.commit()

        return LicenseActivationResponse(
            status=activation_status,
            message=_activation_message(activation_status),
            license=license_response,
            verification=activation_verification,
        )
    except HTTPException as exc:
        await _record_license_activation_failure_audit(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload=payload,
            exc=exc,
        )
        raise


async def get_license_modules_for_tenant(
    session: AsyncSession,
    *,
    tenant_id: UUID,
) -> LicenseModulesResponse:
    try:
        license_record = await _load_current_license(session, tenant_id)
    except (OSError, SQLAlchemyError):
        license_record = None
    license_status = (
        _status_from_record(license_record) if license_record else _inactive_license_status()
    )
    module_names, tenant_module_states = await _load_license_module_catalog_state(
        session,
        tenant_id=tenant_id,
    )
    module_names = {**_known_module_names(), **module_names}
    for module_id in license_status.allowed_modules:
        module_names.setdefault(module_id, module_id)
    allowed_features = set(
        license_status.allowed_features if license_status.status == LicenseStatus.ACTIVE else []
    )

    modules = [
        _build_authorized_module(
            module_id=module_id,
            name=name,
            license_status=license_status,
            tenant_module_state=tenant_module_states.get(module_id),
        )
        for module_id, name in module_names.items()
    ]
    features = [
        AuthorizedFeature(id=feature_id, name=name, enabled=feature_id in allowed_features)
        for feature_id, name in _known_feature_names().items()
    ]
    return LicenseModulesResponse(modules=modules, features=features)


async def deactivate_license_for_tenant(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    actor_id: UUID | None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> LicenseDeactivateResponse:
    license_record = await _load_current_license(session, tenant_id)
    now = datetime.now(timezone.utc)
    if license_record is not None:
        license_record.status = LicenseStatus.INACTIVE.value
        license_record.updated_at = now
        await _deactivate_license_activations(
            session,
            tenant_id=tenant_id,
            license_id=license_record.id,
            deactivated_at=now,
        )
        disabled_instance_count = await reconcile_agent_instances_for_license_status(
            session,
            tenant_id=tenant_id,
            license_status=_status_from_record(license_record),
            actor_id=actor_id,
            request_id=request_id,
            reason="license_deactivated",
        )
        await record_audit_event(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="license.deactivate",
            resource_type="license",
            resource_id=license_record.id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"disabled_agent_instance_count": disabled_instance_count},
        )
        await session.commit()
    else:
        disabled_instance_count = await reconcile_agent_instances_for_license_status(
            session,
            tenant_id=tenant_id,
            license_status=_inactive_license_status(),
            actor_id=actor_id,
            request_id=request_id,
            reason="license_deactivated",
        )
        await record_audit_event(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="license.deactivate",
            resource_type="license",
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "result": "no_active_license",
                "disabled_agent_instance_count": disabled_instance_count,
            },
        )
        await session.commit()

    return LicenseDeactivateResponse(
        status=LicenseStatus.INACTIVE,
        message="License deactivated for this deployment.",
        deactivated_at=now,
    )


async def _record_license_activation_failure_audit(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    actor_id: UUID | None,
    request_id: str | None,
    ip_address: str | None,
    user_agent: str | None,
    payload: LicenseActivationRequest,
    exc: HTTPException,
) -> None:
    try:
        await session.rollback()
        await record_audit_event(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="license.activate",
            resource_type="license",
            status="failure",
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "status_code": exc.status_code,
                "reason": str(exc.detail),
                "license_input_format": _license_input_format(payload.license_key),
                "activation_mode": "offline" if payload.activation_code else "online",
            },
        )
        await session.commit()
    except Exception:
        await session.rollback()


def _activation_data_from_payload(
    raw_license: str,
    now: datetime,
    *,
    tenant_id: UUID | None = None,
) -> dict[str, object]:
    if _looks_like_signed_license(raw_license):
        return _activation_data_from_signed_license(raw_license, now, tenant_id=tenant_id)
    if not is_development_environment():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsigned development license keys are not accepted outside development.",
        )
    return _activation_data_from_legacy_key(raw_license, now)


def _activation_data_from_signed_license(
    raw_license: str,
    now: datetime,
    *,
    tenant_id: UUID | None,
) -> dict[str, object]:
    public_key = _load_license_public_key()
    identity = get_install_identity()
    verification = verify_signed_license(
        raw=raw_license,
        public_key_pem=public_key,
        deployment_id=str(identity.deployment_id),
        install_id=str(identity.install_id),
        machine_fingerprint_hash=identity.machine_fingerprint_hash,
        tenant_id=str(tenant_id) if tenant_id else None,
        now=now,
    )
    if verification.envelope is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid signed license: {verification.reason}",
        )
    if verification.status == "invalid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid signed license: {verification.reason}",
        )
    envelope = verification.envelope
    payload = envelope.payload
    known_statuses = {item.value for item in LicenseStatus}
    license_status = (
        LicenseStatus(verification.status)
        if verification.status in known_statuses
        else LicenseStatus.REVOKED
    )
    if not verification.valid and license_status == LicenseStatus.INACTIVE:
        license_status = LicenseStatus.REVOKED
    allowed_modules = list(payload.allowed_modules) if verification.valid else []
    allowed_features = list(payload.allowed_features) if verification.valid else []
    return {
        "status": license_status,
        "license_type": payload.license_type,
        "customer_name": payload.customer_name,
        "allowed_modules": allowed_modules,
        "allowed_features": allowed_features,
        "max_users": payload.max_users,
        "max_agents": payload.max_agents,
        "max_kb_size_gb": payload.max_kb_size_gb,
        "maintenance_until": payload.maintenance_until,
        "expires_at": payload.expires_at,
        "signature_payload": {
            "mode": "signed-license",
            "signature_alg": envelope.signature_alg,
            "license_id": payload.license_id,
            "verification": verification.model_dump(mode="json", exclude={"envelope"}),
            "payload": payload.model_dump(mode="json"),
        },
        "verification": LicenseVerificationResponse(
            mode="signed-license",
            valid=verification.valid,
            status=license_status,
            reason=verification.reason,
            signature_alg=envelope.signature_alg,
            license_id=payload.license_id,
        ),
    }


def _activation_data_from_legacy_key(raw_license: str, now: datetime) -> dict[str, object]:
    normalized_key_lower = raw_license.lower()
    license_status = _status_from_key(normalized_key_lower)
    allowed_modules = list(DEFAULT_ALLOWED_MODULES)
    allowed_features = list(DEFAULT_ALLOWED_FEATURES)
    maintenance_until: datetime | None = MAINTENANCE_UNTIL
    expires_at: datetime | None = None

    if license_status == LicenseStatus.EXPIRED:
        maintenance_until = datetime(2025, 6, 8, tzinfo=timezone.utc)
        expires_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    if license_status in {LicenseStatus.REVOKED, LicenseStatus.MISMATCH}:
        allowed_modules = []
        allowed_features = []

    return {
        "status": license_status,
        "license_type": "enterprise" if "enterprise" in normalized_key_lower else "standard",
        "customer_name": "AgentHive Demo Customer",
        "allowed_modules": allowed_modules,
        "allowed_features": allowed_features,
        "max_users": None,
        "max_agents": None,
        "max_kb_size_gb": None,
        "maintenance_until": maintenance_until,
        "expires_at": expires_at,
        "signature_payload": {
            "mode": "development-legacy-key",
            "activated_at": now.isoformat(),
        },
        "verification": LicenseVerificationResponse(
            mode="development-legacy-key",
            valid=license_status == LicenseStatus.ACTIVE,
            status=license_status,
            reason="development_legacy_key",
            signature_alg=None,
            license_id=None,
        ),
    }


def _load_license_public_key() -> str:
    if not settings.license_public_key_path:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="License public key is not configured.",
        )
    try:
        return Path(settings.license_public_key_path).read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="License public key cannot be read.",
        ) from exc


def _looks_like_signed_license(raw_license: str) -> bool:
    stripped = raw_license.strip()
    if stripped.startswith("{"):
        return True
    try:
        decoded = base64.b64decode(stripped.encode("utf-8"), validate=True).decode("utf-8")
    except Exception:
        return False
    return decoded.strip().startswith("{")


def _license_input_format(raw_license: str) -> str:
    stripped = raw_license.strip()
    if not stripped:
        return "empty"
    if stripped.startswith("{"):
        return "signed_license_json"
    try:
        decoded = base64.b64decode(stripped.encode("utf-8"), validate=True).decode("utf-8")
    except Exception:
        return "development_legacy_key"
    return "signed_license_base64" if decoded.strip().startswith("{") else "development_legacy_key"


def _canonical_activation_request(document: dict[str, object]) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _activation_request_code(canonical_request: bytes) -> str:
    return base64.urlsafe_b64encode(canonical_request).decode("ascii")


async def _load_current_license(session: AsyncSession, tenant_id: UUID) -> License | None:
    result = await session.execute(
        select(License)
        .where(cast(ColumnElement[bool], License.tenant_id == tenant_id))
        .order_by(
            cast(Any, (License.status == LicenseStatus.ACTIVE.value)).desc(),
            cast(Any, License.created_at).desc(),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _load_license_module_catalog_state(
    session: AsyncSession,
    *,
    tenant_id: UUID,
) -> tuple[dict[str, str], dict[str, AgentModuleState]]:
    try:
        modules_result = await session.execute(
            select(AgentModule)
            .where(cast(Any, AgentModule.is_active).is_(True))
            .order_by(AgentModule.priority, AgentModule.module_key)
        )
        modules = list(modules_result.scalars().all())
        modules_by_id = {module.id: module for module in modules}
        module_names = {module.module_key: module.name for module in modules}

        tenant_result = await session.execute(
            select(TenantAgentModule).where(TenantAgentModule.tenant_id == tenant_id)
        )
    except (OSError, SQLAlchemyError):
        await session.rollback()
        return {}, {}

    tenant_module_states: dict[str, AgentModuleState] = {}
    for tenant_module in tenant_result.scalars().all():
        module = modules_by_id.get(tenant_module.module_id)
        if module is None:
            continue
        try:
            tenant_module_states[module.module_key] = AgentModuleState(tenant_module.state)
        except ValueError:
            tenant_module_states[module.module_key] = AgentModuleState.NOT_INSTALLED
    return module_names, tenant_module_states


def _build_authorized_module(
    *,
    module_id: str,
    name: str,
    license_status: LicenseStatusResponse,
    tenant_module_state: AgentModuleState | None,
) -> AuthorizedModule:
    licensed = module_id in license_status.allowed_modules
    installed_states = {
        AgentModuleState.INSTALLED,
        AgentModuleState.ENABLED,
        AgentModuleState.DISABLED,
    }

    if not licensed:
        return AuthorizedModule(
            id=module_id,
            name=name,
            state=AgentModuleState.NOT_LICENSED,
            licensed=False,
            installed=False,
            enabled=False,
        )

    installed = tenant_module_state in installed_states
    if license_status.status == LicenseStatus.EXPIRED:
        return AuthorizedModule(
            id=module_id,
            name=name,
            state=AgentModuleState.EXPIRED,
            licensed=True,
            installed=installed,
            enabled=False,
        )

    if license_status.status != LicenseStatus.ACTIVE:
        return AuthorizedModule(
            id=module_id,
            name=name,
            state=AgentModuleState.NOT_LICENSED,
            licensed=False,
            installed=False,
            enabled=False,
        )

    state = tenant_module_state or AgentModuleState.NOT_INSTALLED
    return AuthorizedModule(
        id=module_id,
        name=name,
        state=state,
        licensed=True,
        installed=state in installed_states,
        enabled=state == AgentModuleState.ENABLED,
    )


async def _deactivate_license_activations(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    license_id: UUID,
    deactivated_at: datetime,
) -> int:
    result = await session.execute(
        select(LicenseActivation).where(
            cast(ColumnElement[bool], LicenseActivation.tenant_id == tenant_id),
            cast(ColumnElement[bool], LicenseActivation.license_id == license_id),
            cast(Any, LicenseActivation.deactivated_at).is_(None),
        )
    )
    rows = list(result.scalars().all())
    for row in rows:
        row.status = LicenseStatus.INACTIVE.value
        row.deactivated_at = deactivated_at
        row.updated_at = deactivated_at
    return len(rows)


async def _supersede_active_licenses(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    deactivated_at: datetime,
) -> list[SupersededLicenseSummary]:
    result = await session.execute(
        select(License).where(
            License.tenant_id == tenant_id,
            License.status == LicenseStatus.ACTIVE.value,
        )
    )
    active_licenses = list(result.scalars().all())
    superseded: list[SupersededLicenseSummary] = []
    for license_record in active_licenses:
        license_record.status = LicenseStatus.INACTIVE.value
        license_record.updated_at = deactivated_at
        deactivated_activation_count = await _deactivate_license_activations(
            session,
            tenant_id=tenant_id,
            license_id=license_record.id,
            deactivated_at=deactivated_at,
        )
        superseded.append(
            SupersededLicenseSummary(
                license_id=license_record.id,
                license_type=license_record.license_type,
                customer_name=license_record.customer_name,
                deactivated_activation_count=deactivated_activation_count,
            )
        )
    return superseded


def _inactive_license_status() -> LicenseStatusResponse:
    identity = get_install_identity()
    return LicenseStatusResponse(
        status=LicenseStatus.INACTIVE,
        license_type="basic",
        customer_name="Uninitialized Tenant",
        deployment_id=identity.deployment_id,
        install_id=identity.install_id,
        machine_fingerprint_hash=identity.machine_fingerprint_hash,
        runtime_deployment_id=identity.deployment_id,
        runtime_install_id=identity.install_id,
        runtime_machine_fingerprint_hash=identity.machine_fingerprint_hash,
        verification_issues=["no_active_license"],
        allowed_modules=[],
        allowed_features=[],
        maintenance_until=None,
        expires_at=None,
        activated_at=None,
        max_users=None,
        max_agents=None,
        max_kb_size_gb=None,
        module_count=0,
        feature_count=0,
    )


def _status_from_record(license_record: License) -> LicenseStatusResponse:
    identity = get_install_identity()
    effective_status = LicenseStatus(license_record.status)
    allowed_modules = list(license_record.allowed_modules)
    allowed_features = list(license_record.allowed_features)
    verification_issues = _license_identity_issues(license_record, identity)

    if verification_issues:
        effective_status = LicenseStatus.MISMATCH
        allowed_modules = []
        allowed_features = []
    elif license_record.expires_at and license_record.expires_at <= datetime.now(timezone.utc):
        effective_status = LicenseStatus.EXPIRED
        verification_issues.append("license_expired")
    elif effective_status != LicenseStatus.ACTIVE:
        verification_issues.append(f"license_status_{effective_status.value}")
        allowed_modules = []
        allowed_features = []

    return LicenseStatusResponse(
        status=effective_status,
        license_type=license_record.license_type,
        customer_name=license_record.customer_name,
        deployment_id=license_record.deployment_id,
        install_id=license_record.install_id,
        machine_fingerprint_hash=license_record.machine_fingerprint_hash,
        runtime_deployment_id=identity.deployment_id,
        runtime_install_id=identity.install_id,
        runtime_machine_fingerprint_hash=identity.machine_fingerprint_hash,
        verification_issues=verification_issues,
        allowed_modules=allowed_modules,
        allowed_features=allowed_features,
        maintenance_until=license_record.maintenance_until,
        expires_at=license_record.expires_at,
        activated_at=license_record.activated_at,
        max_users=license_record.max_users,
        max_agents=license_record.max_agents,
        max_kb_size_gb=license_record.max_kb_size_gb,
        module_count=len(allowed_modules),
        feature_count=len(allowed_features),
    )


async def _count_capacity_resource(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    resource: Literal["users", "agents", "knowledge_storage_bytes"],
) -> int:
    if resource == "users":
        result = await session.execute(
            select(func.count())
            .select_from(User)
            .where(
                cast(ColumnElement[bool], User.tenant_id == tenant_id),
                cast(Any, User.deleted_at).is_(None),
            )
        )
    elif resource == "agents":
        result = await session.execute(
            select(func.count())
            .select_from(AgentInstance)
            .where(cast(ColumnElement[bool], AgentInstance.tenant_id == tenant_id))
        )
    else:
        result = await session.execute(
            cast(
                Any,
                select(func.coalesce(func.sum(KnowledgeDocument.size_bytes), 0))
                .select_from(KnowledgeDocument)
                .where(
                    cast(ColumnElement[bool], KnowledgeDocument.tenant_id == tenant_id),
                    cast(Any, KnowledgeDocument.deleted_at).is_(None),
                    cast(ColumnElement[bool], KnowledgeDocument.status != "deleted"),
                ),
            )
        )
    return int(result.scalar_one() or 0)


def _enforce_license_capacity(
    *,
    resource: Literal["users", "agents", "knowledge_storage_bytes"],
    current_count: int,
    increment: int,
    license_status: LicenseStatusResponse,
) -> None:
    if license_status.status != LicenseStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active AgentHive license is required before adding licensed resources.",
        )
    limit = _capacity_limit(resource, license_status)
    if limit is None:
        return
    if resource == "knowledge_storage_bytes" and increment <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Knowledge document size is required for licensed storage capacity checks.",
        )
    if current_count + increment > limit:
        label = _capacity_label(resource)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"License capacity exceeded for {label}: "
                f"{_format_capacity_usage(resource, current_count)}/"
                f"{_format_capacity_usage(resource, limit)} currently used."
            ),
        )


def _capacity_limit(
    resource: Literal["users", "agents", "knowledge_storage_bytes"],
    license_status: LicenseStatusResponse,
) -> int | None:
    if resource == "users":
        return license_status.max_users
    if resource == "agents":
        return license_status.max_agents
    if license_status.max_kb_size_gb is None:
        return None
    return int(Decimal(license_status.max_kb_size_gb) * Decimal(1024**3))


def _capacity_label(resource: Literal["users", "agents", "knowledge_storage_bytes"]) -> str:
    if resource == "users":
        return "users"
    if resource == "agents":
        return "Agent instances"
    return "knowledge storage"


def _format_capacity_usage(
    resource: Literal["users", "agents", "knowledge_storage_bytes"],
    value: int,
) -> str:
    if resource != "knowledge_storage_bytes":
        return str(value)
    return f"{Decimal(value) / Decimal(1024**3):.2f} GiB"


def _license_identity_issues(license_record: License, identity: InstallIdentity) -> list[str]:
    issues: list[str] = []
    if license_record.deployment_id != identity.deployment_id:
        issues.append("deployment_id_mismatch")
    if license_record.install_id != identity.install_id:
        issues.append("install_id_mismatch")
    if license_record.machine_fingerprint_hash != identity.machine_fingerprint_hash:
        issues.append("machine_fingerprint_mismatch")
    return issues


def _status_from_key(normalized_key: str) -> LicenseStatus:
    if normalized_key.startswith("expired"):
        return LicenseStatus.EXPIRED
    if normalized_key.startswith("revoked"):
        return LicenseStatus.REVOKED
    if normalized_key.startswith("mismatch"):
        return LicenseStatus.MISMATCH
    return LicenseStatus.ACTIVE


def _activation_message(status: LicenseStatus) -> str:
    messages = {
        LicenseStatus.ACTIVE: "License activated for this deployment.",
        LicenseStatus.EXPIRED: "License data accepted, but the license is expired.",
        LicenseStatus.REVOKED: "License data accepted, but the license is revoked.",
        LicenseStatus.MISMATCH: "License data accepted, but it does not match this deployment.",
        LicenseStatus.INACTIVE: "License is inactive.",
    }
    return messages[status]


def _known_module_names() -> dict[str, str]:
    return {
        "agent.customer_service": "电商客服助手",
        "agent.hr_screening": "HR简历筛选助手",
        "agent.copywriting": "文案创作助手",
        "agent.content_analysis": "爆款内容拆解助手",
        "agent.report_writer": "项目汇报助手",
        "agent.product_design": "新品设计辅助",
        "agent.finance": "财务效率助手",
        "agent.store_operations": "店铺运营助手",
        "agent.data_analyst": "数据分析助手",
    }


def _known_feature_names() -> dict[str, str]:
    return {
        "feature.agent_catalog": "Agent模块目录",
        "feature.license_offline_activation": "离线License激活",
        "feature.model_budget": "模型预算治理",
        "channel.web_widget": "网页Widget接入",
        "channel.rest_api": "REST API接入",
        "channel.wecom": "企业微信接入",
        "channel.dingtalk": "钉钉接入",
        "channel.feishu": "飞书接入",
    }
