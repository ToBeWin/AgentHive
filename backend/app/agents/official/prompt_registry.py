"""Official Agent prompt configuration registry.

Loads per-agent JSON files from ``app/agents/official/prompts/`` at startup,
provides a cached ``get_prompt_config`` accessor, and supports mtime-based
hot-reload in development environments.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import is_development_environment

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


@dataclass(frozen=True)
class OfficialPromptConfig:
    """Immutable snapshot of a single agent's prompt configuration."""

    agent_key: str
    required_module: str
    role_prompt: str
    output_prompt: str
    output_format: str = "text"
    structured_schema_hint: str | None = None
    defaults: dict[str, Any] = field(default_factory=dict)
    platforms: list[str] = field(default_factory=list)
    templates: list[dict[str, Any]] = field(default_factory=list)
    brand_guidelines: dict[str, Any] | None = None
    # Raw JSON payload for future extensibility.
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> OfficialPromptConfig:
        """Parse a JSON dict into an ``OfficialPromptConfig``.

        Missing keys fall back to sensible defaults so that partially-filled
        prompt files are safe.
        """
        return cls(
            agent_key=raw.get("agent_key", ""),
            required_module=raw.get("required_module", ""),
            role_prompt=raw.get("role_prompt", ""),
            output_prompt=raw.get("output_prompt", ""),
            output_format=raw.get("output_format", "text"),
            structured_schema_hint=raw.get("structured_schema_hint"),
            defaults=raw.get("defaults", {}),
            platforms=raw.get("platforms", []),
            templates=raw.get("templates", []),
            brand_guidelines=raw.get("brand_guidelines"),
            extra={k: v for k, v in raw.items() if k not in cls.__dataclass_fields__},
        )


# ---------------------------------------------------------------------------
# Module-level singleton cache
# ---------------------------------------------------------------------------

_cache: dict[str, OfficialPromptConfig] = {}
_cache_mtimes: dict[str, float] = {}


def _scan_prompt_files() -> list[Path]:
    """Return sorted list of ``*.json`` files in the prompts directory."""
    if not _PROMPTS_DIR.is_dir():
        logger.warning("Prompts directory does not exist: %s", _PROMPTS_DIR)
        return []
    return sorted(_PROMPTS_DIR.glob("*.json"))


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)  # type: ignore[no-any-return]


def _reload_if_needed(path: Path, agent_key: str) -> None:
    """Reload a single prompt file if its mtime changed (dev only)."""
    if not is_development_environment():
        return
    try:
        current_mtime = os.path.getmtime(path)
    except OSError:
        return
    cached_mtime = _cache_mtimes.get(agent_key)
    if cached_mtime is not None and current_mtime <= cached_mtime:
        return
    try:
        raw = _load_json(path)
        config = OfficialPromptConfig.from_json(raw)
        _cache[agent_key] = config
        _cache_mtimes[agent_key] = current_mtime
        logger.debug("Hot-reloaded prompt config: %s", agent_key)
    except (json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
        logger.warning("Failed to hot-reload %s: %s", path, exc)


def _load_all() -> dict[str, OfficialPromptConfig]:
    """Load all prompt files into the cache and return the mapping."""
    configs: dict[str, OfficialPromptConfig] = {}
    for path in _scan_prompt_files():
        try:
            raw = _load_json(path)
            config = OfficialPromptConfig.from_json(raw)
            agent_key = config.agent_key
            if not agent_key:
                logger.warning("Prompt file missing agent_key: %s", path)
                continue
            configs[agent_key] = config
            _cache_mtimes[agent_key] = os.path.getmtime(path)
        except (json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
            logger.warning("Failed to load prompt file %s: %s", path, exc)
    return configs


def ensure_loaded() -> None:
    """Populate the cache if empty.  Safe to call multiple times."""
    if not _cache:
        _cache.update(_load_all())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_prompt_config(agent_key: str) -> OfficialPromptConfig | None:
    """Return the prompt configuration for *agent_key*, or ``None`` if not
    found.

    In development environments the backing JSON file is checked for mtime
    changes on every call so that editors see updates without restarting the
    server.
    """
    ensure_loaded()

    # Hot-reload path for dev environments.
    if is_development_environment() and agent_key in _cache:
        # Find the file that originally provided this key.
        for path in _scan_prompt_files():
            if path.stem == agent_key or (
                _cache.get(agent_key)
                and _cache[agent_key].required_module
                and f"agent.{agent_key}" in path.name
            ):
                _reload_if_needed(path, agent_key)
                break

    return _cache.get(agent_key)


def list_prompt_configs() -> dict[str, OfficialPromptConfig]:
    """Return a snapshot of all loaded prompt configurations.

    Development callers get hot-reloaded values; production callers get
    the startup-time snapshot.
    """
    ensure_loaded()
    # Force full reload in dev to pick up new/deleted files.
    if is_development_environment():
        _cache.update(_load_all())
    return dict(_cache)


def get_role_prompt(agent_key: str) -> str:
    """Convenience accessor returning the ``role_prompt`` for *agent_key*,
    falling back to an empty string.
    """
    config = get_prompt_config(agent_key)
    return config.role_prompt if config else ""


def get_output_prompt(agent_key: str) -> str:
    """Convenience accessor returning the ``output_prompt`` for *agent_key*,
    falling back to an empty string.
    """
    config = get_prompt_config(agent_key)
    return config.output_prompt if config else ""


def reload_prompt_configs() -> dict[str, OfficialPromptConfig]:
    """Force a full reload regardless of environment.

    Returns the newly loaded mapping.
    """
    _cache.clear()
    _cache_mtimes.clear()
    _cache.update(_load_all())
    return dict(_cache)
