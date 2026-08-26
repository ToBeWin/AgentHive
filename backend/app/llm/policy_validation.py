"""Pure validation and normalization for persisted LLM policy payloads."""

import re

from fastapi import HTTPException, status

from app.schemas.llm import LLMPolicyEffect, LLMPolicyScope, LLMPolicyUpsertRequest


MODEL_POLICY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,119}$")
MAX_MODEL_POLICY_LIST_ITEMS = 100


def normalize_and_validate_policy_payload(payload: LLMPolicyUpsertRequest) -> None:
    """Normalize a policy in place and raise the existing client-facing errors."""
    payload.name = payload.name.strip()
    if not payload.name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Model policy name cannot be empty.",
        )

    payload.description = payload.description.strip() if payload.description else None
    payload.allowed_models = normalize_policy_key_list(payload.allowed_models, field_name="allowed_models")
    payload.allowed_routing_keys = normalize_policy_key_list(
        payload.allowed_routing_keys,
        field_name="allowed_routing_keys",
    )
    payload.default_model_key = normalize_policy_key(
        payload.default_model_key,
        field_name="default_model_key",
        required=False,
    )
    payload.default_routing_key = normalize_policy_key(
        payload.default_routing_key,
        field_name="default_routing_key",
        required=False,
    )

    if (
        payload.effect == LLMPolicyEffect.ALLOW
        and not payload.allowed_models
        and not payload.allowed_routing_keys
        and payload.default_model_key is None
        and payload.default_routing_key is None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Allow model policies must specify at least one model, routing key, or default route.",
        )
    if payload.default_model_key and payload.default_model_key not in payload.allowed_models:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="default_model_key must be included in allowed_models.",
        )
    if payload.default_routing_key and payload.default_routing_key not in payload.allowed_routing_keys:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="default_routing_key must be included in allowed_routing_keys.",
        )


def validate_policy_scope(payload: LLMPolicyUpsertRequest) -> None:
    if payload.scope_type == LLMPolicyScope.TENANT:
        payload.scope_id = None
        return
    if payload.scope_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="scope_id is required for non-tenant model policies.",
        )


def dedupe_text_list(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def normalize_policy_key_list(values: list[str], *, field_name: str) -> list[str]:
    if len(values) > MAX_MODEL_POLICY_LIST_ITEMS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{field_name} cannot contain more than {MAX_MODEL_POLICY_LIST_ITEMS} items.",
        )
    result: list[str] = []
    for value in values:
        normalized = normalize_policy_key(value, field_name=field_name, required=False)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def normalize_policy_key(value: str | None, *, field_name: str, required: bool) -> str | None:
    if value is None:
        if required:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{field_name} is required.",
            )
        return None
    normalized = value.strip()
    if not normalized:
        if required:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{field_name} cannot be empty.",
            )
        return None
    if not MODEL_POLICY_KEY_PATTERN.fullmatch(normalized):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"{field_name} contains an invalid model or routing key. "
                "Use letters, numbers, '.', '_', '-', '/', ':', '@', or '+'."
            ),
        )
    return normalized
