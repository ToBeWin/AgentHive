from typing import Any

REDACTED = "[REDACTED]"

_SENSITIVE_SUBSTRINGS = (
    "api_key",
    "apikey",
    "authorization",
    "secret",
    "secret_ref",
    "password",
    "private_key",
    "license_key",
    "activation_code",
)
_SENSITIVE_EXACT_KEYS = {
    "token",
    "access_token",
    "refresh_token",
    "id_token",
    "bearer_token",
}


def redact_audit_details(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): REDACTED if _is_sensitive_key(str(key)) else redact_audit_details(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_audit_details(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    if lowered.endswith("_configured"):
        return False
    return lowered in _SENSITIVE_EXACT_KEYS or any(
        keyword in lowered for keyword in _SENSITIVE_SUBSTRINGS
    )
