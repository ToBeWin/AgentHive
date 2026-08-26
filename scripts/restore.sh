#!/usr/bin/env bash
set -euo pipefail
umask 077

PROJECT_NAME="agenthive"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
ENV_FILE="${ENV_FILE:-.env}"
BACKUP_DIR=""
BACKUP_DIR_ABS=""
CHECKSUM_FILE="checksums.sha256"
CONFIRM=0

usage() {
    cat <<'USAGE'
AgentHive production restore

Usage:
  scripts/restore.sh --backup-dir DIR --yes

This is a destructive restore. Before stopping services or replacing data it
requires an AgentHive v2 manifest and verifies the SHA-256 checksum of every
manifest payload, including manifest.json itself.

Requirements:
  - Run from the AgentHive project root.
  - Review the backup manifest and recorded image versions first.
  - Stop external traffic before restoring production.
USAGE
}

has_command() {
    command -v "$1" >/dev/null 2>&1
}

compose() {
    docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

volume_name() {
    printf '%s_%s\n' "${PROJECT_NAME}" "$1"
}

absolute_path() {
    python3 -c 'import os, sys; print(os.path.abspath(sys.argv[1]))' "$1"
}

validate_manifest() {
    python3 - "${BACKUP_DIR_ABS}" "${CHECKSUM_FILE}" <<'PY'
import json
import re
import sys
from pathlib import Path, PurePosixPath

root = Path(sys.argv[1]).resolve()
checksum_name = sys.argv[2]
manifest_path = root / "manifest.json"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: invalid AgentHive backup manifest: {message}")


try:
    with manifest_path.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
except (OSError, json.JSONDecodeError) as exc:
    fail(f"manifest.json cannot be read as JSON ({exc})")

if not isinstance(manifest, dict):
    fail("root must be an object")
if manifest.get("product") != "AgentHive":
    fail("product must be exactly AgentHive")
if manifest.get("backup_format") != "agenthive.backup.v2":
    fail("backup_format must be exactly agenthive.backup.v2")

migration = manifest.get("migration")
if not isinstance(migration, dict):
    fail("migration must be an object")
for key in ("current_revision", "head_revision"):
    if not isinstance(migration.get(key), str) or not migration[key].strip():
        fail(f"migration.{key} must be a non-empty string")

images = manifest.get("images")
if not isinstance(images, list) or not images:
    fail("images must be a non-empty list")
for index, image in enumerate(images):
    if not isinstance(image, dict):
        fail(f"images[{index}] must be an object")
    if not isinstance(image.get("service"), str) or not image["service"]:
        fail(f"images[{index}].service must be non-empty")
    if not isinstance(image.get("configured_ref"), str) or not image["configured_ref"]:
        fail(f"images[{index}].configured_ref must be non-empty")

files = manifest.get("files")
if not isinstance(files, list) or not files or not all(isinstance(item, str) for item in files):
    fail("files must be a non-empty string list")
if len(files) != len(set(files)):
    fail("files must not contain duplicate entries")

required = {
    "manifest.json",
    checksum_name,
    "postgres.sql",
    "minio_data.tgz",
    "redis_data.tgz",
    "agenthive_data.tgz",
    "config/.env",
    "config/docker-compose.yml",
}
missing = sorted(required - set(files))
if missing:
    fail(f"files is missing required entries: {', '.join(missing)}")


def validate_relative_file(relative: str) -> Path:
    if "\\" in relative:
        fail(f"unsafe path separator in {relative!r}")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        fail(f"unsafe path {relative!r}")
    candidate = root.joinpath(*pure.parts)
    current = root
    for part in pure.parts:
        current /= part
        if current.is_symlink():
            fail(f"symlinks are not allowed in backup payloads: {relative!r}")
    try:
        candidate.resolve().relative_to(root)
    except ValueError:
        fail(f"path escapes backup directory: {relative!r}")
    if not candidate.is_file():
        fail(f"listed file is missing: {relative!r}")
    return candidate


for relative in files:
    validate_relative_file(relative)

checksum_pattern = re.compile(r"^([0-9a-fA-F]{64})  (.+)$")
checksum_entries = []
try:
    with (root / checksum_name).open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            match = checksum_pattern.fullmatch(raw_line.rstrip("\n"))
            if not match:
                fail(f"{checksum_name}:{line_number} has an invalid SHA-256 entry")
            relative = match.group(2)
            validate_relative_file(relative)
            checksum_entries.append(relative)
except OSError as exc:
    fail(f"{checksum_name} cannot be read ({exc})")

if len(checksum_entries) != len(set(checksum_entries)):
    fail(f"{checksum_name} contains duplicate paths")
expected_checksums = set(files) - {checksum_name}
if set(checksum_entries) != expected_checksums:
    missing_hashes = sorted(expected_checksums - set(checksum_entries))
    extra_hashes = sorted(set(checksum_entries) - expected_checksums)
    details = []
    if missing_hashes:
        details.append(f"missing hashes: {', '.join(missing_hashes)}")
    if extra_hashes:
        details.append(f"unexpected hashes: {', '.join(extra_hashes)}")
    fail("; ".join(details))
PY
}

verify_checksums() {
    python3 - "${BACKUP_DIR_ABS}" "${CHECKSUM_FILE}" <<'PY'
import hashlib
import re
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
checksum_path = root / sys.argv[2]
pattern = re.compile(r"^([0-9a-fA-F]{64})  (.+)$")

with checksum_path.open(encoding="utf-8") as handle:
    entries = [pattern.fullmatch(line.rstrip("\n")).groups() for line in handle]

for expected, relative in entries:
    path = root / relative
    digest = hashlib.sha256()
    with path.open("rb") as payload:
        for chunk in iter(lambda: payload.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest().lower() != expected.lower():
        raise SystemExit(f"ERROR: SHA-256 verification failed: {relative}")
    print(f"{relative}: OK")
PY
}

restore_volume() {
    local archive="$1"
    local volume="$2"
    docker volume create "${volume}" >/dev/null
    docker run --rm \
        -v "${volume}:/to" \
        -v "${BACKUP_DIR_ABS}:/backup:ro" \
        alpine:3.20 \
        sh -c "rm -rf /to/* /to/.[!.]* /to/..?* 2>/dev/null || true; tar -xzf /backup/${archive} -C /to"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --backup-dir)
            shift
            BACKUP_DIR="${1:-}"
            ;;
        --yes)
            CONFIRM=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf 'ERROR: Unknown option: %s\n' "$1" >&2
            usage >&2
            exit 1
            ;;
    esac
    shift
done

if [ -z "${BACKUP_DIR}" ]; then
    printf 'ERROR: --backup-dir is required.\n' >&2
    usage >&2
    exit 1
fi
if [ "${CONFIRM}" -ne 1 ]; then
    printf 'ERROR: restore is destructive. Re-run with --yes after reviewing the backup.\n' >&2
    exit 1
fi
if ! has_command docker; then
    printf 'ERROR: Docker is required.\n' >&2
    exit 1
fi
if ! has_command python3; then
    printf 'ERROR: python3 is required to validate the manifest and SHA-256 checksums.\n' >&2
    exit 1
fi
if [ ! -f "${ENV_FILE}" ]; then
    printf 'ERROR: %s does not exist. Restore config/.env from the backup or run scripts/install.sh first.\n' "${ENV_FILE}" >&2
    exit 1
fi

BACKUP_DIR_ABS="$(absolute_path "${BACKUP_DIR}")"
for file in manifest.json "${CHECKSUM_FILE}" postgres.sql minio_data.tgz redis_data.tgz agenthive_data.tgz; do
    if [ ! -f "${BACKUP_DIR_ABS}/${file}" ]; then
        printf 'ERROR: backup file missing: %s\n' "${BACKUP_DIR_ABS}/${file}" >&2
        exit 1
    fi
done

printf 'Validating AgentHive v2 manifest before destructive restore...\n'
validate_manifest
printf 'Verifying every manifest payload checksum before destructive restore...\n'
verify_checksums

# Everything above this point is read-only. No stack or volume is modified until
# both the manifest contract and all SHA-256 digests have passed.
compose config >/dev/null

printf 'Restoring AgentHive from %s\n' "${BACKUP_DIR_ABS}"
printf 'Stopping stack...\n'
compose down

printf 'Restoring persistent volumes...\n'
restore_volume "minio_data.tgz" "$(volume_name minio_data)"
restore_volume "redis_data.tgz" "$(volume_name redis_data)"
restore_volume "agenthive_data.tgz" "$(volume_name agenthive_data)"

printf 'Starting database dependencies...\n'
compose up -d postgres redis minio

printf 'Waiting for PostgreSQL readiness...\n'
POSTGRES_READY=0
for _ in $(seq 1 60); do
    if compose exec -T postgres pg_isready -U agenthive -d agenthive >/dev/null 2>&1; then
        POSTGRES_READY=1
        break
    fi
    sleep 2
done
if [ "${POSTGRES_READY}" -ne 1 ]; then
    printf 'ERROR: PostgreSQL did not become ready; database restore has not started.\n' >&2
    exit 1
fi

printf 'Restoring PostgreSQL logical dump...\n'
compose exec -T postgres psql -U agenthive -d agenthive -v ON_ERROR_STOP=1 <<'SQL'
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO agenthive;
GRANT ALL ON SCHEMA public TO public;
SQL
compose exec -T postgres psql -U agenthive -d agenthive -v ON_ERROR_STOP=1 <"${BACKUP_DIR_ABS}/postgres.sql"

printf 'Starting full stack...\n'
compose up -d

printf '\nRestore complete. Run these checks before reopening traffic:\n'
printf '  scripts/diagnose.sh\n'
printf '  docker compose --env-file %s -f %s exec backend python scripts/check_db.py\n' "${ENV_FILE}" "${COMPOSE_FILE}"
