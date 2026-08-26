#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"

SSH_HOST="${AGENTHIVE_REMOTE_HOST:-123.207.181.198}"
SSH_USER="${AGENTHIVE_REMOTE_USER:-ubuntu}"
SSH_KEY="${AGENTHIVE_REMOTE_SSH_KEY:-${HOME}/.ssh/agenthive_codex_ed25519}"
BACKEND_ENV_FILE="${AGENTHIVE_BACKEND_ENV_FILE:-${BACKEND_DIR}/.env}"
BACKEND_PORT="${AGENTHIVE_BACKEND_PORT:-8000}"
FRONTEND_PORT="${AGENTHIVE_FRONTEND_PORT:-5173}"
START_TUNNEL=1
START_BACKEND=1
START_WORKER=1
START_FRONTEND=1
RUN_MIGRATIONS=1
SEED_DEMO=0

PIDS=()

usage() {
    cat <<'USAGE'
AgentHive local services with remote infrastructure

Usage:
  scripts/dev-remote-infra.sh [options]

This starts the local development stack against remote private infrastructure:
SSH tunnel -> FastAPI backend -> Celery media worker -> Vite frontend.

Options:
  --host HOST          Remote SSH host. Default: AGENTHIVE_REMOTE_HOST or 123.207.181.198.
  --user USER          Remote SSH user. Default: AGENTHIVE_REMOTE_USER or ubuntu.
  --ssh-key PATH       SSH private key. Default: AGENTHIVE_REMOTE_SSH_KEY or ~/.ssh/agenthive_codex_ed25519.
  --env-file PATH      Backend .env file. Default: backend/.env.
  --skip-tunnel        Do not start the SSH tunnel.
  --skip-backend       Do not start FastAPI.
  --skip-worker        Do not start the Celery media worker.
  --skip-frontend      Do not start Vite frontend.
  --skip-migrations    Do not run Alembic migrations before starting services.
  --seed-demo          Run idempotent demo seed after migrations.
  -h, --help           Show this help.

Required backend/.env local tunnel ports:
  PostgreSQL 127.0.0.1:15432
  Redis      127.0.0.1:16379
  MinIO      127.0.0.1:19000
  LiteLLM    127.0.0.1:14000
USAGE
}

log() {
    printf '[agenthive-dev] %s\n' "$1"
}

fail() {
    printf '[agenthive-dev] ERROR: %s\n' "$1" >&2
    exit 1
}

has_command() {
    command -v "$1" >/dev/null 2>&1
}

env_file_value() {
    key="$1"
    file="$2"
    if [ ! -f "${file}" ]; then
        return 0
    fi
    grep -E "^${key}=" "${file}" | tail -n 1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"
}

cleanup() {
    if [ "${#PIDS[@]}" -eq 0 ]; then
        return
    fi
    log "Stopping local services..."
    for pid in "${PIDS[@]}"; do
        if kill -0 "${pid}" >/dev/null 2>&1; then
            kill "${pid}" >/dev/null 2>&1 || true
        fi
    done
}

wait_for_http() {
    name="$1"
    url="$2"
    timeout_seconds="$3"
    started_at="$(date +%s)"
    while true; do
        if curl -fsS "${url}" >/dev/null 2>&1; then
            log "${name} is reachable: ${url}"
            return 0
        fi
        now="$(date +%s)"
        if [ $((now - started_at)) -ge "${timeout_seconds}" ]; then
            fail "${name} did not become reachable at ${url}"
        fi
        sleep 1
    done
}

wait_for_http_optional() {
    name="$1"
    url="$2"
    timeout_seconds="$3"
    bearer_token="${4:-}"
    started_at="$(date +%s)"
    while true; do
        if [ -n "${bearer_token}" ]; then
            curl_command=(curl -fsS -H "Authorization: Bearer ${bearer_token}" "${url}")
        else
            curl_command=(curl -fsS "${url}")
        fi
        if "${curl_command[@]}" >/dev/null 2>&1; then
            log "${name} is reachable: ${url}"
            return 0
        fi
        now="$(date +%s)"
        if [ $((now - started_at)) -ge "${timeout_seconds}" ]; then
            log "WARN: ${name} did not become reachable at ${url}; continuing without blocking core infrastructure."
            return 0
        fi
        sleep 1
    done
}

wait_for_tcp() {
    name="$1"
    host="$2"
    port="$3"
    timeout_seconds="$4"
    started_at="$(date +%s)"
    while true; do
        if nc -z "${host}" "${port}" >/dev/null 2>&1; then
            log "${name} is reachable: ${host}:${port}"
            return 0
        fi
        now="$(date +%s)"
        if [ $((now - started_at)) -ge "${timeout_seconds}" ]; then
            fail "${name} did not become reachable at ${host}:${port}"
        fi
        sleep 1
    done
}

run_in_background() {
    name="$1"
    workdir="$2"
    shift 2
    log "Starting ${name}..."
    (
        cd "${workdir}"
        exec "$@"
    ) &
    pid="$!"
    PIDS+=("${pid}")
    log "${name} pid=${pid}"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --host)
            SSH_HOST="${2:-}"
            shift 2
            ;;
        --user)
            SSH_USER="${2:-}"
            shift 2
            ;;
        --ssh-key)
            SSH_KEY="${2:-}"
            shift 2
            ;;
        --env-file)
            BACKEND_ENV_FILE="${2:-}"
            shift 2
            ;;
        --skip-tunnel)
            START_TUNNEL=0
            shift
            ;;
        --skip-backend)
            START_BACKEND=0
            shift
            ;;
        --skip-worker)
            START_WORKER=0
            shift
            ;;
        --skip-frontend)
            START_FRONTEND=0
            shift
            ;;
        --skip-migrations)
            RUN_MIGRATIONS=0
            shift
            ;;
        --seed-demo)
            SEED_DEMO=1
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            fail "Unknown option: $1"
            ;;
    esac
done

trap cleanup EXIT INT TERM

[ -d "${BACKEND_DIR}" ] || fail "backend directory not found"
[ -d "${FRONTEND_DIR}" ] || fail "frontend directory not found"
[ -f "${BACKEND_ENV_FILE}" ] || fail "backend env file not found: ${BACKEND_ENV_FILE}"

has_command ssh || fail "ssh is required"
has_command nc || fail "nc is required"
has_command curl || fail "curl is required"

LITELLM_HEALTH_KEY="${LITELLM_MASTER_KEY:-$(env_file_value LITELLM_MASTER_KEY "${BACKEND_ENV_FILE}")}"

if [ "${START_TUNNEL}" -eq 1 ]; then
    [ -f "${SSH_KEY}" ] || fail "SSH key not found: ${SSH_KEY}"
    run_in_background "SSH tunnel" "${ROOT_DIR}" \
        ssh -i "${SSH_KEY}" \
            -o BatchMode=yes \
            -o ExitOnForwardFailure=yes \
            -o ServerAliveInterval=30 \
            -o ServerAliveCountMax=3 \
            -N \
            -L 15432:127.0.0.1:5432 \
            -L 16379:127.0.0.1:6379 \
            -L 19000:127.0.0.1:9000 \
            -L 19001:127.0.0.1:9001 \
            -L 14000:127.0.0.1:4000 \
            "${SSH_USER}@${SSH_HOST}"
    wait_for_tcp "PostgreSQL tunnel" 127.0.0.1 15432 20
    wait_for_tcp "Redis tunnel" 127.0.0.1 16379 20
    wait_for_tcp "MinIO tunnel" 127.0.0.1 19000 20
    wait_for_http_optional "LiteLLM tunnel" "http://127.0.0.1:14000/health" 30 "${LITELLM_HEALTH_KEY}"
fi

if [ "${RUN_MIGRATIONS}" -eq 1 ]; then
    log "Running Alembic migrations..."
    (
        cd "${BACKEND_DIR}"
        uv run alembic upgrade head
    )
fi

if [ "${SEED_DEMO}" -eq 1 ]; then
    log "Seeding demo tenant..."
    (
        cd "${BACKEND_DIR}"
        PYTHONPATH=. uv run python scripts/seed_demo.py
    )
fi

if [ "${START_BACKEND}" -eq 1 ]; then
    run_in_background "FastAPI backend" "${BACKEND_DIR}" \
        uv run uvicorn app.main:app --host 0.0.0.0 --port "${BACKEND_PORT}"
    wait_for_http "Backend setup API" "http://127.0.0.1:${BACKEND_PORT}/api/v1/auth/setup-status" 45
fi

if [ "${START_WORKER}" -eq 1 ]; then
    run_in_background "Celery media worker" "${BACKEND_DIR}" \
        uv run celery -A app.workers.celery_app.celery_app worker \
            --loglevel=INFO \
            --queues=celery \
            --hostname=agenthive-worker@%h
fi

if [ "${START_FRONTEND}" -eq 1 ]; then
    run_in_background "Vite frontend" "${FRONTEND_DIR}" npm run dev
    wait_for_http "Frontend" "http://127.0.0.1:${FRONTEND_PORT}" 45
fi

log "Setup status:"
curl -fsS "http://127.0.0.1:${BACKEND_PORT}/api/v1/auth/setup-status"
printf '\n'

log "Readiness summary:"
curl -fsS "http://127.0.0.1:${BACKEND_PORT}/api/v1/health/readiness" || true
printf '\n'

log "AgentHive is running at http://localhost:${FRONTEND_PORT}"
log "Press Ctrl+C to stop the local backend, worker, frontend, and tunnel."
wait
