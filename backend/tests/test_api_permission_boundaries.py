import unittest

from app.api.v1 import agent_modules, agents, knowledge, media
from app.core.security import Permission


class ApiPermissionBoundaryTest(unittest.TestCase):
    def test_agent_management_routes_require_agent_write(self) -> None:
        expected = {
            ("GET", "/agents/catalog"),
            ("GET", "/agents/instances"),
            ("GET", "/agents/governance-targets"),
            ("POST", "/agents/instances"),
            ("GET", "/agents/instances/{agent_id}"),
            ("PATCH", "/agents/instances/{agent_id}"),
            ("POST", "/agents/{agent_key}/run"),
        }

        for method, path in expected:
            with self.subTest(method=method, path=path):
                self.assertEqual(
                    Permission.AGENTS_WRITE, _route_permission(agents.router, method, path)
                )

    def test_workbench_agent_route_allows_employee_chat_permissions(self) -> None:
        permissions = _route_permission(agents.router, "GET", "/agents/workbench/instances")

        self.assertEqual(
            {Permission.CHAT_READ, Permission.CHAT_WRITE, Permission.AGENTS_READ},
            permissions,
        )

    def test_agent_module_management_routes_require_agent_write(self) -> None:
        for method, path in {
            ("GET", "/agent-modules"),
            ("GET", "/agent-modules/{id}"),
            ("POST", "/agent-modules/{id}/install"),
            ("POST", "/agent-modules/{id}/enable"),
            ("POST", "/agent-modules/{id}/disable"),
        }:
            with self.subTest(method=method, path=path):
                self.assertEqual(
                    Permission.AGENTS_WRITE, _route_permission(agent_modules.router, method, path)
                )

    def test_knowledge_management_diagnostics_require_knowledge_write(self) -> None:
        for method, path in {
            ("GET", "/knowledge/bases"),
            ("GET", "/knowledge/bases/{id}/documents"),
            ("GET", "/knowledge/governance-targets"),
            ("POST", "/knowledge/bases/{id}/retrieval-test"),
        }:
            with self.subTest(method=method, path=path):
                self.assertEqual(
                    Permission.KNOWLEDGE_WRITE, _route_permission(knowledge.router, method, path)
                )

    def test_employee_safe_knowledge_read_routes_keep_knowledge_read(self) -> None:
        for method, path in {
            ("GET", "/knowledge/workbench/bases"),
            ("GET", "/knowledge/workbench/bases/{id}/documents"),
        }:
            with self.subTest(method=method, path=path):
                self.assertEqual(
                    Permission.KNOWLEDGE_READ, _route_permission(knowledge.router, method, path)
                )

    def test_employee_media_enqueue_route_allows_chat_write(self) -> None:
        permissions = _route_permission(media.router, "POST", "/media/generations/{job_id}/enqueue")

        self.assertEqual({Permission.AGENTS_WRITE, Permission.CHAT_WRITE}, permissions)


def _route_permission(router, method: str, path: str):
    for route in router.routes:
        if route.path == path and method in route.methods:
            permissions = [
                closure.cell_contents
                for dependency in route.dependant.dependencies
                for closure in (dependency.call.__closure__ or [])
                if isinstance(closure.cell_contents, Permission)
                or isinstance(closure.cell_contents, set)
            ]
            if permissions:
                return permissions[-1]
    raise AssertionError(f"Route not found or no permission dependency: {method} {path}")
