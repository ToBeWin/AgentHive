from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class LicenseStatus(str, Enum):
    INACTIVE = "inactive"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    MISMATCH = "mismatch"


class AgentModuleState(str, Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    EXPIRED = "expired"
    NOT_LICENSED = "not_licensed"


class DeploymentFingerprintResponse(BaseModel):
    product: str
    deployment_id: UUID
    install_id: UUID
    machine_fingerprint_hash: str
    fingerprint_algorithm: str
    generated_at: datetime


class LicenseActivationRequest(BaseModel):
    license_key: str = Field(min_length=1, max_length=32768)
    activation_code: str | None = Field(default=None, max_length=4096)


class LicenseActivationRequestExport(BaseModel):
    product: str
    tenant_id: UUID
    deployment_id: UUID
    install_id: UUID
    machine_fingerprint_hash: str
    fingerprint_algorithm: str
    generated_at: datetime
    request_id: str
    request_code: str
    request_hash: str
    request_format: str = "agenthive.offline_activation_request.v1"
    schema_version: int = 1


class LicenseVerificationResponse(BaseModel):
    mode: str
    valid: bool
    status: LicenseStatus
    reason: str
    signature_alg: str | None = None
    license_id: str | None = None


class AuthorizedFeature(BaseModel):
    id: str
    name: str
    enabled: bool


class AuthorizedModule(BaseModel):
    id: str
    name: str
    state: AgentModuleState
    licensed: bool
    installed: bool
    enabled: bool


class LicenseStatusResponse(BaseModel):
    status: LicenseStatus
    license_type: str
    customer_name: str
    deployment_id: UUID
    install_id: UUID
    machine_fingerprint_hash: str
    runtime_deployment_id: UUID | None = None
    runtime_install_id: UUID | None = None
    runtime_machine_fingerprint_hash: str | None = None
    verification_issues: list[str] = Field(default_factory=list)
    allowed_modules: list[str]
    allowed_features: list[str]
    maintenance_until: datetime | None
    expires_at: datetime | None
    activated_at: datetime | None
    max_users: int | None = None
    max_agents: int | None = None
    max_kb_size_gb: Decimal | None = None
    module_count: int
    feature_count: int


class LicenseActivationResponse(BaseModel):
    status: LicenseStatus
    message: str
    license: LicenseStatusResponse
    verification: LicenseVerificationResponse | None = None


class LicenseModulesResponse(BaseModel):
    modules: list[AuthorizedModule]
    features: list[AuthorizedFeature]


class LicenseDeactivateResponse(BaseModel):
    status: LicenseStatus
    message: str
    deactivated_at: datetime
