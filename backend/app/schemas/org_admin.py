from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.security import Permission


class DepartmentCreateRequest(BaseModel):
    parent_id: UUID | None = None
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    sort_order: int = 0


class DepartmentUpdateRequest(BaseModel):
    parent_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    sort_order: int | None = None


class DepartmentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    parent_id: UUID | None
    name: str
    description: str | None
    sort_order: int
    created_at: datetime
    updated_at: datetime


class DepartmentTreeNode(DepartmentResponse):
    children: list[DepartmentTreeNode] = Field(default_factory=list)


class DepartmentListResponse(BaseModel):
    departments: list[DepartmentResponse] = Field(default_factory=list)
    tree: list[DepartmentTreeNode] = Field(default_factory=list)
    total: int = 0


class DeleteResponse(BaseModel):
    id: UUID
    deleted: bool = True


class CostCenterCreateRequest(BaseModel):
    department_id: UUID | None = None
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    monthly_budget_usd: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=4,
    )
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class CostCenterUpdateRequest(BaseModel):
    department_id: UUID | None = None
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    monthly_budget_usd: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=4,
    )
    is_active: bool | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else value


class CostCenterResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    department_id: UUID | None
    code: str
    name: str
    description: str | None
    monthly_budget_usd: Decimal | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CostCenterListResponse(BaseModel):
    cost_centers: list[CostCenterResponse] = Field(default_factory=list)
    total: int = 0


class UserDepartmentBindingRequest(BaseModel):
    department_id: UUID
    is_leader: bool = False
    is_primary: bool = False
    position_title: str | None = Field(default=None, max_length=100)
    cost_center_id: UUID | None = None


class UserDepartmentBindingResponse(UserDepartmentBindingRequest):
    department_name: str | None = None
    cost_center_code: str | None = None
    cost_center_name: str | None = None


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    username: str | None = Field(default=None, max_length=50)
    full_name: str | None = Field(default=None, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=1000)
    phone: str | None = Field(default=None, max_length=20)
    is_tenant_admin: bool = False
    is_active: bool = True
    department_bindings: list[UserDepartmentBindingRequest] = Field(default_factory=list)
    role_ids: list[UUID] = Field(default_factory=list)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class UserStatusUpdateRequest(BaseModel):
    is_active: bool


class UserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    username: str | None = Field(default=None, max_length=50)
    full_name: str | None = Field(default=None, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=1000)
    phone: str | None = Field(default=None, max_length=20)
    is_tenant_admin: bool | None = None
    department_bindings: list[UserDepartmentBindingRequest] | None = None
    role_ids: list[UUID] | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return value.lower() if value else value


class UserPasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


class UserRoleResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    permissions: list[str] = Field(default_factory=list)
    is_system: bool


class UserResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    email: str
    username: str | None
    full_name: str | None
    avatar_url: str | None
    phone: str | None
    is_super_admin: bool
    is_tenant_admin: bool
    is_active: bool
    last_login_at: datetime | None
    departments: list[UserDepartmentBindingResponse] = Field(default_factory=list)
    roles: list[UserRoleResponse] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    users: list[UserResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0


class RoleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[Permission] = Field(default_factory=list)
    is_system: bool = False


class RoleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[Permission] | None = None


class RoleResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    permissions: list[str] = Field(default_factory=list)
    is_system: bool
    created_at: datetime
    updated_at: datetime


class RoleDeleteResponse(BaseModel):
    id: UUID
    deleted: bool = True


class RoleListResponse(BaseModel):
    roles: list[RoleResponse] = Field(default_factory=list)
    total: int = 0


class PermissionCatalogItem(BaseModel):
    value: str
    category: str
    label: str


class PermissionCatalogResponse(BaseModel):
    permissions: list[PermissionCatalogItem] = Field(default_factory=list)
    total: int = 0


class RolePresetItem(BaseModel):
    key: str
    name: str
    description: str
    permissions: list[str] = Field(default_factory=list)
    scope: str
    category: str


class RolePresetResponse(BaseModel):
    presets: list[RolePresetItem] = Field(default_factory=list)
    total: int = 0
