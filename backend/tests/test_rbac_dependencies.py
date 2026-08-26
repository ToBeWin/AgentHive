import unittest
from uuid import UUID

from fastapi import HTTPException

from app.api import deps
from app.api.deps import (
    Principal,
    get_current_principal,
    require_all_permissions,
    require_any_permission,
    require_permission,
)
from app.core.security import Permission, create_access_token
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.org_admin import RoleCreateRequest
from app.services.org_admin_service import list_role_permissions, list_role_presets


class RBACDependenciesTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._old_environment = deps.settings.environment
        self._old_auth_cookie_enabled = deps.settings.auth_cookie_enabled

    def tearDown(self) -> None:
        deps.settings.environment = self._old_environment
        deps.settings.auth_cookie_enabled = self._old_auth_cookie_enabled

    async def test_principal_permission_helpers_respect_tenant_admin(self) -> None:
        principal = Principal(
            user_id=UUID("00000000-0000-4000-8000-000000000101"),
            tenant_id=UUID("00000000-0000-4000-8000-000000000201"),
            permissions={Permission.TENANT_ADMIN.value},
        )

        self.assertTrue(principal.has_permission(Permission.BUDGETS_WRITE))
        self.assertTrue(principal.has_permission(Permission.BUDGETS_EXPORT))
        self.assertTrue(
            principal.has_any_permission({Permission.AGENTS_WRITE, Permission.AUDIT_READ})
        )
        self.assertTrue(
            principal.has_all_permissions({Permission.MODELS_WRITE, Permission.LICENSE_WRITE})
        )

    async def test_require_permission_accepts_valid_token_permission(self) -> None:
        token = create_access_token(
            subject=UUID("00000000-0000-4000-8000-000000000102"),
            tenant_id=UUID("00000000-0000-4000-8000-000000000202"),
            permissions=[Permission.AGENTS_READ.value],
        )

        principal = await require_permission(Permission.AGENTS_READ)(
            authorization=f"Bearer {token}"
        )

        self.assertEqual(UUID("00000000-0000-4000-8000-000000000102"), principal.user_id)
        self.assertIn(Permission.AGENTS_READ.value, principal.permissions)

    async def test_role_create_request_accepts_budget_export_permission(self) -> None:
        payload = RoleCreateRequest(
            name="Cost Auditor",
            permissions=[Permission.BUDGETS_READ, Permission.BUDGETS_EXPORT],
        )

        self.assertEqual(
            [Permission.BUDGETS_READ, Permission.BUDGETS_EXPORT],
            payload.permissions,
        )

    async def test_role_permission_catalog_exposes_all_assignable_permissions(self) -> None:
        catalog = list_role_permissions()
        values = {permission.value for permission in catalog.permissions}

        self.assertEqual(len(Permission), catalog.total)
        self.assertEqual({permission.value for permission in Permission}, values)
        self.assertIn(Permission.BUDGETS_EXPORT.value, values)
        self.assertIn(Permission.ANALYTICS_READ.value, values)
        self.assertIn(Permission.CHANNELS_READ.value, values)
        self.assertIn(Permission.CHANNELS_WRITE.value, values)
        self.assertIn(Permission.MCP_READ.value, values)
        self.assertIn(Permission.MCP_WRITE.value, values)
        self.assertIn(Permission.MCP_INVOKE.value, values)
        self.assertIn(Permission.SYSTEM_DIAGNOSTICS.value, values)
        self.assertTrue(
            any(
                permission.value == Permission.BUDGETS_EXPORT.value
                and permission.category == "budgets"
                and permission.label
                for permission in catalog.permissions
            )
        )
        self.assertTrue(
            any(
                permission.value == Permission.CHANNELS_WRITE.value
                and permission.category == "channels"
                and permission.label
                for permission in catalog.permissions
            )
        )
        self.assertTrue(
            any(
                permission.value == Permission.SYSTEM_DIAGNOSTICS.value
                and permission.category == "system"
                and permission.label
                for permission in catalog.permissions
            )
        )
        self.assertTrue(
            any(
                permission.value == Permission.ANALYTICS_READ.value
                and permission.category == "analytics"
                and permission.label
                for permission in catalog.permissions
            )
        )

    async def test_role_presets_cover_enterprise_operating_roles(self) -> None:
        presets = list_role_presets()
        known_permissions = {permission.value for permission in Permission}
        preset_by_key = {preset.key: preset for preset in presets.presets}

        self.assertEqual(7, presets.total)
        self.assertIn("enterprise_admin", preset_by_key)
        self.assertIn("model_admin", preset_by_key)
        self.assertIn("agent_admin", preset_by_key)
        self.assertIn("department_leader", preset_by_key)
        self.assertIn("employee", preset_by_key)
        self.assertIn("audit_finance", preset_by_key)
        self.assertEqual(
            [Permission.TENANT_ADMIN.value], preset_by_key["enterprise_admin"].permissions
        )
        self.assertEqual(
            {
                Permission.USERS_READ.value,
                Permission.DEPARTMENTS_READ.value,
                Permission.AGENTS_READ.value,
                Permission.CHAT_READ.value,
                Permission.CHANNELS_READ.value,
                Permission.CHANNELS_WRITE.value,
                Permission.LICENSE_READ.value,
                Permission.AUDIT_READ.value,
                Permission.SYSTEM_DIAGNOSTICS.value,
            },
            set(preset_by_key["implementation_operator"].permissions),
        )
        self.assertEqual(
            {
                Permission.MODELS_READ.value,
                Permission.MODELS_WRITE.value,
                Permission.BUDGETS_READ.value,
                Permission.AUDIT_READ.value,
            },
            set(preset_by_key["model_admin"].permissions),
        )
        self.assertEqual(
            {
                Permission.AGENTS_READ.value,
                Permission.AGENTS_WRITE.value,
                Permission.CHAT_READ.value,
                Permission.CHAT_WRITE.value,
                Permission.KNOWLEDGE_READ.value,
                Permission.KNOWLEDGE_WRITE.value,
                Permission.CHANNELS_READ.value,
            },
            set(preset_by_key["agent_admin"].permissions),
        )
        self.assertEqual(
            {
                Permission.AGENTS_READ.value,
                Permission.CHAT_READ.value,
                Permission.CHAT_WRITE.value,
                Permission.KNOWLEDGE_READ.value,
            },
            set(preset_by_key["employee"].permissions),
        )
        self.assertEqual(
            {
                Permission.BUDGETS_READ.value,
                Permission.BUDGETS_EXPORT.value,
                Permission.AUDIT_READ.value,
                Permission.AUDIT_EXPORT.value,
                Permission.ANALYTICS_READ.value,
            },
            set(preset_by_key["audit_finance"].permissions),
        )
        self.assertEqual("department", preset_by_key["department_leader"].scope)

        for preset in presets.presets:
            self.assertTrue(preset.name)
            self.assertTrue(preset.description)
            self.assertLessEqual(set(preset.permissions), known_permissions)

    async def test_require_permission_rejects_missing_permission(self) -> None:
        token = create_access_token(
            subject=UUID("00000000-0000-4000-8000-000000000103"),
            tenant_id=UUID("00000000-0000-4000-8000-000000000203"),
            permissions=[Permission.AGENTS_READ.value],
        )

        with self.assertRaises(HTTPException) as raised:
            await require_permission(Permission.AGENTS_WRITE)(authorization=f"Bearer {token}")

        self.assertEqual(403, raised.exception.status_code)

    async def test_require_any_permission_accepts_one_match(self) -> None:
        token = create_access_token(
            subject=UUID("00000000-0000-4000-8000-000000000104"),
            tenant_id=UUID("00000000-0000-4000-8000-000000000204"),
            permissions=[Permission.USERS_READ.value],
        )

        principal = await require_any_permission(Permission.USERS_WRITE, Permission.USERS_READ)(
            authorization=f"Bearer {token}"
        )

        self.assertIn(Permission.USERS_READ.value, principal.permissions)

    async def test_require_all_permissions_requires_every_permission(self) -> None:
        token = create_access_token(
            subject=UUID("00000000-0000-4000-8000-000000000105"),
            tenant_id=UUID("00000000-0000-4000-8000-000000000205"),
            permissions=[Permission.KNOWLEDGE_READ.value],
        )

        with self.assertRaises(HTTPException) as raised:
            await require_all_permissions(Permission.KNOWLEDGE_READ, Permission.KNOWLEDGE_WRITE)(
                authorization=f"Bearer {token}"
            )

        self.assertEqual(403, raised.exception.status_code)

    async def test_missing_authorization_is_unauthorized_outside_development(self) -> None:
        deps.settings.environment = "production"

        with self.assertRaises(HTTPException) as raised:
            await get_current_principal(authorization=None)

        self.assertEqual(401, raised.exception.status_code)

    async def test_cookie_session_requires_matching_csrf_token(self) -> None:
        deps.settings.environment = "production"
        deps.settings.auth_cookie_enabled = True
        token = create_access_token(
            subject=UUID("00000000-0000-4000-8000-000000000108"),
            tenant_id=UUID("00000000-0000-4000-8000-000000000208"),
            permissions=[Permission.AGENTS_READ.value],
        )

        principal = await get_current_principal(
            authorization=None,
            session_cookie=token,
            csrf_cookie="csrf-value",
            csrf_header="csrf-value",
        )

        self.assertEqual(UUID("00000000-0000-4000-8000-000000000108"), principal.user_id)

    async def test_cookie_session_rejects_missing_or_invalid_csrf_token(self) -> None:
        deps.settings.environment = "production"
        deps.settings.auth_cookie_enabled = True
        token = create_access_token(
            subject=UUID("00000000-0000-4000-8000-000000000109"),
            tenant_id=UUID("00000000-0000-4000-8000-000000000209"),
            permissions=[Permission.AGENTS_READ.value],
        )

        with self.assertRaises(HTTPException) as raised:
            await get_current_principal(
                authorization=None,
                session_cookie=token,
                csrf_cookie="csrf-value",
                csrf_header="wrong-value",
            )

        self.assertEqual(403, raised.exception.status_code)

    async def test_require_permission_rejects_inactive_user_even_with_valid_token(self) -> None:
        tenant_id = UUID("00000000-0000-4000-8000-000000000206")
        user_id = UUID("00000000-0000-4000-8000-000000000106")
        token = create_access_token(
            subject=user_id,
            tenant_id=tenant_id,
            permissions=[Permission.AGENTS_READ.value],
        )
        session = FakePrincipalSession(
            user=User(
                id=user_id,
                tenant_id=tenant_id,
                email="inactive@example.com",
                hashed_password="bcrypt-sha256$placeholder",
                is_active=False,
            ),
            tenant=Tenant(id=tenant_id, name="Demo", slug="demo", is_active=True),
        )

        with self.assertRaises(HTTPException) as raised:
            await require_permission(Permission.AGENTS_READ)(
                authorization=f"Bearer {token}",
                session=session,
            )

        self.assertEqual(401, raised.exception.status_code)
        self.assertIn("inactive", str(raised.exception.detail))

    async def test_require_permission_accepts_active_user_session(self) -> None:
        tenant_id = UUID("00000000-0000-4000-8000-000000000207")
        user_id = UUID("00000000-0000-4000-8000-000000000107")
        token = create_access_token(
            subject=user_id,
            tenant_id=tenant_id,
            permissions=[Permission.AGENTS_READ.value],
        )
        session = FakePrincipalSession(
            user=User(
                id=user_id,
                tenant_id=tenant_id,
                email="active@example.com",
                hashed_password="bcrypt-sha256$placeholder",
                is_active=True,
            ),
            tenant=Tenant(id=tenant_id, name="Demo", slug="demo", is_active=True),
        )

        principal = await require_permission(Permission.AGENTS_READ)(
            authorization=f"Bearer {token}",
            session=session,
        )

        self.assertEqual(user_id, principal.user_id)

    async def test_require_permission_rejects_revoked_auth_version(self) -> None:
        tenant_id = UUID("00000000-0000-4000-8000-000000000208")
        user_id = UUID("00000000-0000-4000-8000-000000000108")
        token = create_access_token(
            subject=user_id,
            tenant_id=tenant_id,
            permissions=[Permission.AGENTS_READ.value],
            auth_version=1,
        )
        session = FakePrincipalSession(
            user=User(
                id=user_id,
                tenant_id=tenant_id,
                email="revoked@example.com",
                hashed_password="bcrypt-sha256$placeholder",
                is_active=True,
                auth_version=2,
            ),
            tenant=Tenant(id=tenant_id, name="Demo", slug="demo", is_active=True),
        )

        with self.assertRaises(HTTPException) as raised:
            await require_permission(Permission.AGENTS_READ)(
                authorization=f"Bearer {token}",
                session=session,
            )

        self.assertEqual(401, raised.exception.status_code)


class FakePrincipalSession:
    def __init__(self, *, user: User | None, tenant: Tenant | None) -> None:
        self.user = user
        self.tenant = tenant

    async def get(self, model: object, _row_id: object) -> object:
        if model is User:
            return self.user
        if model is Tenant:
            return self.tenant
        return None


if __name__ == "__main__":
    unittest.main()
