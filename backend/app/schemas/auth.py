from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class BootstrapRequest(BaseModel):
    tenant_name: str = Field(min_length=2, max_length=100)
    tenant_slug: str = Field(min_length=2, max_length=50, pattern=r"^[a-z0-9][a-z0-9-]*$")
    admin_email: EmailStr
    admin_password: str = Field(min_length=10, max_length=128)
    admin_full_name: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    tenant_slug: str = Field(min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class SetupStatusResponse(BaseModel):
    initialized: bool
    tenant_count: int
    setup_available: bool = True
    message: str | None = None
    diagnostics: dict[str, object] = Field(default_factory=dict)


class AuthUser(BaseModel):
    id: UUID
    tenant_id: UUID
    email: EmailStr
    full_name: str | None
    is_tenant_admin: bool
    is_super_admin: bool
    permissions: list[str]


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: AuthUser


class LogoutResponse(BaseModel):
    message: str


class BootstrapResponse(BaseModel):
    tenant_id: UUID
    admin_user_id: UUID
    message: str
    auth: AuthTokenResponse
