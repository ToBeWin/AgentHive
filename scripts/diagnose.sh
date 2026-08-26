#!/usr/bin/env bash
set -uo pipefail

STRICT=0
ENV_FILE="${ENV_FILE:-.env}"
COMPOSE_FILE="${COMPOSE_FILE:-}"
OUTPUT_DIR="${OUTPUT_DIR:-}"
BACKEND_PORT_VALUE="${BACKEND_PORT:-}"
HTTP_PORT_VALUE="${HTTP_PORT:-}"
MINIO_CONSOLE_PORT_VALUE="${MINIO_CONSOLE_PORT:-}"
DIAGNOSTICS_TOKEN_VALUE="${AGENTHIVE_DIAGNOSTICS_TOKEN:-}"
DIAG_TIMESTAMP="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
DELIVERY_STATUS="unknown"
DELIVERY_BLOCKERS="unknown"
DELIVERY_WARNINGS="unknown"
MEDIA_GENERATION_STATUS="unknown"
MEDIA_GENERATION_CONFIGURED_MODELS="unknown"
MEDIA_GENERATION_IMAGE_MODELS="unknown"
MEDIA_GENERATION_VIDEO_MODELS="unknown"
MEDIA_GENERATION_CONFIGURED_PROVIDERS="unknown"
MEDIA_GENERATION_MISSING_PROVIDERS="unknown"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --strict)
            STRICT=1
            shift
            ;;
        --env-file)
            ENV_FILE="${2:-}"
            shift 2
            ;;
        --compose-file|-f)
            COMPOSE_FILE="${2:-}"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="${2:-}"
            shift 2
            ;;
        --diagnostics-token)
            DIAGNOSTICS_TOKEN_VALUE="${2:-}"
            shift 2
            ;;
        --help|-h)
            cat <<'EOF'
AgentHive deployment diagnostics

Usage:
  scripts/diagnose.sh [--strict] [--env-file .env] [--compose-file docker-compose.yml] [--output-dir DIR] [--diagnostics-token TOKEN]

Default mode collects as much evidence as possible and exits 0 for support bundles.
Use --strict in delivery acceptance or CI to fail when critical checks fail.

Options:
  --output-dir DIR   Write a sanitized support bundle directory with health JSON, status summaries, and command output.
  --diagnostics-token TOKEN
                     Export the authenticated /api/v1/system/diagnostics package into the support bundle.
                     The token is never printed or written to bundle files. You can also set AGENTHIVE_DIAGNOSTICS_TOKEN.
EOF
            exit 0
            ;;
        *)
            printf 'Unknown option: %s\n' "$1" >&2
            exit 2
            ;;
    esac
done

if [ -z "${COMPOSE_FILE}" ]; then
    if [ -f "${ENV_FILE}" ]; then
        COMPOSE_FILE="docker-compose.yml"
    else
        COMPOSE_FILE="docker-compose.dev.yml"
    fi
fi

FAILURES=0
WARNINGS=0
DOCKER_DAEMON_READY=0

has_command() {
    command -v "$1" >/dev/null 2>&1
}

slugify_label() {
    printf '%s' "$1" | tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9._-'
}

init_output_dir() {
    if [ -z "${OUTPUT_DIR}" ]; then
        return
    fi
    if ! mkdir -p "${OUTPUT_DIR}"; then
        printf 'ERROR: unable to create output directory: %s\n' "${OUTPUT_DIR}" >&2
        exit 2
    fi
    OUTPUT_DIR="$(cd "${OUTPUT_DIR}" && pwd)"
    cat >"${OUTPUT_DIR}/manifest.txt" <<EOF
AgentHive diagnostic support bundle
generated_at=${DIAG_TIMESTAMP}
working_directory=$(pwd)
compose_file=${COMPOSE_FILE}
env_file=${ENV_FILE}
mode=$([ "${STRICT}" -eq 1 ] && printf strict || printf support)
privacy=No .env values or full rendered Compose config are included.
authenticated_diagnostics=$([ -n "${DIAGNOSTICS_TOKEN_VALUE}" ] && printf enabled || printf disabled)
EOF
}

write_report_file() {
    relative_path="$1"
    if [ -z "${OUTPUT_DIR}" ]; then
        cat >/dev/null
        return
    fi
    report_path="${OUTPUT_DIR}/${relative_path}"
    report_dir="$(dirname "${report_path}")"
    mkdir -p "${report_dir}"
    cat >"${report_path}"
}

section() {
    printf '\n== %s ==\n' "$1"
}

ok() {
    printf 'OK: %s\n' "$1"
}

warn() {
    WARNINGS=$((WARNINGS + 1))
    printf 'WARN: %s\n' "$1"
}

fail() {
    FAILURES=$((FAILURES + 1))
    printf 'FAIL: %s\n' "$1"
}

read_env_value() {
    key="$1"
    if [ ! -f "${ENV_FILE}" ]; then
        return 0
    fi
    awk -F= -v key="${key}" '
        $1 == key {
            value = substr($0, length(key) + 2)
            gsub(/^["'"'"']|["'"'"']$/, "", value)
            print value
            exit
        }
    ' "${ENV_FILE}"
}

is_production_compose() {
    [ "${COMPOSE_FILE}" = "docker-compose.yml" ]
}

is_placeholder_value() {
    value="$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')"
    case "${value}" in
        ""|*change-me*|*changeme*|*placeholder*|*example*|*default*|*agenthive_dev*)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

check_required_config() {
    key="$1"
    min_length="$2"
    value="$(read_env_value "${key}")"

    if is_placeholder_value "${value}"; then
        fail "${key} is missing or still uses a template value"
        return
    fi

    if [ "${#value}" -lt "${min_length}" ]; then
        fail "${key} is too short for production deployment"
        return
    fi

    ok "${key} is configured"
}

check_https_public_base_url() {
    value="$(read_env_value AGENTHIVE_PUBLIC_BASE_URL)"
    normalized="${value%/}"
    lowered="$(printf '%s' "${normalized}" | tr '[:upper:]' '[:lower:]')"
    case "${lowered}" in
        ''|*'.example'|*'.example:'*|*'.example/'*|*'.example.'*|*'.invalid'|*'.invalid:'*|*'.invalid/'*|*'<'*|*'>'*)
            fail "AGENTHIVE_PUBLIC_BASE_URL is missing or still uses a template hostname"
            return
            ;;
    esac
    case "${normalized}" in
        https://*) ;;
        *)
            fail "AGENTHIVE_PUBLIC_BASE_URL must be an explicit https:// origin"
            return
            ;;
    esac
    case "${normalized}" in
        *[[:space:]]*|*'@'*|*'?'*|*'#'*)
            fail "AGENTHIVE_PUBLIC_BASE_URL must not contain credentials, whitespace, query, or fragment"
            return
            ;;
    esac
    authority="${normalized#https://}"
    case "${authority}" in
        ''|*/*)
            fail "AGENTHIVE_PUBLIC_BASE_URL must contain only scheme, host, and optional port"
            return
            ;;
    esac
    ok "AGENTHIVE_PUBLIC_BASE_URL uses an explicit HTTPS origin"
}

check_forwarded_allow_ips() {
    value="$(read_env_value AGENTHIVE_FORWARDED_ALLOW_IPS)"
    value="${value:-127.0.0.1,::1,172.16.0.0/12}"
    case "${value}" in
        '*'|*'0.0.0.0/0'*|*'::/0'*)
            fail "AGENTHIVE_FORWARDED_ALLOW_IPS must not trust every source"
            return
            ;;
    esac
    ok "AGENTHIVE_FORWARDED_ALLOW_IPS is restricted to explicit proxy networks"
}

compose_args() {
    if [ -f "${ENV_FILE}" ]; then
        printf '%s\n' "--env-file" "${ENV_FILE}" "-f" "${COMPOSE_FILE}"
    else
        printf '%s\n' "-f" "${COMPOSE_FILE}"
    fi
}

write_env_summary() {
    if [ -z "${OUTPUT_DIR}" ]; then
        return
    fi
    {
        printf 'key\tstatus\tlength\n'
        for key in \
            POSTGRES_PASSWORD \
            REDIS_PASSWORD \
            MINIO_ROOT_USER \
            MINIO_ROOT_PASSWORD \
            LITELLM_MASTER_KEY \
            AGENTHIVE_PUBLIC_BASE_URL \
            AGENTHIVE_FORWARDED_ALLOW_IPS \
            AGENTHIVE_FRONTEND_HEALTH_URL \
            SECRET_KEY \
            BACKEND_PORT \
            HTTP_PORT \
            MINIO_CONSOLE_PORT \
            RAGFLOW_URL \
            AGENTHIVE_OPENAI_IMAGES_BASE_URL \
            AGENTHIVE_OPENAI_IMAGES_API_KEY \
            AGENTHIVE_NANO_BANANA_BASE_URL \
            AGENTHIVE_NANO_BANANA_API_KEY \
            AGENTHIVE_VOLCENGINE_SEEDANCE_BASE_URL \
            AGENTHIVE_VOLCENGINE_SEEDANCE_API_KEY \
            AGENTHIVE_MEDIA_OPENAI_COMPATIBLE_BASE_URL \
            AGENTHIVE_MEDIA_OPENAI_COMPATIBLE_API_KEY \
            AGENTHIVE_MEDIA_OPENAI_COMPATIBLE_IMAGE_PATH \
            AGENTHIVE_MEDIA_OPENAI_COMPATIBLE_VIDEO_PATH \
            AGENTHIVE_MEDIA_WEBHOOK_SECRET
        do
            value="$(read_env_value "${key}")"
            if [ ! -f "${ENV_FILE}" ]; then
                status="env_file_missing"
            elif is_placeholder_value "${value}"; then
                status="missing_or_template"
            else
                status="configured"
            fi
            printf '%s\t%s\t%s\n' "${key}" "${status}" "${#value}"
        done
    } | write_report_file "env-summary.tsv"
}

probe_url() {
    label="$1"
    url="$2"
    report_slug="$(slugify_label "${label}")"
    if ! has_command curl; then
        warn "curl not found; skipping ${label}: ${url}"
        return
    fi

    body_file="$(mktemp "${TMPDIR:-/tmp}/agenthive-diagnose.XXXXXX")"
    http_code="$(curl -sS -o "${body_file}" -w '%{http_code}' "${url}" 2>"${body_file}.err")"
    curl_status=$?
    if [ -n "${OUTPUT_DIR}" ]; then
        cp "${body_file}" "${OUTPUT_DIR}/${report_slug}.json" 2>/dev/null || true
        {
            printf 'label=%s\n' "${label}"
            printf 'url=%s\n' "${url}"
            printf 'http_code=%s\n' "${http_code}"
            printf 'curl_status=%s\n' "${curl_status}"
        } >"${OUTPUT_DIR}/${report_slug}.meta"
        if [ -s "${body_file}.err" ]; then
            cp "${body_file}.err" "${OUTPUT_DIR}/${report_slug}.stderr" 2>/dev/null || true
        fi
    fi
    if [ "${curl_status}" -ne 0 ]; then
        fail "${label} is not reachable: ${url}"
        sed -n '1,6p' "${body_file}.err"
        rm -f "${body_file}" "${body_file}.err"
        return
    fi

    if [ "${http_code}" -ge 200 ] && [ "${http_code}" -lt 400 ]; then
        ok "${label} HTTP ${http_code}: ${url}"
    else
        fail "${label} HTTP ${http_code}: ${url}"
    fi
    sed -n '1,20p' "${body_file}"
    case "${label}" in
        *readiness*|*Readiness*)
            capture_delivery_summary "${body_file}" || true
            ;;
    esac
    rm -f "${body_file}" "${body_file}.err"
}

probe_authenticated_diagnostics() {
    url="$1"
    if [ -z "${DIAGNOSTICS_TOKEN_VALUE}" ]; then
        printf 'INFO: Skipping authenticated diagnostics export; set AGENTHIVE_DIAGNOSTICS_TOKEN or pass --diagnostics-token\n'
        return
    fi
    if ! has_command curl; then
        warn "curl not found; skipping authenticated diagnostics export"
        return
    fi

    body_file="$(mktemp "${TMPDIR:-/tmp}/agenthive-diagnostics.XXXXXX")"
    stderr_file="${body_file}.err"
    http_code="$(curl -sS -o "${body_file}" -w '%{http_code}' \
        -H "Authorization: Bearer ${DIAGNOSTICS_TOKEN_VALUE}" \
        -H "X-Forwarded-Proto: https" \
        "${url}" 2>"${stderr_file}")"
    curl_status=$?
    if [ -n "${OUTPUT_DIR}" ]; then
        cp "${body_file}" "${OUTPUT_DIR}/system-diagnostics.json" 2>/dev/null || true
        {
            printf 'label=Authenticated diagnostics\n'
            printf 'url=%s\n' "${url}"
            printf 'http_code=%s\n' "${http_code}"
            printf 'curl_status=%s\n' "${curl_status}"
            printf 'token_present=true\n'
            printf 'token_written=false\n'
        } >"${OUTPUT_DIR}/system-diagnostics.meta"
        if [ -s "${stderr_file}" ]; then
            cp "${stderr_file}" "${OUTPUT_DIR}/system-diagnostics.stderr" 2>/dev/null || true
        fi
    fi
    if [ "${curl_status}" -ne 0 ]; then
        fail "Authenticated diagnostics export is not reachable: ${url}"
        sed -n '1,6p' "${stderr_file}"
        rm -f "${body_file}" "${stderr_file}"
        return
    fi
    if [ "${http_code}" -ge 200 ] && [ "${http_code}" -lt 300 ]; then
        ok "Authenticated diagnostics exported HTTP ${http_code}: ${url}"
        capture_delivery_summary "${body_file}" || true
        write_acceptance_checklist "${body_file}" || true
    else
        fail "Authenticated diagnostics export HTTP ${http_code}: ${url}"
        sed -n '1,20p' "${body_file}"
    fi
    rm -f "${body_file}" "${stderr_file}"
}

capture_delivery_summary() {
    body_file="$1"
    if [ -z "${backend_python:-}" ]; then
        return 0
    fi
    delivery_summary="$("${backend_python}" - "${body_file}" <<'PY' 2>/dev/null
import json
import sys

try:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        payload = json.load(handle)
except Exception:
    raise SystemExit(0)

delivery = payload.get("delivery")
readiness = payload
diagnostics = payload.get("diagnostics")
if isinstance(diagnostics, dict) and isinstance(diagnostics.get("readiness"), dict):
    readiness = diagnostics["readiness"]
if not isinstance(delivery, dict):
    delivery = readiness.get("delivery") if isinstance(readiness, dict) else None
if not isinstance(delivery, dict):
    delivery = {}

print(
    "|".join(
        [
            "DELIVERY",
            str(delivery.get("status") or "unknown"),
            str(delivery.get("blocker_count") if delivery.get("blocker_count") is not None else "unknown"),
            str(delivery.get("warning_count") if delivery.get("warning_count") is not None else "unknown"),
        ]
    )
)
components = readiness.get("components") if isinstance(readiness, dict) else None
media = components.get("media_generation") if isinstance(components, dict) else None
if isinstance(media, dict):
    details = media.get("details") if isinstance(media.get("details"), dict) else {}
    providers = details.get("configured_provider_types")
    if isinstance(providers, list):
        providers_value = ",".join(str(item) for item in providers) or "none"
    else:
        providers_value = "unknown"
    missing = details.get("missing_by_provider")
    if isinstance(missing, dict):
        missing_value = ",".join(sorted(str(key) for key in missing.keys())) or "none"
    else:
        missing_value = "unknown"
    print(
        "|".join(
            [
                "MEDIA",
                str(media.get("status") or "unknown"),
                str(details.get("configured_model_count", "unknown")),
                str(details.get("image_model_count", "unknown")),
                str(details.get("video_model_count", "unknown")),
                providers_value,
                missing_value,
            ]
        )
    )
worker = components.get("media_worker") if isinstance(components, dict) else None
if isinstance(worker, dict):
    details = worker.get("details") if isinstance(worker.get("details"), dict) else {}
    print(
        "|".join(
            [
                "MEDIA_WORKER",
                str(worker.get("status") or "unknown"),
                str(details.get("worker_ping_ok", "unknown")),
                str(details.get("worker_count", "unknown")),
            ]
        )
    )
PY
)"
    if [ -z "${delivery_summary}" ]; then
        return 0
    fi
    while IFS='|' read -r summary_kind field1 field2 field3 field4 field5 field6; do
        case "${summary_kind}" in
            DELIVERY)
                DELIVERY_STATUS="${field1:-unknown}"
                DELIVERY_BLOCKERS="${field2:-unknown}"
                DELIVERY_WARNINGS="${field3:-unknown}"
                ;;
            MEDIA)
                MEDIA_GENERATION_STATUS="${field1:-unknown}"
                MEDIA_GENERATION_CONFIGURED_MODELS="${field2:-unknown}"
                MEDIA_GENERATION_IMAGE_MODELS="${field3:-unknown}"
                MEDIA_GENERATION_VIDEO_MODELS="${field4:-unknown}"
                MEDIA_GENERATION_CONFIGURED_PROVIDERS="${field5:-unknown}"
                MEDIA_GENERATION_MISSING_PROVIDERS="${field6:-unknown}"
                ;;
            MEDIA_WORKER)
                MEDIA_WORKER_STATUS="${field1:-unknown}"
                MEDIA_WORKER_PING_OK="${field2:-unknown}"
                MEDIA_WORKER_COUNT="${field3:-unknown}"
                ;;
        esac
    done <<EOF
${delivery_summary}
EOF
}

write_acceptance_checklist() {
    body_file="$1"
    if [ -z "${OUTPUT_DIR}" ] || [ -z "${backend_python:-}" ]; then
        return 0
    fi
    "${backend_python}" - "${body_file}" >"${OUTPUT_DIR}/acceptance-checklist.md" <<'PY' 2>/dev/null
import json
import sys


def as_dict(value):
    return value if isinstance(value, dict) else {}


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


try:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        payload = json.load(handle)
except Exception:
    raise SystemExit(0)

diagnostics = as_dict(payload.get("diagnostics"))
readiness = as_dict(diagnostics.get("readiness") or payload)
health = as_dict(diagnostics.get("health"))
info = as_dict(diagnostics.get("info"))
delivery = as_dict(payload.get("delivery") or readiness.get("delivery"))
components = as_dict(readiness.get("components"))
health_components = as_dict(health.get("components"))

status = str(delivery.get("status") or "unknown")
decision = {
    "ready": "pass",
    "ready_with_warnings": "conditional_pass",
    "blocked": "blocked",
}.get(status, "manual_review")

print("# AgentHive Acceptance Checklist")
print()
print("Generated from the authenticated, redacted AgentHive diagnostics package.")
print()
print("## Decision")
print()
print(f"- Product: {info.get('name', 'AgentHive')} {info.get('version', '-')}")
print(f"- Edition: {info.get('edition', '-')}")
print(f"- Generated at: {payload.get('generated_at', '-')}")
print(f"- Readiness status: {readiness.get('status', '-')}")
print(f"- Delivery status: {status}")
print(f"- Acceptance decision: {decision}")
print(f"- Blockers: {delivery.get('blocker_count', '-')}")
print(f"- Warnings: {delivery.get('warning_count', '-')}")
print()
print("## Required Evidence")
print()
for component_id, label in [
    ("database", "PostgreSQL business database"),
    ("redis", "Redis cache and queue runtime"),
    ("minio", "MinIO object storage"),
    ("pgvector", "PostgreSQL pgvector retrieval store"),
    ("litellm", "LiteLLM model gateway"),
    ("license_identity", "License install identity"),
    ("production_config", "Production secret/config gate"),
    ("agent_runtime", "LangChain/LangGraph Agent runtime"),
    ("media_generation", "Media generation gateway"),
    ("media_worker", "Media generation worker queue"),
    ("frontend", "AgentHive management console"),
]:
    component = as_dict(components.get(component_id))
    component_status = str(component.get("status") or "missing")
    marker = "[x]" if component_status == "healthy" else "[ ]"
    print(f"- {marker} **{label}** (`{component_id}`): {component_status} - {cell(component.get('message', 'not reported'))}")

for title, component_id in [
    ("Deployment Identity", "license_identity"),
    ("Production Configuration", "production_config"),
]:
    print()
    print(f"## {title}")
    print()
    component = as_dict(components.get(component_id) or health_components.get(component_id))
    if not component:
        print("- status: not_reported")
        continue
    print(f"- status: {component.get('status', '-')}")
    print(f"- message: {cell(component.get('message', '-'))}")
    for key, value in sorted(as_dict(component.get("details")).items()):
        print(f"- {key}: {cell(value)}")

for title, key in [("Open Blockers", "blockers"), ("Open Warnings", "warnings")]:
    print()
    print(f"## {title}")
    print()
    issues = delivery.get(key)
    if not isinstance(issues, list) or not issues:
        print("No issues reported.")
        continue
    for issue in issues:
        item = as_dict(issue)
        print(f"- **{item.get('label', item.get('id', 'unknown'))}**")
        print(f"  - Component: {item.get('component', '-')}")
        print(f"  - Status: {item.get('status', '-')}")
        print(f"  - Message: {cell(item.get('message', '-'))}")

print()
print("## Sign-off")
print()
print("- Customer organization:")
print("- Customer owner:")
print("- Implementer:")
print("- Acceptance date:")
print("- Notes:")
print()
print("## Post-Handoff Actions")
print()
print("1. Archive this support bundle with the customer contract and License record.")
print("2. Confirm backup and restore ownership with customer IT.")
print("3. Record enabled Agent modules, model providers, and cost-center owners.")
print("4. Keep API keys, passwords, private keys, and raw License material outside this bundle.")
PY
}

write_summary_report() {
    if [ -z "${OUTPUT_DIR}" ]; then
        return
    fi
    {
        printf 'generated_at=%s\n' "${DIAG_TIMESTAMP}"
        printf 'failures=%s\n' "${FAILURES}"
        printf 'warnings=%s\n' "${WARNINGS}"
        printf 'delivery_status=%s\n' "${DELIVERY_STATUS}"
        printf 'delivery_blockers=%s\n' "${DELIVERY_BLOCKERS}"
        printf 'delivery_warnings=%s\n' "${DELIVERY_WARNINGS}"
        printf 'media_generation_status=%s\n' "${MEDIA_GENERATION_STATUS}"
        printf 'media_generation_configured_models=%s\n' "${MEDIA_GENERATION_CONFIGURED_MODELS}"
        printf 'media_generation_image_models=%s\n' "${MEDIA_GENERATION_IMAGE_MODELS}"
        printf 'media_generation_video_models=%s\n' "${MEDIA_GENERATION_VIDEO_MODELS}"
        printf 'media_generation_configured_providers=%s\n' "${MEDIA_GENERATION_CONFIGURED_PROVIDERS}"
        printf 'media_generation_missing_providers=%s\n' "${MEDIA_GENERATION_MISSING_PROVIDERS}"
        printf 'media_worker_status=%s\n' "${MEDIA_WORKER_STATUS}"
        printf 'media_worker_ping_ok=%s\n' "${MEDIA_WORKER_PING_OK}"
        printf 'media_worker_count=%s\n' "${MEDIA_WORKER_COUNT}"
        printf 'strict=%s\n' "${STRICT}"
        printf 'compose_file=%s\n' "${COMPOSE_FILE}"
        printf 'env_file=%s\n' "${ENV_FILE}"
    } | write_report_file "summary.txt"
}

init_output_dir
if [ -n "${OUTPUT_DIR}" ]; then
    exec > >(tee "${OUTPUT_DIR}/diagnose.log") 2>&1
fi

section "AgentHive Diagnostics"
printf 'Timestamp:         %s\n' "${DIAG_TIMESTAMP}"
printf 'Working directory: %s\n' "$(pwd)"
printf 'Compose file:      %s\n' "${COMPOSE_FILE}"
printf 'Env file:          %s\n' "${ENV_FILE}"
printf 'Mode:              %s\n' "$([ "${STRICT}" -eq 1 ] && printf strict || printf support)"
printf 'Auth diagnostics:  %s\n' "$([ -n "${DIAGNOSTICS_TOKEN_VALUE}" ] && printf enabled || printf disabled)"
if [ -n "${OUTPUT_DIR}" ]; then
    printf 'Output directory:  %s\n' "${OUTPUT_DIR}"
fi

section "Required Files"
for path in "${COMPOSE_FILE}" "docker-compose.yml" "docker-compose.dev.yml" "nginx/nginx.conf" "litellm/config.yaml.example" "backend/pyproject.toml" "frontend/package.json"; do
    if [ -e "$path" ]; then
        ok "$path"
    else
        fail "$path is missing"
    fi
done

if [ -f "${ENV_FILE}" ]; then
    ok "${ENV_FILE}"
else
    warn "${ENV_FILE} is missing; using development defaults where possible"
fi
write_env_summary

section "Production Configuration"
if is_production_compose; then
    if [ -f "${ENV_FILE}" ]; then
        check_required_config "POSTGRES_PASSWORD" 16
        check_required_config "REDIS_PASSWORD" 16
        check_required_config "MINIO_ROOT_USER" 3
        check_required_config "MINIO_ROOT_PASSWORD" 16
        check_required_config "LITELLM_MASTER_KEY" 24
        check_required_config "SECRET_KEY" 32
        check_https_public_base_url
        check_forwarded_allow_ips
    else
        fail "Production compose requires ${ENV_FILE}; run scripts/install.sh or copy .env.example to .env and replace every secret"
    fi
else
    ok "Development compose selected; production secret gate skipped"
fi

section "Toolchain"
if has_command docker; then
    docker --version
else
    fail "Docker not found in PATH"
fi

if has_command docker && docker compose version >/dev/null 2>&1; then
    docker compose version
else
    fail "Docker Compose v2 is not available"
fi

if has_command curl; then
    ok "curl: $(command -v curl)"
else
    warn "curl not found"
fi

if has_command node; then
    node --version
else
    warn "node not found"
fi

if has_command npm; then
    npm --version
else
    warn "npm not found"
fi

if [ -x "backend/.venv/bin/python" ]; then
    backend_python="backend/.venv/bin/python"
elif has_command python3; then
    backend_python="$(command -v python3)"
else
    backend_python=""
fi

if [ -n "${backend_python}" ]; then
    "${backend_python}" --version
else
    fail "Python 3.12 runtime not found"
fi

section "Docker"
if has_command docker && docker info >/dev/null 2>&1; then
    DOCKER_DAEMON_READY=1
    ok "Docker daemon is reachable"
else
    fail "Docker daemon is not reachable"
fi

if has_command docker && docker compose version >/dev/null 2>&1; then
    if docker compose $(compose_args) config >/dev/null; then
        ok "Compose configuration parses successfully"
    else
        fail "Compose configuration failed to parse"
    fi
else
    warn "Skipping Compose config parse because docker compose is unavailable"
fi

if [ "${DOCKER_DAEMON_READY}" -eq 1 ]; then
    compose_ps_output="$(docker compose $(compose_args) ps 2>&1)"
    printf '%s\n' "${compose_ps_output}"
    printf '%s\n' "${compose_ps_output}" | write_report_file "docker-compose-ps.txt"
else
    warn "Skipping Compose service status because Docker daemon is not reachable"
fi

section "Backend Health"
if [ -z "${HTTP_PORT_VALUE}" ]; then
    HTTP_PORT_VALUE="$(read_env_value HTTP_PORT)"
fi
if [ -z "${HTTP_PORT_VALUE}" ]; then
    if [ "${COMPOSE_FILE}" = "docker-compose.dev.yml" ]; then
        HTTP_PORT_VALUE="8080"
    else
        HTTP_PORT_VALUE="80"
    fi
fi

if [ -z "${BACKEND_PORT_VALUE}" ]; then
    BACKEND_PORT_VALUE="$(read_env_value BACKEND_PORT)"
fi
BACKEND_PORT_VALUE="${BACKEND_PORT_VALUE:-8000}"

if [ "${HTTP_PORT_VALUE}" = "80" ]; then
    origin_base_url="http://localhost"
else
    origin_base_url="http://localhost:${HTTP_PORT_VALUE}"
fi
backend_base_url="http://localhost:${BACKEND_PORT_VALUE}"

probe_url "Loopback origin liveness" "${origin_base_url}/api/v1/health"
probe_url "Loopback origin readiness" "${origin_base_url}/api/v1/health/readiness"
probe_url "Backend direct liveness" "${backend_base_url}/api/v1/health"
probe_url "Backend direct readiness" "${backend_base_url}/api/v1/health/readiness"

section "Authenticated Diagnostics Package"
probe_authenticated_diagnostics "${origin_base_url}/api/v1/system/diagnostics"

section "Database And Migrations"
if [ -n "${backend_python}" ]; then
    if migration_head="$(PYTHONPATH=backend "${backend_python}" -c 'from app.services.migration_service import get_migration_head; print(get_migration_head() or "none")' 2>&1)"; then
        ok "Alembic head revision: ${migration_head}"
        printf 'Alembic head revision: %s\n' "${migration_head}" | write_report_file "database/migration-head.txt"
    else
        fail "Unable to read Alembic head revision"
        printf '%s\n' "${migration_head}"
        printf '%s\n' "${migration_head}" | write_report_file "database/migration-head.txt"
    fi

    if db_check_output="$(PYTHONPATH=backend "${backend_python}" backend/scripts/check_db.py 2>&1)"; then
        ok "Database schema, official modules, pgvector, and vector index are ready"
        printf '%s\n' "${db_check_output}"
        printf '%s\n' "${db_check_output}" | write_report_file "database/check-db.txt"
    else
        fail "Database readiness check failed"
        printf '%s\n' "${db_check_output}"
        printf '%s\n' "${db_check_output}" | write_report_file "database/check-db.txt"
    fi
else
    warn "Skipping database checks because Python is unavailable"
fi

section "Frontend"
if [ -d "frontend/node_modules" ]; then
    ok "frontend/node_modules is present"
else
    warn "frontend/node_modules is missing; run npm --prefix frontend install"
fi

if [ -f "frontend/dist/index.html" ]; then
    ok "frontend/dist/index.html is present"
else
    warn "frontend build artifact is missing; run npm --prefix frontend run build"
fi

if [ -f "frontend/package.json" ]; then
    if grep -q '"build"' frontend/package.json && grep -q '"check"' frontend/package.json; then
        ok "frontend package has build and check scripts"
    else
        warn "frontend package is missing build or check script"
    fi
fi

section "Access Hints"
printf 'Frontend dev server:     http://localhost:5173 or next available Vite port\n'
printf 'Backend direct health:   %s/api/v1/health\n' "${backend_base_url}"
printf 'Backend direct readiness:%s/api/v1/health/readiness\n' "${backend_base_url}"
printf 'Diagnostics package:     %s/api/v1/system/diagnostics (requires system:diagnostics)\n' "${origin_base_url}"
printf 'Loopback origin health:  %s/api/v1/health\n' "${origin_base_url}"
configured_https_origin="$(read_env_value AGENTHIVE_PUBLIC_BASE_URL)"
printf 'Customer HTTPS origin:   %s\n' "${configured_https_origin:-not-configured}"
if [ -z "${MINIO_CONSOLE_PORT_VALUE}" ]; then
    MINIO_CONSOLE_PORT_VALUE="$(read_env_value MINIO_CONSOLE_PORT)"
fi
printf 'MinIO console:           http://localhost:%s\n' "${MINIO_CONSOLE_PORT_VALUE:-9001}"

section "Summary"
printf 'Failures: %s\n' "${FAILURES}"
printf 'Warnings: %s\n' "${WARNINGS}"
printf 'Delivery readiness: %s (blockers=%s, warnings=%s)\n' \
    "${DELIVERY_STATUS}" "${DELIVERY_BLOCKERS}" "${DELIVERY_WARNINGS}"
printf 'Media generation:   %s (configured_models=%s, image=%s, video=%s)\n' \
    "${MEDIA_GENERATION_STATUS}" \
    "${MEDIA_GENERATION_CONFIGURED_MODELS}" \
    "${MEDIA_GENERATION_IMAGE_MODELS}" \
    "${MEDIA_GENERATION_VIDEO_MODELS}"
printf 'Media providers:    configured=%s missing=%s\n' \
    "${MEDIA_GENERATION_CONFIGURED_PROVIDERS}" \
    "${MEDIA_GENERATION_MISSING_PROVIDERS}"
if [ -n "${OUTPUT_DIR}" ]; then
    write_summary_report
    printf 'Support bundle: %s\n' "${OUTPUT_DIR}"
fi

if [ "${STRICT}" -eq 1 ] && [ "${FAILURES}" -gt 0 ]; then
    exit 1
fi

exit 0
