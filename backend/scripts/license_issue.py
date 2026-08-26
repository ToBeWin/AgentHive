from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import sys
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.license_crypto import (  # noqa: E402
    SignedLicenseEnvelope,
    SignedLicensePayload,
    canonical_license_payload,
)
from app.services.agent_module_service import list_module_definitions  # noqa: E402

MODULE_DEFINITIONS = list_module_definitions()
OFFICIAL_MODULES = [definition.id for definition in MODULE_DEFINITIONS]

STANDARD_FEATURES = [
    "feature.agent_catalog",
    "feature.license_offline_activation",
    "feature.model_budget",
    "channel.web_widget",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentHive offline license issuer.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    keygen = subparsers.add_parser("generate-keypair", help="Generate Ed25519 issuer keys.")
    keygen.add_argument("--private-key", required=True, type=Path)
    keygen.add_argument("--public-key", required=True, type=Path)
    keygen.add_argument("--force", action="store_true")

    list_modules = subparsers.add_parser("list-modules", help="List official Agent module keys.")
    list_modules.add_argument("--format", choices=["text", "json"], default="text")

    issue = subparsers.add_parser("issue", help="Issue a signed license from an activation request.")
    issue.add_argument("--activation-request", required=True, type=Path)
    issue.add_argument("--private-key", required=True, type=Path)
    issue.add_argument("--output", type=Path)
    issue.add_argument("--customer-name", required=True)
    issue.add_argument("--license-id", default=None)
    issue.add_argument("--license-type", default="standard")
    issue.add_argument("--module", action="append", default=[])
    issue.add_argument("--feature", action="append", default=[])
    issue.add_argument("--all-official-modules", action="store_true")
    issue.add_argument("--standard-features", action="store_true")
    issue.add_argument("--max-users", type=int, default=50)
    issue.add_argument("--max-agents", type=int, default=5)
    issue.add_argument("--max-kb-size-gb", type=Decimal, default=Decimal("5.0"))
    issue.add_argument("--maintenance-until")
    issue.add_argument("--expires-at")
    issue.add_argument("--not-before")
    issue.add_argument("--metadata-json", default="{}")
    issue.add_argument("--base64", action="store_true", help="Write a base64-encoded license blob.")

    args = parser.parse_args()
    if args.command == "generate-keypair":
        generate_keypair(args.private_key, args.public_key, force=args.force)
        return
    if args.command == "list-modules":
        print_official_modules(output_format=args.format)
        return
    if args.command == "issue":
        issue_license(args)
        return
    raise SystemExit(f"Unsupported command: {args.command}")


def generate_keypair(private_key_path: Path, public_key_path: Path, *, force: bool) -> None:
    _ensure_writable(private_key_path, force=force)
    _ensure_writable(public_key_path, force=force)

    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    public_key_path.parent.mkdir(parents=True, exist_ok=True)
    private_key_path.write_bytes(private_pem)
    public_key_path.write_bytes(public_pem)
    private_key_path.chmod(0o600)
    public_key_path.chmod(0o644)
    print(f"Private key written to {private_key_path}")
    print(f"Public key written to {public_key_path}")


def official_module_rows() -> list[dict[str, object]]:
    return [
        {
            "module_key": definition.id,
            "name": definition.name,
            "priority": definition.priority,
            "category": definition.category,
            "required_features": list(definition.required_features),
            "dependencies": list(definition.dependencies),
        }
        for definition in MODULE_DEFINITIONS
    ]


def print_official_modules(*, output_format: str) -> None:
    rows = official_module_rows()
    if output_format == "json":
        print(json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=True))
        return

    print("module_key\tpriority\tcategory\tname\tdependencies\trequired_features")
    for row in rows:
        dependencies = ",".join(str(item) for item in row["dependencies"]) or "-"
        required_features = ",".join(str(item) for item in row["required_features"]) or "-"
        print(
            f"{row['module_key']}\t{row['priority']}\t{row['category']}\t"
            f"{row['name']}\t{dependencies}\t{required_features}"
        )


def issue_license(args: argparse.Namespace) -> None:
    activation_request = _load_json(args.activation_request)
    private_key = _load_private_key(args.private_key)
    modules = sorted(set((OFFICIAL_MODULES if args.all_official_modules else []) + args.module))
    features = sorted(set((STANDARD_FEATURES if args.standard_features else []) + args.feature))
    validate_module_feature_coverage(modules, features)
    metadata = _load_json_text(args.metadata_json)
    now = datetime.now(timezone.utc)

    payload = SignedLicensePayload(
        product="AgentHive",
        license_id=args.license_id or f"AH-{uuid4().hex}",
        license_type=args.license_type,
        customer_name=args.customer_name,
        tenant_id=str(activation_request.get("tenant_id")) if activation_request.get("tenant_id") else None,
        deployment_id=str(activation_request["deployment_id"]),
        install_id=str(activation_request["install_id"]),
        machine_fingerprint_hash=str(activation_request["machine_fingerprint_hash"]),
        allowed_modules=modules,
        allowed_features=features,
        max_users=args.max_users,
        max_agents=args.max_agents,
        max_kb_size_gb=args.max_kb_size_gb,
        maintenance_until=_parse_datetime(args.maintenance_until),
        expires_at=_parse_datetime(args.expires_at),
        issued_at=now,
        not_before=_parse_datetime(args.not_before),
        metadata={
            **metadata,
            "activation_request_id": activation_request.get("request_id"),
            "activation_request_generated_at": activation_request.get("generated_at"),
        },
    )
    signature = private_key.sign(canonical_license_payload(payload))
    envelope = SignedLicenseEnvelope(
        payload=payload,
        signature_alg="Ed25519",
        signature=base64.b64encode(signature).decode("ascii"),
    )
    document = json.dumps(
        envelope.model_dump(mode="json", exclude_none=True),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    output = base64.b64encode(document.encode("utf-8")).decode("ascii") if args.base64 else document
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
        print(f"Signed license written to {args.output}")
    else:
        print(output)


def required_features_for_modules(module_keys: list[str]) -> list[str]:
    definitions_by_id = {definition.id: definition for definition in MODULE_DEFINITIONS}
    required_features: set[str] = set()
    for module_key in module_keys:
        definition = definitions_by_id.get(module_key)
        if definition is not None:
            required_features.update(definition.required_features)
    return sorted(required_features)


def missing_required_features_for_modules(module_keys: list[str], feature_keys: list[str]) -> list[str]:
    return sorted(set(required_features_for_modules(module_keys)) - set(feature_keys))


def validate_module_feature_coverage(module_keys: list[str], feature_keys: list[str]) -> None:
    missing = missing_required_features_for_modules(module_keys, feature_keys)
    if not missing:
        return
    raise SystemExit(
        "Selected Agent modules require missing license features: "
        f"{', '.join(missing)}. Add explicit --feature values or use --standard-features."
    )


def _ensure_writable(path: Path, *, force: bool) -> None:
    if path.exists() and not force:
        raise SystemExit(f"{path} already exists. Pass --force to overwrite.")


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_json_text(raw: str) -> dict[str, object]:
    document = json.loads(raw)
    if not isinstance(document, dict):
        raise SystemExit("--metadata-json must be a JSON object.")
    return document


def _load_private_key(path: Path) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise SystemExit("Private key must be an Ed25519 PEM key.")
    return key


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


if __name__ == "__main__":
    main()
