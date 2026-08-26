"""Shared final-response safety helpers for official Agents."""

from __future__ import annotations

import re


_BRAND_REPLACEMENTS = {
    "AgentH Hive": "AgentHive",
    "Agent Hive": "AgentHive",
    "AI Hive": "AgentHive",
    "Hive Enterprise AI Platform": "AgentHive Enterprise AI Platform",
}

_INTERNAL_DIAGNOSTIC_PATTERNS = (
    re.compile(r"^\s*(request[_\s-]?id|trace[_\s-]?id|run[_\s-]?id)\s*[:：]", re.IGNORECASE),
    re.compile(
        r"^\s*(model[_\s-]?key|provider[_\s-]?key|deployment[_\s-]?id)\s*[:：]", re.IGNORECASE
    ),
    re.compile(r"^\s*(input|output|total)?\s*tokens?\s*[:：]", re.IGNORECASE),
    re.compile(
        r"^\s*(fallback[_\s-]?attempt|route[_\s-]?attempt|selected[_\s-]?route)\w*\s*[:：]",
        re.IGNORECASE,
    ),
    re.compile(r"^\s*(请求|追踪|运行)\s*ID\s*[:：]", re.IGNORECASE),
    re.compile(r"^\s*(模型|供应商|部署|路由)\s*(Key|ID|键|标识)\s*[:：]", re.IGNORECASE),
    re.compile(r"^\s*(输入|输出|总)?\s*Token\s*[:：]", re.IGNORECASE),
    re.compile(r"^\s*(检索分数|检索得分|内部策略|系统提示词)\s*[:：]", re.IGNORECASE),
)


def normalize_agenthive_brand(text: str) -> str:
    """Normalize common AgentHive brand misspellings in model output."""
    normalized = text
    for source, target in _BRAND_REPLACEMENTS.items():
        normalized = normalized.replace(source, target)
    return normalized


def sanitize_official_agent_answer(answer: str, *, fallback: str) -> str:
    """Sanitize an official Agent answer before it reaches a user channel."""
    normalized = normalize_agenthive_brand(str(answer or "")).strip()
    if not normalized:
        return fallback

    kept_lines = [
        line.rstrip() for line in normalized.splitlines() if not _is_internal_diagnostic_line(line)
    ]
    sanitized = "\n".join(line for line in kept_lines).strip()
    return sanitized or fallback


def _is_internal_diagnostic_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return any(pattern.search(stripped) for pattern in _INTERNAL_DIAGNOSTIC_PATTERNS)
