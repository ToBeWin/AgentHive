#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
ENV_FILE="${ENV_FILE:-.env}"
SKIP_BACKUP=0
DIAGNOSTICS_OUTPUT_DIR="${DIAGNOSTICS_OUTPUT_DIR:-diagnostics/upgrade-$(date -u +%Y%m%dT%H%M%SZ)}"

usage() {
    cat <<'USAGE'
AgentHive production upgrade helper

Usage:
  scripts/upgrade.sh [--skip-backup] [--diagnostics-output-dir DIR]

The helper:
  1. Creates a production backup unless --skip-backup is passed.
  2. Builds the backend image and checks whether the active License permits upgrade.
  3. Builds and starts the Docker Compose stack.
  4. Runs database migrations and seed verification.
  5. Runs strict diagnostics and writes a sanitized support bundle.
USAGE
}

compose() {
    docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

read_env_value() {
    key="$1"
    if [ ! -f "${ENV_FILE}" ]; then
        return
    fi
    awk -F= -v key="${key}" '
        $0 !~ /^[[:space:]]*#/ && $1 == key {
            value = substr($0, index($0, "=") + 1)
            gsub(/^["'\'']|["'\'']$/, "", value)
            print value
            exit
        }
    ' "${ENV_FILE}"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --skip-backup)
            SKIP_BACKUP=1
            ;;
        --diagnostics-output-dir)
            DIAGNOSTICS_OUTPUT_DIR="${2:-}"
            if [ -z "${DIAGNOSTICS_OUTPUT_DIR}" ]; then
                printf 'ERROR: --diagnostics-output-dir requires a directory.\n' >&2
                exit 1
            fi
            shift
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

if [ ! -f "${ENV_FILE}" ]; then
    printf 'ERROR: %s does not exist. Run scripts/install.sh first.\n' "${ENV_FILE}" >&2
    exit 1
fi

compose config >/dev/null
TARGET_VERSION="${AGENTHIVE_VERSION:-$(read_env_value AGENTHIVE_VERSION)}"
TARGET_VERSION="${TARGET_VERSION:-0.3.0-alpha.2}"

if [ "${SKIP_BACKUP}" -eq 0 ]; then
    scripts/backup.sh
else
    printf 'WARNING: skipping backup because --skip-backup was provided.\n'
fi

printf 'Building backend image for license upgrade precheck...\n'
compose build backend

printf 'Checking license maintenance and upgrade authorization...\n'
compose run --rm --no-deps backend python scripts/check_license_upgrade.py --target-version "${TARGET_VERSION}"

printf 'Building and starting AgentHive stack...\n'
compose up -d --build

printf 'Running database migrations and seed initialization...\n'
compose exec -T backend python scripts/init_db.py

printf 'Verifying database schema and seed data...\n'
compose exec -T backend python scripts/check_db.py

printf 'Running strict deployment diagnostics...\n'
COMPOSE_FILE="${COMPOSE_FILE}" ENV_FILE="${ENV_FILE}" scripts/diagnose.sh --strict --output-dir "${DIAGNOSTICS_OUTPUT_DIR}"
printf 'Strict diagnostics passed. Support bundle: %s\n' "${DIAGNOSTICS_OUTPUT_DIR}"

printf '\nAgentHive upgrade flow completed.\n'
