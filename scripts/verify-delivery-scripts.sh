#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail() {
    printf 'ERROR: %s\n' "$1" >&2
    exit 1
}

assert_executable() {
    script_path="$1"
    [ -x "${ROOT_DIR}/${script_path}" ] || fail "${script_path} must be executable"
}

assert_help_contains() {
    script_path="$1"
    expected="$2"
    help_output="$("${ROOT_DIR}/${script_path}" --help)"
    printf '%s\n' "${help_output}" | grep -F -- "${expected}" >/dev/null || \
        fail "${script_path} --help must mention: ${expected}"
}

assert_source_contains() {
    file_path="$1"
    expected="$2"
    grep -F -- "${expected}" "${ROOT_DIR}/${file_path}" >/dev/null || \
        fail "${file_path} must contain: ${expected}"
}

assert_source_not_contains() {
    file_path="$1"
    unexpected="$2"
    if grep -F -- "${unexpected}" "${ROOT_DIR}/${file_path}" >/dev/null; then
        fail "${file_path} must not contain: ${unexpected}"
    fi
}

assert_rendered_production_tls_boundary() {
    rendered_config="$(mktemp "${TMPDIR:-/tmp}/agenthive-compose.XXXXXX")"
    (
        cd "${ROOT_DIR}"
        docker compose --env-file .env.example -f docker-compose.yml config --format json
    ) >"${rendered_config}"
    python3 - "${rendered_config}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    config = json.load(handle)

nginx = config["services"]["nginx"]
ports = nginx.get("ports") or []
if not any(
    str(port.get("published")) == "8080"
    and str(port.get("target")) == "80"
    and port.get("host_ip") == "127.0.0.1"
    for port in ports
):
    raise SystemExit("production nginx origin must render as 127.0.0.1:8080 -> 80")

backend_env = config["services"]["backend"].get("environment") or {}
public_base_url = str(backend_env.get("AGENTHIVE_PUBLIC_BASE_URL") or "")
if not public_base_url.startswith("https://"):
    raise SystemExit("production backend must receive an explicit HTTPS public base URL")
if str(backend_env.get("AGENTHIVE_AUTH_COOKIE_SECURE") or "").lower() != "true":
    raise SystemExit("production auth cookies must remain Secure")
trusted_proxy_cidrs = str(backend_env.get("AGENTHIVE_TRUSTED_PROXY_CIDRS") or "")
if "0.0.0.0/0" in trusted_proxy_cidrs or "::/0" in trusted_proxy_cidrs:
    raise SystemExit("production backend must not trust arbitrary proxy sources")
forwarded_allow_ips = str(backend_env.get("FORWARDED_ALLOW_IPS") or "")
if not forwarded_allow_ips or forwarded_allow_ips == "*":
    raise SystemExit("Uvicorn forwarded-header trust must use explicit proxy networks")
if "172.16.0.0/12" not in forwarded_allow_ips:
    raise SystemExit("Uvicorn must trust the default internal Docker proxy network")
PY
    rm -f "${rendered_config}"
}

assert_rendered_litellm_database_isolation() {
    production_config="$(mktemp "${TMPDIR:-/tmp}/agenthive-compose-production.XXXXXX")"
    development_config="$(mktemp "${TMPDIR:-/tmp}/agenthive-compose-development.XXXXXX")"
    infrastructure_config="$(mktemp "${TMPDIR:-/tmp}/agenthive-compose-infrastructure.XXXXXX")"
    (
        cd "${ROOT_DIR}"
        docker compose --env-file .env.example -f docker-compose.yml config --format json
    ) >"${production_config}"
    (
        cd "${ROOT_DIR}"
        docker compose --env-file .env.example -f docker-compose.dev.yml config --format json
    ) >"${development_config}"
    (
        cd "${ROOT_DIR}"
        docker compose --env-file .env.infra.example -f docker-compose.infra.yml config --format json
    ) >"${infrastructure_config}"
    python3 - "${production_config}" "${development_config}" "${infrastructure_config}" <<'PY'
import json
import sys

for index, config_path in enumerate(sys.argv[1:]):
    with open(config_path, encoding="utf-8") as handle:
        config = json.load(handle)
    services = config["services"]
    database_url = str(services["litellm"].get("environment", {}).get("DATABASE_URL") or "")
    if not database_url.endswith("/litellm"):
        raise SystemExit(f"LiteLLM DATABASE_URL must target the separate litellm database: {database_url}")
    if database_url.endswith("/agenthive"):
        raise SystemExit("LiteLLM must never target the AgentHive business database")
    postgres_environment = services["postgres"].get("environment", {})
    if str(postgres_environment.get("LITELLM_POSTGRES_DB") or "") != "litellm":
        raise SystemExit("PostgreSQL must receive LITELLM_POSTGRES_DB for fresh-volume initialization")
    if index == 2:
        volumes = services["litellm"].get("volumes") or []
        if not any(
            str(volume.get("source") or "").endswith("/infra/litellm/config.yaml")
            and volume.get("target") == "/app/config.yaml"
            for volume in volumes
            if isinstance(volume, dict)
        ):
            raise SystemExit("remote infrastructure LiteLLM config must mount infra/litellm/config.yaml")
PY
    rm -f "${production_config}" "${development_config}" "${infrastructure_config}"
}

assert_bash_syntax() {
    script_path="$1"
    bash -n "${ROOT_DIR}/${script_path}" || fail "${script_path} has invalid bash syntax"
}

delivery_scripts=(
    "scripts/install.sh"
    "scripts/diagnose.sh"
    "scripts/upgrade.sh"
    "scripts/backup.sh"
    "scripts/restore.sh"
)

for script_path in "${delivery_scripts[@]}"; do
    assert_executable "${script_path}"
    assert_bash_syntax "${script_path}"
done

assert_help_contains "scripts/install.sh" "--license-public-key PATH"
assert_help_contains "scripts/install.sh" "--public-base-url URL"
assert_help_contains "scripts/install.sh" "--allow-missing-license-public-key"
assert_help_contains "scripts/install.sh" "--wait-timeout SECONDS"
assert_help_contains "scripts/diagnose.sh" "--strict"
assert_help_contains "scripts/diagnose.sh" "--diagnostics-token TOKEN"
assert_help_contains "scripts/upgrade.sh" "--diagnostics-output-dir DIR"

assert_source_contains "frontend/src/pages/settings/DeliveryCenterPanel.tsx" "scripts/install.sh --license-public-key ./agenthive_license_public.pem --start"
assert_source_contains "frontend/src/pages/settings/DeliveryCenterPanel.tsx" "scripts/diagnose.sh --strict --output-dir"
assert_source_contains "frontend/src/pages/settings/DeliveryCenterPanel.tsx" "scripts/upgrade.sh --diagnostics-output-dir"

assert_source_contains "docs/deployment.md" "scripts/install.sh --license-public-key ./agenthive_license_public.pem --start"
assert_source_contains "docs/deployment.md" "scripts/diagnose.sh --strict"
assert_source_contains "docs/deployment.md" "scripts/upgrade.sh"
assert_source_contains "scripts/install.sh" "AGENTHIVE_MEDIA_WEBHOOK_SECRET=\$(random_secret)"
assert_source_contains "docker-compose.yml" 'AGENTHIVE_MEDIA_WEBHOOK_SECRET: ${AGENTHIVE_MEDIA_WEBHOOK_SECRET}'
assert_source_contains "scripts/backup.sh" 'CHECKSUM_FILE="checksums.sha256"'
assert_source_contains "scripts/restore.sh" "verify_checksums"
assert_source_contains "docker-compose.yml" '127.0.0.1:${HTTP_PORT:-8080}:80'
assert_source_not_contains "docker-compose.yml" '"${HTTP_PORT:-80}:80"'
assert_source_contains "docker-compose.yml" 'AGENTHIVE_PUBLIC_BASE_URL: ${AGENTHIVE_PUBLIC_BASE_URL:?Set AGENTHIVE_PUBLIC_BASE_URL to the customer HTTPS origin}'
assert_source_contains "docker-compose.yml" 'AGENTHIVE_TRUSTED_PROXY_CIDRS:'
assert_source_contains "docker-compose.yml" '${AGENTHIVE_TRUSTED_PROXY_CIDRS:-'
assert_source_contains "nginx/nginx.conf" 'map $http_x_forwarded_proto $agenthive_forwarded_proto'
assert_source_contains "nginx/nginx.conf" 'return 308 https://$host$request_uri;'
assert_source_contains "nginx/nginx.conf" 'location = /api/v1/health/readiness'
assert_source_contains "scripts/diagnose.sh" 'check_https_public_base_url'
assert_source_contains "scripts/diagnose.sh" 'check_forwarded_allow_ips'
assert_source_contains "docs/deployment.md" '标准 Compose 采用“同宿主机 TLS 终止”模式'
assert_source_contains "docs/deployment.md" '## LiteLLM 数据库隔离'
assert_source_contains "infra/postgres/init/02_create_litellm_database.sh" "CREATE DATABASE"
assert_source_contains "infra/postgres/init/02_create_litellm_database.sh" "must differ from POSTGRES_DB"
assert_source_contains "docker-compose.yml" 'LITELLM_POSTGRES_DB: ${LITELLM_POSTGRES_DB:-litellm}'
assert_source_contains "docker-compose.dev.yml" 'LITELLM_POSTGRES_DB: ${LITELLM_POSTGRES_DB:-litellm}'
assert_source_contains "docker-compose.infra.yml" 'LITELLM_POSTGRES_DB: ${LITELLM_POSTGRES_DB:-litellm}'

assert_rendered_production_tls_boundary
assert_rendered_litellm_database_isolation

printf 'Delivery script verification passed.\n'
