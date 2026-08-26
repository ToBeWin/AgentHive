"""Tests for app.agents.official.prompt_registry."""

import json
import unittest
from pathlib import Path

from app.agents.official.prompt_registry import (
    OfficialPromptConfig,
    ensure_loaded,
    get_output_prompt,
    get_prompt_config,
    get_role_prompt,
    list_prompt_configs,
    reload_prompt_configs,
)


class OfficialPromptConfigTest(unittest.TestCase):
    """Unit tests for the OfficialPromptConfig dataclass."""

    def test_from_json_full(self) -> None:
        raw = {
            "agent_key": "hr_screening",
            "required_module": "agent.hr_screening",
            "role_prompt": "你是 HR 助手。",
            "output_prompt": "请输出摘要。",
            "output_format": "structured_json",
            "structured_schema_hint": "ResumeScreeningResult",
            "defaults": {"max_candidates": 10},
            "platforms": ["xiaohongshu"],
            "templates": [{"id": "t1"}],
            "brand_guidelines": {"forbidden_words": ["cheap"]},
        }
        config = OfficialPromptConfig.from_json(raw)
        self.assertEqual(config.agent_key, "hr_screening")
        self.assertEqual(config.role_prompt, "你是 HR 助手。")
        self.assertEqual(config.output_prompt, "请输出摘要。")
        self.assertEqual(config.output_format, "structured_json")
        self.assertEqual(config.structured_schema_hint, "ResumeScreeningResult")
        self.assertEqual(config.defaults, {"max_candidates": 10})
        self.assertEqual(config.platforms, ["xiaohongshu"])
        self.assertEqual(config.templates, [{"id": "t1"}])
        self.assertEqual(config.brand_guidelines, {"forbidden_words": ["cheap"]})

    def test_from_json_minimal(self) -> None:
        raw: dict[str, str] = {"agent_key": "test", "required_module": "agent.test"}
        config = OfficialPromptConfig.from_json(raw)
        self.assertEqual(config.role_prompt, "")
        self.assertEqual(config.output_prompt, "")
        self.assertEqual(config.output_format, "text")
        self.assertIsNone(config.structured_schema_hint)
        self.assertEqual(config.defaults, {})
        self.assertEqual(config.platforms, [])
        self.assertEqual(config.templates, [])
        self.assertIsNone(config.brand_guidelines)

    def test_from_json_extra_keys_stored(self) -> None:
        raw = {
            "agent_key": "x",
            "required_module": "agent.x",
            "role_prompt": "r",
            "output_prompt": "o",
            "future_field": "will_be_here",
        }
        config = OfficialPromptConfig.from_json(raw)
        self.assertEqual(config.extra, {"future_field": "will_be_here"})

    def test_from_json_missing_agent_key_graceful(self) -> None:
        raw: dict[str, str] = {"required_module": "agent.x"}
        config = OfficialPromptConfig.from_json(raw)
        self.assertEqual(config.agent_key, "")


class PromptRegistryLoadTest(unittest.TestCase):
    """Tests for loading prompt files from disk."""

    def test_list_prompt_configs_returns_all_json_files(self) -> None:
        """All 9 configured agents should have JSON files in the prompts dir."""
        # Force a fresh load regardless of environment.
        reload_prompt_configs()
        configs = list_prompt_configs()
        # At minimum the 9 OFFICIAL_AGENT_BINDINGS should be present.
        expected_keys = {
            "hr_screening",
            "copywriting",
            "image_generation",
            "video_generation",
            "content_analysis",
            "report_writer",
            "product_design",
            "finance",
            "store_operations",
            "data_analyst",
        }
        loaded_keys = set(configs.keys())
        self.assertTrue(
            expected_keys.issubset(loaded_keys),
            f"Missing prompt configs: {expected_keys - loaded_keys}",
        )

    def test_hr_screening_loaded_correctly(self) -> None:
        config = get_prompt_config("hr_screening")
        self.assertIsNotNone(config)
        assert config is not None  # for type checkers
        self.assertEqual(config.required_module, "agent.hr_screening")
        self.assertIn("简历", config.role_prompt)
        self.assertIn("匹配评分", config.output_prompt)
        self.assertEqual(config.output_format, "structured_json")
        self.assertEqual(config.structured_schema_hint, "ResumeScreeningResult")

    def test_copywriting_loaded_with_platforms(self) -> None:
        config = get_prompt_config("copywriting")
        self.assertIsNotNone(config)
        assert config is not None
        self.assertIn("小红书", config.role_prompt)
        self.assertEqual(config.output_format, "text")
        self.assertIn("xiaohongshu", config.platforms)

    def test_image_generation_has_generation_kind(self) -> None:
        config = get_prompt_config("image_generation")
        self.assertIsNotNone(config)
        assert config is not None
        self.assertEqual(config.defaults.get("generation_kind"), "image")

    def test_video_generation_has_generation_kind(self) -> None:
        config = get_prompt_config("video_generation")
        self.assertIsNotNone(config)
        assert config is not None
        self.assertEqual(config.defaults.get("generation_kind"), "video")

    def test_unknown_agent_key_returns_none(self) -> None:
        self.assertIsNone(get_prompt_config("nonexistent_agent"))


class PromptRegistryAccessorTest(unittest.TestCase):
    """Tests for convenience accessors."""

    def test_get_role_prompt(self) -> None:
        prompt = get_role_prompt("hr_screening")
        self.assertIn("简历", prompt)

    def test_get_role_prompt_unknown_empty(self) -> None:
        self.assertEqual(get_role_prompt("nonexistent"), "")

    def test_get_output_prompt(self) -> None:
        prompt = get_output_prompt("hr_screening")
        self.assertIn("匹配评分", prompt)

    def test_get_output_prompt_unknown_empty(self) -> None:
        self.assertEqual(get_output_prompt("nonexistent"), "")


class PromptRegistryHotReloadTest(unittest.IsolatedAsyncioTestCase):
    """Tests for development-time hot-reload behavior."""

    def setUp(self) -> None:
        # Force fresh state.
        reload_prompt_configs()

    def test_reload_reflects_file_change(self) -> None:
        """After reload_prompt_configs(), updated content is visible."""
        original = get_prompt_config("hr_screening")
        assert original is not None
        self.assertIn("简历", original.role_prompt)

        # Overwrite the file with a different role_prompt.
        prompts_dir = (
            Path(__file__).resolve().parent.parent / "app" / "agents" / "official" / "prompts"
        )
        target = prompts_dir / "hr_screening.json"
        original_content = target.read_text(encoding="utf-8")
        modified = json.loads(original_content)
        modified["role_prompt"] = "你是修改后的 HR 助手。"

        try:
            target.write_text(json.dumps(modified, ensure_ascii=False, indent=2), encoding="utf-8")
            # Force reload (not dev hot-reload, which depends on mtime caching).
            reload_prompt_configs()
            updated = get_prompt_config("hr_screening")
            self.assertIn("修改后的", updated.role_prompt)
        finally:
            # Restore original.
            target.write_text(original_content, encoding="utf-8")

    def test_broken_json_does_not_crash(self) -> None:
        """A malformed JSON file is skipped with a warning, not a crash."""
        prompts_dir = (
            Path(__file__).resolve().parent.parent / "app" / "agents" / "official" / "prompts"
        )
        broken_file = prompts_dir / "_test_broken.json"
        broken_file.write_text("{invalid json content", encoding="utf-8")
        try:
            # Should not raise.
            reload_prompt_configs()
            # The broken file should not appear in configs.
            self.assertIsNone(get_prompt_config("_test_broken"))
        finally:
            broken_file.unlink(missing_ok=True)

    def test_file_missing_agent_key_skipped(self) -> None:
        """A JSON file without agent_key is skipped."""
        prompts_dir = (
            Path(__file__).resolve().parent.parent / "app" / "agents" / "official" / "prompts"
        )
        bad_file = prompts_dir / "_test_no_key.json"
        bad_file.write_text(json.dumps({"required_module": "agent.x"}), encoding="utf-8")
        try:
            reload_prompt_configs()
            # agent_key="" is empty string, not a valid key.
            self.assertIsNone(get_prompt_config(""))
        finally:
            bad_file.unlink(missing_ok=True)


class PromptRegistryIdempotencyTest(unittest.TestCase):
    """ensure_loaded and reload should be safe to call multiple times."""

    def test_ensure_loaded_idempotent(self) -> None:
        ensure_loaded()
        first = get_prompt_config("hr_screening")
        ensure_loaded()
        second = get_prompt_config("hr_screening")
        self.assertEqual(first, second)

    def test_reload_idempotent(self) -> None:
        reload_prompt_configs()
        first = list_prompt_configs()
        reload_prompt_configs()
        second = list_prompt_configs()
        self.assertEqual(set(first.keys()), set(second.keys()))


if __name__ == "__main__":
    unittest.main()
