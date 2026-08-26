from datetime import datetime, timedelta, timezone
from enum import StrEnum
from hashlib import sha256
from typing import Any
from uuid import UUID

import bcrypt
import jwt

from app.core.config import settings

BCRYPT_PREFIX = "bcrypt-sha256$"
BCRYPT_ROUNDS = 12


class Permission(StrEnum):
    TENANT_ADMIN = "tenant.admin"
    USERS_READ = "users:read"
    USERS_WRITE = "users:write"
    DEPARTMENTS_READ = "departments:read"
    DEPARTMENTS_WRITE = "departments:write"
    AGENTS_READ = "agents:read"
    AGENTS_WRITE = "agents:write"
    CHAT_READ = "chat:read"
    CHAT_WRITE = "chat:write"
    KNOWLEDGE_READ = "knowledge:read"
    KNOWLEDGE_WRITE = "knowledge:write"
    CHANNELS_READ = "channels:read"
    CHANNELS_WRITE = "channels:write"
    MCP_READ = "mcp:read"
    MCP_WRITE = "mcp:write"
    MCP_INVOKE = "mcp:invoke"
    MODELS_READ = "models:read"
    MODELS_WRITE = "models:write"
    BUDGETS_READ = "budgets:read"
    BUDGETS_WRITE = "budgets:write"
    BUDGETS_EXPORT = "budgets:export"
    ANALYTICS_READ = "analytics:read"
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"
    LICENSE_READ = "license:read"
    LICENSE_WRITE = "license:write"
    SYSTEM_DIAGNOSTICS = "system:diagnostics"


def hash_password(password: str) -> str:
    digest = sha256(password.encode("utf-8")).digest()
    hashed = bcrypt.hashpw(digest, bcrypt.gensalt(rounds=BCRYPT_ROUNDS))
    return f"{BCRYPT_PREFIX}{hashed.decode('utf-8')}"


def verify_password(password: str, hashed_password: str) -> bool:
    if not hashed_password.startswith(BCRYPT_PREFIX):
        return False
    digest = sha256(password.encode("utf-8")).digest()
    stored = hashed_password.removeprefix(BCRYPT_PREFIX).encode("utf-8")
    try:
        return bcrypt.checkpw(digest, stored)
    except ValueError:
        return False


def password_hash_needs_rehash(hashed_password: str) -> bool:
    if not hashed_password.startswith(BCRYPT_PREFIX):
        return True
    stored = hashed_password.removeprefix(BCRYPT_PREFIX)
    parts = stored.split("$")
    try:
        rounds = int(parts[2])
    except (IndexError, ValueError):
        return True
    return rounds < BCRYPT_ROUNDS


def create_access_token(
    *,
    subject: UUID,
    tenant_id: UUID,
    permissions: list[str],
    auth_version: int = 0,
    expires_delta: timedelta | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload: dict[str, Any] = {
        "sub": str(subject),
        "tenant_id": str(tenant_id),
        "permissions": permissions,
        "ver": auth_version,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": "AgentHive",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.jwt_algorithm],
        issuer="AgentHive",
    )
