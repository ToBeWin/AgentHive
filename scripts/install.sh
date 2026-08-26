#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="AgentHive"
COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"
DATA_VOLUME_NAME="${AGENTHIVE_DATA_VOLUME:-agenthive_agenthive_data}"
LICENSE_PUBLIC_KEY_SOURCE=""
LICENSE_PUBLIC_KEY_COPIED=0
ALLOW_MISSING_LICENSE_PUBLIC_KEY=0
SKIP_DB_INIT=0
WAIT_TIMEOUT_SECONDS="${AGENTHIVE_INSTALL_WAIT_TIMEOUT_SECONDS:-240}"
PUBLIC_BASE_URL_OVERRIDE="${AGENTHIVE_PUBLIC_BASE_URL:-}"

usage() {
    cat <<'USAGE'
AgentHive private deployment installer

Usage:
  scripts/install.sh [--start] [--license-public-key PATH] [--public-base-url URL]

Options:
  --start   Generate .env if needed, then build and start the Docker Compose stack.
  --license-public-key PATH
            Copy the AgentHive Ed25519 license public key into the backend data volume
            before starting the production stack.
  --public-base-url URL
            Required for --start. The customer-facing HTTPS origin, for example
            https://agenthive.customer.example. TLS must terminate on this host and
            proxy to the loopback origin configured by HTTP_PORT.
  --allow-missing-license-public-key
            Allow --start without a license public key. Use only for local evaluation,
            because production readiness requires /data/agenthive/license_public.pem.
  --skip-db-init
            Start containers without running backend database migrations and seed checks.
            Use only for advanced recovery; normal private deployments should not skip it.
  --wait-timeout SECONDS
            Maximum time to wait for containers and readiness checks. Default: 240.
  -h, --help
            Show this help text.
USAGE
}

has_command() {
    command -v "$1" >/dev/null 2>&1
}

compose() {
    docker compose "$@"
}

random_secret() {
    if has_command openssl; then
        openssl rand -hex 32
    else
        od -An -N32 -tx1 /dev/urandom | tr -d ' \n'
        printf '\n'
    fi
}

write_env_file() {
    umask 077
    cat >"${ENV_FILE}" <<EOF
AGENTHIVE_VERSION=0.3.0-alpha.3
HTTP_PORT=8080
AGENTHIVE_PUBLIC_BASE_URL=${PUBLIC_BASE_URL_OVERRIDE}

POSTGRES_PASSWORD=$(random_secret)
LITELLM_POSTGRES_DB=litellm
REDIS_PASSWORD=$(random_secret)
MINIO_ROOT_USER=agenthive
MINIO_ROOT_PASSWORD=$(random_secret)
AGENTHIVE_MINIO_SECURE=false
AGENTHIVE_OBJECT_STORAGE_FALLBACK_PATH=/data/agenthive/object-storage-fallback
LITELLM_MASTER_KEY=sk-agenthive-$(random_secret)
AGENTHIVE_MEDIA_WEBHOOK_SECRET=$(random_secret)
SECRET_KEY=$(random_secret)
SECURITY_HEADERS_ENABLED=true
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=120
RATE_LIMIT_WINDOW_SECONDS=60
AGENTHIVE_TRUSTED_PROXY_CIDRS=["127.0.0.1/32","::1/128","172.16.0.0/12"]
AGENTHIVE_FORWARDED_ALLOW_IPS=127.0.0.1,::1,172.16.0.0/12

AGENTHIVE_INSTALL_ID_PATH=/data/agenthive/install-identity.json
AGENTHIVE_LICENSE_PUBLIC_KEY_PATH=/data/agenthive/license_public.pem
MINIO_CONSOLE_PORT=9001
LITELLM_CONFIG_FILE=./litellm/config.yaml.example
RAGFLOW_URL=
RAG_EMBEDDING_MODE=deterministic_local
RAG_EMBEDDING_MODEL_KEY=agenthive-local-hash-v1
RAG_EMBEDDING_DIMENSIONS=1536
EOF
}

check_docker() {
    if ! has_command docker; then
        printf 'ERROR: Docker is not installed or not in PATH.\n' >&2
        exit 1
    fi

    if ! docker info >/dev/null 2>&1; then
        printf 'ERROR: Docker is not running or this user cannot access it.\n' >&2
        exit 1
    fi

    if ! docker compose version >/dev/null 2>&1; then
        printf 'ERROR: Docker Compose v2 is required.\n' >&2
        exit 1
    fi
}

validate_license_public_key_file() {
    key_path="$1"
    if [ ! -f "${key_path}" ]; then
        printf 'ERROR: License public key file does not exist: %s\n' "${key_path}" >&2
        exit 1
    fi
    if [ ! -s "${key_path}" ]; then
        printf 'ERROR: License public key file is empty: %s\n' "${key_path}" >&2
        exit 1
    fi
    if ! grep -q 'BEGIN PUBLIC KEY' "${key_path}"; then
        printf 'ERROR: License public key must be a PEM public key file: %s\n' "${key_path}" >&2
        exit 1
    fi
}

copy_license_public_key_to_volume() {
    key_path="$1"
    validate_license_public_key_file "${key_path}"
    key_dir="$(cd "$(dirname "${key_path}")" && pwd)"
    key_name="$(basename "${key_path}")"

    docker volume create "${DATA_VOLUME_NAME}" >/dev/null
    docker run --rm \
        -v "${DATA_VOLUME_NAME}:/target" \
        -v "${key_dir}:/source:ro" \
        busybox:1.36 sh -eu -c '
            mkdir -p /target
            cp "/source/${1}" /target/license_public.pem
            chmod 0444 /target/license_public.pem
        ' sh "${key_name}"
    LICENSE_PUBLIC_KEY_COPIED=1
    printf 'Copied license public key into Docker volume %s:/license_public.pem.\n' "${DATA_VOLUME_NAME}"
}

data_volume_has_license_public_key() {
    docker volume create "${DATA_VOLUME_NAME}" >/dev/null
    docker run --rm -v "${DATA_VOLUME_NAME}:/target:ro" busybox:1.36 sh -c \
        'test -s /target/license_public.pem && grep -q "BEGIN PUBLIC KEY" /target/license_public.pem' >/dev/null 2>&1
}

ensure_license_public_key_ready() {
    public_base_url_hint="$(env_value AGENTHIVE_PUBLIC_BASE_URL)"
    if [ -n "${LICENSE_PUBLIC_KEY_SOURCE}" ]; then
        if [ "${LICENSE_PUBLIC_KEY_COPIED}" -eq 1 ]; then
            return
        fi
        copy_license_public_key_to_volume "${LICENSE_PUBLIC_KEY_SOURCE}"
        return
    fi

    if data_volume_has_license_public_key; then
        printf 'License public key already exists in Docker volume %s.\n' "${DATA_VOLUME_NAME}"
        return
    fi

    if [ "${ALLOW_MISSING_LICENSE_PUBLIC_KEY}" -eq 1 ]; then
        printf 'WARNING: starting without /data/agenthive/license_public.pem. Production readiness may fail.\n'
        return
    fi

    cat >&2 <<EOF
ERROR: License public key is required before starting the production stack.

Provide the customer public key:
  scripts/install.sh --license-public-key ./agenthive_license_public.pem --start \
    --public-base-url ${public_base_url_hint:-https://agenthive.customer.example}

For local evaluation only, bypass this gate with:
  scripts/install.sh --allow-missing-license-public-key --start \
    --public-base-url ${public_base_url_hint:-https://agenthive.customer.example}
EOF
    exit 1
}

require_positive_integer() {
    value="$1"
    label="$2"
    case "${value}" in
        ''|*[!0-9]*)
            printf 'ERROR: %s must be a positive integer.\n' "${label}" >&2
            exit 1
            ;;
    esac
    if [ "${value}" -le 0 ]; then
        printf 'ERROR: %s must be greater than zero.\n' "${label}" >&2
        exit 1
    fi
}

wait_for_container_running() {
    service="$1"
    timeout_seconds="$2"
    elapsed=0
    printf 'Waiting for %s container to be running' "${service}"
    while [ "${elapsed}" -lt "${timeout_seconds}" ]; do
        container_id="$(compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps -q "${service}" 2>/dev/null || true)"
        if [ -n "${container_id}" ]; then
            running="$(docker inspect -f '{{.State.Running}}' "${container_id}" 2>/dev/null || true)"
            status="$(docker inspect -f '{{.State.Status}}' "${container_id}" 2>/dev/null || true)"
            if [ "${running}" = "true" ]; then
                printf ' ok\n'
                return
            fi
            if [ "${status}" = "exited" ] || [ "${status}" = "dead" ]; then
                printf '\nERROR: %s container exited before initialization.\n' "${service}" >&2
                compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" logs --tail=80 "${service}" >&2 || true
                exit 1
            fi
        fi
        printf '.'
        sleep 2
        elapsed=$((elapsed + 2))
    done
    printf '\nERROR: timed out waiting for %s container to run.\n' "${service}" >&2
    compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps >&2 || true
    exit 1
}

wait_for_service_healthy() {
    service="$1"
    timeout_seconds="$2"
    elapsed=0
    printf 'Waiting for %s healthcheck' "${service}"
    while [ "${elapsed}" -lt "${timeout_seconds}" ]; do
        container_id="$(compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps -q "${service}" 2>/dev/null || true)"
        if [ -n "${container_id}" ]; then
            health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "${container_id}" 2>/dev/null || true)"
            status="$(docker inspect -f '{{.State.Status}}' "${container_id}" 2>/dev/null || true)"
            if [ "${health}" = "healthy" ] || { [ "${health}" = "none" ] && [ "${status}" = "running" ]; }; then
                printf ' ok\n'
                return
            fi
            if [ "${status}" = "exited" ] || [ "${status}" = "dead" ]; then
                printf '\nERROR: %s container exited while waiting for health.\n' "${service}" >&2
                compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" logs --tail=80 "${service}" >&2 || true
                exit 1
            fi
        fi
        printf '.'
        sleep 2
        elapsed=$((elapsed + 2))
    done
    printf '\nERROR: timed out waiting for %s to become healthy.\n' "${service}" >&2
    compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps >&2 || true
    exit 1
}

env_value() {
    key="$1"
    if [ ! -f "${ENV_FILE}" ]; then
        return
    fi
    grep -E "^${key}=" "${ENV_FILE}" | tail -n 1 | cut -d= -f2- || true
}

validate_public_base_url() {
    value="${1%/}"
    lowered_value="$(printf '%s' "${value}" | tr '[:upper:]' '[:lower:]')"
    case "${value}" in
        https://*) ;;
        *)
            printf 'ERROR: AGENTHIVE_PUBLIC_BASE_URL must start with https:// (received: %s).\n' "${1}" >&2
            exit 1
            ;;
    esac
    case "${lowered_value}" in
        *'.example'|*'.example:'*|*'.example/'*|*'.example.'*|*'.invalid'|*'.invalid:'*|*'.invalid/'*|*'<'*|*'>'*)
            printf 'ERROR: AGENTHIVE_PUBLIC_BASE_URL still looks like a documentation placeholder.\n' >&2
            exit 1
            ;;
    esac
    case "${value}" in
        *[[:space:]]*|*'@'*|*'?'*|*'#'*)
            printf 'ERROR: AGENTHIVE_PUBLIC_BASE_URL must be an HTTPS origin without credentials, query, or fragment.\n' >&2
            exit 1
            ;;
    esac
    authority="${value#https://}"
    case "${authority}" in
        ''|*/*)
            printf 'ERROR: AGENTHIVE_PUBLIC_BASE_URL must contain only scheme, host, and optional port.\n' >&2
            exit 1
            ;;
    esac
}

upsert_env_value() {
    key="$1"
    value="$2"
    temporary_file="$(mktemp "${ENV_FILE}.tmp.XXXXXX")"
    awk -F= -v key="${key}" -v value="${value}" '
        BEGIN { replaced = 0 }
        $1 == key {
            if (!replaced) {
                print key "=" value
                replaced = 1
            }
            next
        }
        { print }
        END {
            if (!replaced) {
                print key "=" value
            }
        }
    ' "${ENV_FILE}" >"${temporary_file}"
    chmod 0600 "${temporary_file}"
    mv "${temporary_file}" "${ENV_FILE}"
}

ensure_tls_delivery_config() {
    public_base_url="$(env_value AGENTHIVE_PUBLIC_BASE_URL)"
    if [ -z "${public_base_url}" ]; then
        if [ "${START_STACK}" -eq 1 ]; then
            cat >&2 <<'EOF'
ERROR: production startup requires an HTTPS customer origin.

Set it in .env or pass it explicitly:
  scripts/install.sh --public-base-url https://agenthive.customer.example --start

AgentHive keeps Secure authentication cookies enabled and exposes its internal
HTTP origin on 127.0.0.1 only. Configure a same-host TLS terminator before
opening the deployment to users.
EOF
            exit 1
        fi
        printf 'TLS configuration pending: set AGENTHIVE_PUBLIC_BASE_URL=https://<customer-host> before --start.\n'
        return 1
    fi
    validate_public_base_url "${public_base_url}"
    return 0
}

wait_for_origin_readiness() {
    timeout_seconds="$1"
    http_port="$(env_value HTTP_PORT)"
    http_port="${http_port:-8080}"
    origin_url="http://127.0.0.1:${http_port}/api/v1/health/readiness"

    if ! has_command curl; then
        printf 'WARNING: curl is not available; skipping public readiness probe.\n'
        return
    fi

    elapsed=0
    printf 'Waiting for loopback AgentHive readiness at %s' "${origin_url}"
    while [ "${elapsed}" -lt "${timeout_seconds}" ]; do
        if curl -fsS "${origin_url}" >/dev/null 2>&1; then
            printf ' ok\n'
            return
        fi
        printf '.'
        sleep 2
        elapsed=$((elapsed + 2))
    done
    printf '\nERROR: loopback readiness endpoint did not become healthy: %s\n' "${origin_url}" >&2
    compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps >&2 || true
    exit 1
}

initialize_database() {
    if [ "${SKIP_DB_INIT}" -eq 1 ]; then
        printf 'WARNING: skipping database initialization and checks because --skip-db-init was provided.\n'
        return
    fi

    printf 'Running AgentHive database migrations and official Agent module seed...\n'
    compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" exec -T backend python scripts/init_db.py
    printf 'Verifying AgentHive database schema, pgvector, and seed data...\n'
    compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" exec -T backend python scripts/check_db.py
}

start_stack() {
    ensure_license_public_key_ready
    require_positive_integer "${WAIT_TIMEOUT_SECONDS}" "--wait-timeout"

    printf 'Starting AgentHive core services for initialization...\n'
    compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d --build \
        postgres redis minio litellm backend frontend
    wait_for_container_running backend "${WAIT_TIMEOUT_SECONDS}"
    initialize_database

    wait_for_service_healthy backend "${WAIT_TIMEOUT_SECONDS}"
    wait_for_service_healthy frontend "${WAIT_TIMEOUT_SECONDS}"

    printf 'Starting AgentHive loopback origin gateway...\n'
    compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d nginx
    wait_for_container_running nginx "${WAIT_TIMEOUT_SECONDS}"
    wait_for_origin_readiness "${WAIT_TIMEOUT_SECONDS}"

    printf '\n%s stack is initialized. Current service status:\n' "${PROJECT_NAME}"
    compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps
}

print_next_steps() {
    configured_public_base_url="$(env_value AGENTHIVE_PUBLIC_BASE_URL)"
    configured_http_port="$(env_value HTTP_PORT)"
    cat <<EOF

${PROJECT_NAME} deployment scaffold is ready.

Next steps:
  1. Review ${ENV_FILE} and adjust ports or credentials if required.
     ${ENV_FILE}.example documents every production variable.
  2. For real model access, copy litellm/config.yaml.example to litellm/config.yaml,
     add provider credentials, and set LITELLM_CONFIG_FILE=./litellm/config.yaml.
  3. Configure a same-host TLS terminator for ${configured_public_base_url:-https://agenthive.customer.example}
     and proxy it to http://127.0.0.1:${configured_http_port:-8080} with
     X-Forwarded-Proto: https. The origin port is intentionally loopback-only.
  4. Place the AgentHive license public key into the backend data volume before starting:
       scripts/install.sh --license-public-key ./agenthive_license_public.pem --start \
         --public-base-url ${configured_public_base_url:-https://agenthive.customer.example}
     The key is stored at /data/agenthive/license_public.pem inside the backend container.
  5. If the key is already present, start and initialize the stack:
       scripts/install.sh --start --public-base-url ${configured_public_base_url:-https://agenthive.customer.example}
     The installer starts core services, runs database migrations, seeds official
     Agent modules, verifies pgvector/schema readiness, then starts nginx.
  6. Run strict delivery diagnostics:
       scripts/diagnose.sh --strict
  7. Open the HTTPS customer origin (never the loopback HTTP origin):
       ${configured_public_base_url:-https://agenthive.customer.example}

Optional RAGFlow profile:
       docker compose --env-file ${ENV_FILE} -f ${COMPOSE_FILE} --profile ragflow up -d --build

Diagnostics:
       scripts/diagnose.sh

Backup before upgrades or risky maintenance:
       scripts/backup.sh

Upgrade helper:
       scripts/upgrade.sh
EOF
}

START_STACK=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --start)
            START_STACK=1
            ;;
        --license-public-key)
            LICENSE_PUBLIC_KEY_SOURCE="${2:-}"
            if [ -z "${LICENSE_PUBLIC_KEY_SOURCE}" ]; then
                printf 'ERROR: --license-public-key requires a path.\n' >&2
                exit 1
            fi
            shift
            ;;
        --public-base-url)
            PUBLIC_BASE_URL_OVERRIDE="${2:-}"
            if [ -z "${PUBLIC_BASE_URL_OVERRIDE}" ]; then
                printf 'ERROR: --public-base-url requires an HTTPS URL.\n' >&2
                exit 1
            fi
            PUBLIC_BASE_URL_OVERRIDE="${PUBLIC_BASE_URL_OVERRIDE%/}"
            validate_public_base_url "${PUBLIC_BASE_URL_OVERRIDE}"
            shift
            ;;
        --allow-missing-license-public-key)
            ALLOW_MISSING_LICENSE_PUBLIC_KEY=1
            ;;
        --skip-db-init)
            SKIP_DB_INIT=1
            ;;
        --wait-timeout)
            WAIT_TIMEOUT_SECONDS="${2:-}"
            if [ -z "${WAIT_TIMEOUT_SECONDS}" ]; then
                printf 'ERROR: --wait-timeout requires a number of seconds.\n' >&2
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

check_docker

if [ -f "${ENV_FILE}" ]; then
    printf '%s exists; leaving it unchanged.\n' "${ENV_FILE}"
else
    write_env_file
    printf 'Created %s with generated secrets.\n' "${ENV_FILE}"
fi

if [ -n "${PUBLIC_BASE_URL_OVERRIDE}" ]; then
    validate_public_base_url "${PUBLIC_BASE_URL_OVERRIDE}"
    upsert_env_value AGENTHIVE_PUBLIC_BASE_URL "${PUBLIC_BASE_URL_OVERRIDE}"
    printf 'Configured HTTPS public origin in %s.\n' "${ENV_FILE}"
fi

if ensure_tls_delivery_config; then
    compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" config >/dev/null
    printf 'Docker Compose configuration and TLS boundary validated.\n'
fi

if [ -n "${LICENSE_PUBLIC_KEY_SOURCE}" ]; then
    copy_license_public_key_to_volume "${LICENSE_PUBLIC_KEY_SOURCE}"
fi

if [ "${START_STACK}" -eq 1 ]; then
    start_stack
fi

print_next_steps
