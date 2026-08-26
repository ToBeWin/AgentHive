from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

from app.core.config import is_production_environment, settings

FINGERPRINT_ALGORITHM = "sha256"
IDENTITY_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class InstallIdentity:
    deployment_id: UUID
    install_id: UUID
    machine_fingerprint_hash: str
    fingerprint_algorithm: str
    generated_at: datetime
    path: Path


def get_install_identity() -> InstallIdentity:
    path = _identity_path()
    try:
        document = _read_identity(path)
    except FileNotFoundError:
        document = _create_identity(path)
    return _identity_from_document(document, path)


def _identity_path() -> Path:
    if settings.install_id_path:
        return Path(settings.install_id_path)
    if is_production_environment():
        return Path("/data/agenthive/install-identity.json")
    return Path(".agenthive/install-identity.json")


def _read_identity(path: Path) -> dict[str, str | int]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("AgentHive install identity must be a JSON object.")
    if document.get("schema_version") != IDENTITY_SCHEMA_VERSION:
        raise ValueError("Unsupported AgentHive install identity schema.")
    if not all(
        isinstance(key, str) and isinstance(value, (str, int)) for key, value in document.items()
    ):
        raise ValueError("AgentHive install identity contains unsupported values.")
    return cast(dict[str, str | int], document)


def _create_identity(path: Path) -> dict[str, str | int]:
    now = datetime.now(timezone.utc)
    deployment_id = uuid4()
    install_id = uuid4()
    fingerprint_salt = uuid4().hex
    fingerprint = _fingerprint(
        deployment_id=deployment_id,
        install_id=install_id,
        fingerprint_salt=fingerprint_salt,
    )
    document: dict[str, str | int] = {
        "schema_version": IDENTITY_SCHEMA_VERSION,
        "product": "AgentHive",
        "deployment_id": str(deployment_id),
        "install_id": str(install_id),
        "fingerprint_salt": fingerprint_salt,
        "machine_fingerprint_hash": fingerprint,
        "fingerprint_algorithm": FINGERPRINT_ALGORITHM,
        "generated_at": now.isoformat(),
    }
    _atomic_write_identity(path, document)
    return document


def _identity_from_document(document: dict[str, str | int], path: Path) -> InstallIdentity:
    if document.get("product") != "AgentHive":
        raise ValueError("Install identity is not for AgentHive.")
    deployment_id = UUID(str(document["deployment_id"]))
    install_id = UUID(str(document["install_id"]))
    salt = str(document["fingerprint_salt"])
    expected_fingerprint = _fingerprint(
        deployment_id=deployment_id,
        install_id=install_id,
        fingerprint_salt=salt,
    )
    stored_fingerprint = str(document["machine_fingerprint_hash"])
    if stored_fingerprint != expected_fingerprint:
        raise ValueError("Install identity fingerprint does not match its IDs and salt.")
    generated_at = datetime.fromisoformat(str(document["generated_at"]))
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)
    return InstallIdentity(
        deployment_id=deployment_id,
        install_id=install_id,
        machine_fingerprint_hash=stored_fingerprint,
        fingerprint_algorithm=str(document.get("fingerprint_algorithm", FINGERPRINT_ALGORITHM)),
        generated_at=generated_at,
        path=path,
    )


def _fingerprint(*, deployment_id: UUID, install_id: UUID, fingerprint_salt: str) -> str:
    material = f"AgentHive:{deployment_id}:{install_id}:{fingerprint_salt}:private-deployment"
    return sha256(material.encode("utf-8")).hexdigest()


def _atomic_write_identity(path: Path, document: dict[str, str | int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary_path, 0o600)
    os.replace(temporary_path, path)
