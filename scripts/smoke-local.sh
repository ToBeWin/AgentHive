#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${AGENTHIVE_SMOKE_BASE_URL:-http://127.0.0.1:8000}"
TENANT="${AGENTHIVE_SMOKE_TENANT:-demo}"
EMAIL="${AGENTHIVE_SMOKE_EMAIL:-admin@example.com}"
PASSWORD="${AGENTHIVE_SMOKE_PASSWORD:-AgentHive123!}"

exec python3 "${ROOT_DIR}/scripts/smoke_http.py" \
    --base-url "${BASE_URL}" \
    --tenant "${TENANT}" \
    --email "${EMAIL}" \
    --password "${PASSWORD}" \
    "$@"
