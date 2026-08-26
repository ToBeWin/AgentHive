import base64
from datetime import datetime, timezone
from decimal import Decimal
import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel, Field, field_validator


class SignedLicensePayload(BaseModel):
    schema_version: int = 1
    product: str = "AgentHive"
    license_id: str = Field(min_length=1, max_length=120)
    license_type: str = Field(min_length=1, max_length=40)
    customer_name: str = Field(min_length=1, max_length=150)
    tenant_id: str | None = None
    deployment_id: str
    install_id: str
    machine_fingerprint_hash: str = Field(min_length=64, max_length=128)
    allowed_modules: list[str] = Field(default_factory=list)
    allowed_features: list[str] = Field(default_factory=list)
    max_users: int | None = Field(default=None, ge=1)
    max_agents: int | None = Field(default=None, ge=1)
    max_kb_size_gb: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    maintenance_until: datetime | None = None
    expires_at: datetime | None = None
    issued_at: datetime
    not_before: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("allowed_modules", "allowed_features")
    @classmethod
    def sorted_unique(cls, value: list[str]) -> list[str]:
        return sorted(set(value))


class SignedLicenseEnvelope(BaseModel):
    payload: SignedLicensePayload
    signature_alg: str = "Ed25519"
    signature: str


class LicenseVerificationResult(BaseModel):
    valid: bool
    status: str
    reason: str
    envelope: SignedLicenseEnvelope | None = None


def parse_signed_license(raw: str) -> SignedLicenseEnvelope:
    try:
        document = json.loads(raw)
    except json.JSONDecodeError:
        decoded = base64.b64decode(raw.encode("utf-8"), validate=True).decode("utf-8")
        document = json.loads(decoded)
    return SignedLicenseEnvelope.model_validate(document)


def verify_signed_license(
    *,
    raw: str,
    public_key_pem: str,
    deployment_id: str,
    install_id: str,
    machine_fingerprint_hash: str,
    tenant_id: str | None = None,
    now: datetime | None = None,
) -> LicenseVerificationResult:
    checked_at = now or datetime.now(timezone.utc)
    try:
        envelope = parse_signed_license(raw)
    except Exception as exc:
        return LicenseVerificationResult(
            valid=False,
            status="invalid",
            reason=f"license_parse_failed:{exc.__class__.__name__}",
        )

    if envelope.signature_alg != "Ed25519":
        return LicenseVerificationResult(
            valid=False,
            status="invalid",
            reason="unsupported_signature_algorithm",
            envelope=envelope,
        )

    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        if not isinstance(public_key, Ed25519PublicKey):
            return LicenseVerificationResult(
                valid=False,
                status="invalid",
                reason="public_key_is_not_ed25519",
                envelope=envelope,
            )
        public_key.verify(
            base64.b64decode(envelope.signature.encode("utf-8"), validate=True),
            canonical_license_payload(envelope.payload),
        )
    except (InvalidSignature, ValueError):
        return LicenseVerificationResult(
            valid=False,
            status="invalid",
            reason="signature_verification_failed",
            envelope=envelope,
        )

    payload = envelope.payload
    if payload.product != "AgentHive":
        return _mismatch("product_mismatch", envelope)
    if tenant_id and payload.tenant_id and payload.tenant_id != tenant_id:
        return _mismatch("tenant_id_mismatch", envelope)
    if payload.deployment_id != deployment_id:
        return _mismatch("deployment_id_mismatch", envelope)
    if payload.install_id != install_id:
        return _mismatch("install_id_mismatch", envelope)
    if payload.machine_fingerprint_hash != machine_fingerprint_hash:
        return _mismatch("machine_fingerprint_mismatch", envelope)
    if payload.not_before and payload.not_before > checked_at:
        return LicenseVerificationResult(
            valid=False,
            status="inactive",
            reason="license_not_before_current_time",
            envelope=envelope,
        )
    if payload.expires_at and payload.expires_at <= checked_at:
        return LicenseVerificationResult(
            valid=False,
            status="expired",
            reason="license_expired",
            envelope=envelope,
        )

    return LicenseVerificationResult(
        valid=True,
        status="active",
        reason="signature_and_machine_binding_verified",
        envelope=envelope,
    )


def canonical_license_payload(payload: SignedLicensePayload) -> bytes:
    return json.dumps(
        payload.model_dump(mode="json", exclude_none=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _mismatch(reason: str, envelope: SignedLicenseEnvelope) -> LicenseVerificationResult:
    return LicenseVerificationResult(
        valid=False,
        status="mismatch",
        reason=reason,
        envelope=envelope,
    )
