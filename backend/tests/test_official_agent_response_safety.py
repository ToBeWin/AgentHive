import unittest

from app.agents.official.response_safety import (
    normalize_agenthive_brand,
    sanitize_official_agent_answer,
)


class OfficialAgentResponseSafetyTests(unittest.TestCase):
    def test_normalizes_agenthive_brand_variants(self) -> None:
        answer = normalize_agenthive_brand("AgentH Hive 和 Agent Hive 都应该统一为 AgentHive。")

        self.assertEqual("AgentHive 和 AgentHive 都应该统一为 AgentHive。", answer)

    def test_sanitizes_internal_runtime_diagnostics(self) -> None:
        answer = sanitize_official_agent_answer(
            "已为你生成可直接使用的回复。\n"
            "request_id: req_123\n"
            "模型Key：deepseek-v4-flash\n"
            "Token: 120\n"
            "检索分数：0.12",
            fallback="请补充更多信息后重试。",
        )

        self.assertEqual("已为你生成可直接使用的回复。", answer)

    def test_uses_fallback_when_answer_becomes_empty(self) -> None:
        answer = sanitize_official_agent_answer(
            "request_id: req_123\nToken: 120",
            fallback="请补充更多信息后重试。",
        )

        self.assertEqual("请补充更多信息后重试。", answer)
