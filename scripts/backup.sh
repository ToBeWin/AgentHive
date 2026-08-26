#!/usr/bin/env bash
set -euo pipefail
umask 077

PROJECT_NAME="agenthive"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
ENV_FILE="${ENV_FILE:-.env}"
BACKUP_ROOT="${BACKUP_ROOT:-backups}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR=""
BACKUP_DIR_ABS=""
CHECKSUM_FILE="checksums.sha256"
MAINTENANCE_ACTIVE=0
INITIAL_RUNNING_SERVICES=()
STOPPED_SERVICES=()

usage() {
    cat <<'USAGE'
AgentHive production backup

Usage:
  scripts/backup.sh [--output DIR]

Environment:
  COMPOSE_FILE   Docker Compose file. Default: docker-compose.yml
  ENV_FILE       Environment file. Default: .env
  BACKUP_ROOT    Default backup parent directory. Default: backups

The backup enters a write-freeze maintenance window, restores the services that
were running before it started, and includes:
  - PostgreSQL logical dump
  - MinIO volume archive
  - Redis volume archive
  - AgentHive data volume archive (install identity, license public key, local fallback files)
  - deployment config files, migration revisions, image inventory, and a v2 manifest
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

service_is_running() {
    local service="$1"
    local container_id
    container_id="$(compose ps -q "${service}" 2>/dev/null || true)"
    [ -n "${container_id}" ] &&
        [ "$(docker inspect --format '{{.State.Running}}' "${container_id}" 2>/dev/null || true)" = "true" ]
}

array_contains() {
    local expected="$1"
    shift
    local item
    for item in "$@"; do
        if [ "${item}" = "${expected}" ]; then
            return 0
        fi
    done
    return 1
}

record_initial_running_services() {
    local service
    while IFS= read -r service; do
        if service_is_running "${service}"; then
            INITIAL_RUNNING_SERVICES+=("${service}")
        fi
    done < <(compose config --services)
}

require_running_service() {
    local service="$1"
    if ! array_contains "${service}" "${INITIAL_RUNNING_SERVICES[@]}"; then
        printf 'ERROR: %s must be running to create a consistent production backup.\n' "${service}" >&2
        exit 1
    fi
}

stop_initially_running_services() {
    local candidates=("$@")
    local to_stop=()
    local service
    for service in "${candidates[@]}"; do
        if array_contains "${service}" "${INITIAL_RUNNING_SERVICES[@]}" &&
            ! array_contains "${service}" "${STOPPED_SERVICES[@]}"; then
            to_stop+=("${service}")
            STOPPED_SERVICES+=("${service}")
        fi
    done
    if [ "${#to_stop[@]}" -eq 0 ]; then
        return
    fi
    MAINTENANCE_ACTIVE=1
    compose stop -t 30 "${to_stop[@]}"
}

restore_original_services() {
    if [ "${MAINTENANCE_ACTIVE}" -ne 1 ]; then
        return 0
    fi

    printf 'Restoring services that were running before the backup...\n'
    local restore_order=(postgres redis minio litellm frontend backend media-worker nginx ragflow)
    local service
    for service in "${restore_order[@]}"; do
        if array_contains "${service}" "${STOPPED_SERVICES[@]}"; then
            compose start "${service}"
        fi
    done
    MAINTENANCE_ACTIVE=0
}

on_exit() {
    local status=$?
    trap - EXIT INT TERM
    set +e
    if [ "${MAINTENANCE_ACTIVE}" -eq 1 ]; then
        restore_original_services
        local restore_status=$?
        if [ "${restore_status}" -ne 0 ]; then
            printf 'ERROR: automatic service restoration failed; run docker compose ps and restart the previously running services.\n' >&2
            status=1
        fi
    fi
    exit "${status}"
}

trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

write_manifest() {
    local migration_current="$1"
    local migration_head="$2"
    local image_inventory="$3"
    python3 - "${BACKUP_DIR_ABS}" "${TIMESTAMP}" "${COMPOSE_FILE}" "${ENV_FILE}" \
        "${migration_current}" "${migration_head}" "${image_inventory}" "${CHECKSUM_FILE}" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
timestamp, compose_file, env_file = sys.argv[2:5]
migration_current, migration_head = sys.argv[5:7]
inventory_path = Path(sys.argv[7])
checksum_file = sys.argv[8]

images = []
with inventory_path.open(encoding="utf-8") as handle:
    for line in handle:
        service, configured_ref, runtime_ref, image_id = line.rstrip("\n").split("\t", 3)
        images.append(
            {
                "service": service,
                "configured_ref": configured_ref,
                "runtime_ref": runtime_ref or None,
                "image_id": image_id or None,
            }
        )

inventory_path.unlink()
payload_files = sorted(
    path.relative_to(root).as_posix()
    for path in root.rglob("*")
    if path.is_file() and path.name not in {"manifest.json", checksum_file}
)
manifest = {
    "product": "AgentHive",
    "backup_format": "agenthive.backup.v2",
    "created_at": timestamp,
    "compose_file": compose_file,
    "env_file": env_file,
    "migration": {
        "current_revision": migration_current,
        "head_revision": migration_head,
    },
    "images": images,
    "files": payload_files + ["manifest.json", checksum_file],
}
with (root / "manifest.json").open("w", encoding="utf-8") as handle:
    json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
    handle.write("\n")
PY
}

write_checksums() {
    python3 - "${BACKUP_DIR_ABS}" "${CHECKSUM_FILE}" <<'PY'
import hashlib
import sys
from pathlib import Path

root = Path(sys.argv[1])
checksum_name = sys.argv[2]
files = sorted(
    path for path in root.rglob("*") if path.is_file() and path.name != checksum_name
)
with (root / checksum_name).open("w", encoding="utf-8") as output:
    for path in files:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        output.write(f"{digest.hexdigest()}  {path.relative_to(root).as_posix()}\n")
PY
}

capture_image_inventory() {
    local output="$1"
    local rendered_config
    rendered_config="$(mktemp "${TMPDIR:-/tmp}/agenthive-compose.XXXXXX")"
    compose config --format json >"${rendered_config}"
    python3 - "${rendered_config}" <<'PY' >"${output}.configured"
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    config = json.load(handle)
for service, definition in sorted(config.get("services", {}).items()):
    print(f"{service}\t{definition.get('image', '')}")
PY
    rm -f "${rendered_config}"

    : >"${output}"
    local service configured_ref container_id runtime_ref image_id
    while IFS=$'\t' read -r service configured_ref; do
        container_id="$(compose ps -q "${service}" 2>/dev/null || true)"
        runtime_ref=""
        image_id=""
        if [ -n "${container_id}" ]; then
            runtime_ref="$(docker inspect --format '{{.Config.Image}}' "${container_id}")"
            image_id="$(docker inspect --format '{{.Image}}' "${container_id}")"
        fi
        printf '%s\t%s\t%s\t%s\n' \
            "${service}" "${configured_ref}" "${runtime_ref}" "${image_id}" >>"${output}"
    done <"${output}.configured"
    rm -f "${output}.configured"
}

archive_volume() {
    local volume="$1"
    local output="$2"
    docker run --rm \
        -v "${volume}:/from:ro" \
        -v "${BACKUP_DIR_ABS}:/backup" \
        alpine:3.20 \
        sh -c "cd /from && tar -czf /backup/${output} ."
}

copy_if_exists() {
    local source="$1"
    local target_dir="$2"
    if [ -e "${source}" ]; then
        mkdir -p "${target_dir}"
        cp -R "${source}" "${target_dir}/"
    fi
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --output)
            shift
            BACKUP_DIR="${1:-}"
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

if ! has_command docker; then
    printf 'ERROR: Docker is required.\n' >&2
    exit 1
fi
if ! has_command python3; then
    printf 'ERROR: python3 is required to create the manifest and checksums.\n' >&2
    exit 1
fi
if [ ! -f "${ENV_FILE}" ]; then
    printf 'ERROR: %s does not exist. Run scripts/install.sh first.\n' "${ENV_FILE}" >&2
    exit 1
fi

BACKUP_DIR="${BACKUP_DIR:-${BACKUP_ROOT}/agenthive-${TIMESTAMP}}"
mkdir -p "${BACKUP_DIR}"
BACKUP_DIR_ABS="$(absolute_path "${BACKUP_DIR}")"

compose config >/dev/null
record_initial_running_services
require_running_service postgres
require_running_service redis
require_running_service minio
require_running_service backend

printf 'Creating AgentHive backup at %s\n' "${BACKUP_DIR_ABS}"

printf 'Recording migration revisions and deployed image inventory...\n'
MIGRATION_CURRENT="$(compose exec -T postgres psql -U agenthive -d agenthive -Atqc \
    'SELECT version_num FROM alembic_version LIMIT 1')"
MIGRATION_HEAD="$(compose exec -T backend python -c \
    'from app.services.migration_service import get_migration_head; print(get_migration_head() or "")')"
if [ -z "${MIGRATION_CURRENT}" ] || [ -z "${MIGRATION_HEAD}" ]; then
    printf 'ERROR: unable to record the current and head migration revisions.\n' >&2
    exit 1
fi
IMAGE_INVENTORY="${BACKUP_DIR_ABS}/.image-inventory.tsv"
capture_image_inventory "${IMAGE_INVENTORY}"

printf 'Entering maintenance window and stopping ingress/application writers...\n'
stop_initially_running_services nginx backend media-worker litellm

printf 'Backing up PostgreSQL logical dump while application writes are frozen...\n'
compose exec -T postgres pg_dump -U agenthive -d agenthive >"${BACKUP_DIR_ABS}/postgres.sql"

printf 'Stopping Redis and MinIO before persistent volume archives...\n'
stop_initially_running_services redis minio

printf 'Archiving quiesced persistent Docker volumes...\n'
archive_volume "$(volume_name minio_data)" "minio_data.tgz"
archive_volume "$(volume_name redis_data)" "redis_data.tgz"
archive_volume "$(volume_name agenthive_data)" "agenthive_data.tgz"

printf 'Copying deployment configuration...\n'
mkdir -p "${BACKUP_DIR_ABS}/config"
cp "${ENV_FILE}" "${BACKUP_DIR_ABS}/config/.env"
cp "${COMPOSE_FILE}" "${BACKUP_DIR_ABS}/config/docker-compose.yml"
copy_if_exists "docker-compose.dev.yml" "${BACKUP_DIR_ABS}/config"
copy_if_exists "nginx" "${BACKUP_DIR_ABS}/config"
copy_if_exists "litellm" "${BACKUP_DIR_ABS}/config"

write_manifest "${MIGRATION_CURRENT}" "${MIGRATION_HEAD}" "${IMAGE_INVENTORY}"
write_checksums

restore_original_services

printf '\nBackup complete: %s\n' "${BACKUP_DIR_ABS}"
printf 'Backup format: agenthive.backup.v2 (manifest and every payload file are SHA-256 protected).\n'
printf 'Store this directory securely. It contains secrets, license material, and customer data.\n'
