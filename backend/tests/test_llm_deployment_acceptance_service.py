from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4
import unittest

from fastapi import HTTPException

from app.api.deps import Principal
from app.schemas.llm import (
    LLMChatResponse,
    LLMDeploymentAcceptanceTestRequest,
    LLMUsageResponse,
)
from app.services.llm_service import DeploymentAcceptanceTarget, verify_model_deployment_call


class FakeAcceptanceSession:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, row):
        self.added.append(row)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def make_principal() -> Principal:
    return Principal(
        tenant_id=uuid4(),
        user_id=uuid4(),
        permissions={"models:write"},
    )


class LLMDeploymentAcceptanceServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_acceptance_test_runs_gateway_with_saved_deployment_route_and_records_audit(self):
        session = FakeAcceptanceSession()
        principal = make_principal()
        deployment_id = uuid4()
        target = DeploymentAcceptanceTarget(
            deployment_id=deployment_id,
            provider_key="deepseek",
            model_key="deepseek-v4-flash",
            routing_key="deepseek-chat",
            credential_configured=True,
        )
        gateway_response = LLMChatResponse(
            request_id="acceptance-response-request",
            provider_key="deepseek",
            deployment_id=deployment_id,
            model_key="deepseek-v4-flash",
            content="AgentHive acceptance check ok.",
            finish_reason="stop",
            usage=LLMUsageResponse(
                input_tokens=8,
                output_tokens=6,
                total_tokens=14,
                cost_usd=Decimal("0.000014"),
            ),
            metadata={
                "fallback_attempt_count": 0,
                "live_network_call": True,
                "mock": False,
                "pricing_rule": "deepseek-v4-flash",
                "route_attempts": [
                    {
                        "attempt": 1,
                        "deployment_id": str(deployment_id),
                        "provider_key": "deepseek",
                        "model_key": "deepseek-v4-flash",
                        "routing_key": "deepseek-chat",
                        "status": "success",
                    }
                ],
                "selected_route_reason": "direct",
            },
        )

        with (
            patch(
                "app.services.llm_service._get_acceptance_target", AsyncMock(return_value=target)
            ),
            patch(
                "app.services.llm_service.run_gateway_chat",
                AsyncMock(return_value=gateway_response),
            ) as run_chat,
        ):
            response = await verify_model_deployment_call(
                session,
                deployment_id,
                principal,
                LLMDeploymentAcceptanceTestRequest(prompt="ping", max_tokens=32),
                request_id="req-acceptance",
            )

        run_payload = run_chat.await_args.args[0]
        self.assertEqual("deepseek-chat", run_payload.routing_key)
        self.assertEqual("ping", run_payload.messages[0].content)
        self.assertEqual(32, run_payload.max_tokens)
        self.assertTrue(response.ok)
        self.assertEqual(deployment_id, response.deployment_id)
        self.assertEqual("deepseek-chat", response.routing_key)
        self.assertTrue(response.live_network_call)
        self.assertFalse(response.mock)
        self.assertTrue(response.usage_recorded)
        self.assertEqual(1, session.commits)
        event = session.added[0]
        self.assertEqual("llm.deployment.acceptance_test", event.action)
        self.assertEqual("req-acceptance", event.request_id)
        self.assertEqual(str(deployment_id), event.details["deployment_id"])
        self.assertTrue(event.details["ok"])
        self.assertEqual("deployment_acceptance_test", event.details["operation"])
        self.assertEqual("saved_deployment", event.details["configuration_source"])
        self.assertTrue(event.details["live_network_call"])

    async def test_acceptance_test_records_failure_audit_when_gateway_call_fails(self):
        session = FakeAcceptanceSession()
        principal = make_principal()
        deployment_id = uuid4()
        target = DeploymentAcceptanceTarget(
            deployment_id=deployment_id,
            provider_key="mimo",
            model_key="mimo-chat",
            routing_key="mimo-chat",
            credential_configured=True,
        )

        with (
            patch(
                "app.services.llm_service._get_acceptance_target", AsyncMock(return_value=target)
            ),
            patch(
                "app.services.llm_service.run_gateway_chat",
                AsyncMock(side_effect=HTTPException(status_code=502, detail="provider timeout")),
            ),
        ):
            with self.assertRaises(HTTPException):
                await verify_model_deployment_call(
                    session,
                    deployment_id,
                    principal,
                    LLMDeploymentAcceptanceTestRequest(prompt="ping", max_tokens=32),
                    request_id="req-acceptance-failed",
                )

        self.assertEqual(1, session.commits)
        self.assertGreaterEqual(session.rollbacks, 1)
        event = session.added[0]
        self.assertEqual("llm.deployment.acceptance_test", event.action)
        self.assertEqual("failure", event.status)
        self.assertEqual("req-acceptance-failed", event.request_id)
        self.assertEqual(str(deployment_id), event.details["deployment_id"])
        self.assertFalse(event.details["ok"])
        self.assertEqual("deployment_acceptance_test", event.details["operation"])
        self.assertEqual("saved_deployment", event.details["configuration_source"])
        self.assertEqual("mimo", event.details["provider_key"])
        self.assertEqual("mimo-chat", event.details["model_key"])
        self.assertEqual("mimo-chat", event.details["routing_key"])
        self.assertEqual(502, event.details["status_code"])
        self.assertEqual("provider timeout", event.details["message"])


if __name__ == "__main__":
    unittest.main()
