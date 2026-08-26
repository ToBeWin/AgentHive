# AgentHive Load Tests

Baseline load tests using [k6](https://k6.io/). Verifies the platform's
concurrency defaults declared in
[`backend/app/core/config.py`](../../backend/app/core/config.py):

| Setting | Default | Description |
|---|---|---|
| `AGENT_CONCURRENCY_TENANT_LIMIT` | 40 | Max concurrent agent runs per tenant |
| `AGENT_CONCURRENCY_USER_LIMIT` | 4 | Max concurrent agent runs per user |
| `AGENT_CONCURRENCY_AGENT_LIMIT` | 12 | Max concurrent runs per agent instance |

## Setup

```bash
# 1. Start the dev stack (with seeded demo data)
docker compose -f docker-compose.dev.yml up -d

# 2. Install k6
brew install k6         # macOS
# or: https://k6.io/docs/getting-started/installation/

# 3. Verify the stack is up
curl -sf http://127.0.0.1:18080/api/v1/health
```

## Run

```bash
# Smoke test (default 10 VUs, 35s duration)
k6 run tests/load/smoke.js

# Custom load
k6 run --vus 50 --duration 60s tests/load/smoke.js

# Against a different endpoint
AGENTHIVE_LOAD_BASE_URL=https://staging.example.com k6 run tests/load/smoke.js
```

## What the script covers

| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/api/v1/health` | GET | none | Liveness probe baseline latency |
| `/api/v1/auth/login` | POST | none | Login throughput + token issuance |
| `/api/v1/metrics` | GET | none | Prometheus exposition overhead |
| `/api/v1/agents/instances` | GET | Bearer | Authenticated list endpoint |

## Thresholds

- `http_req_failed`: < 1% error rate
- `http_req_duration{endpoint:health}` p95 < 200ms
- `http_req_duration{endpoint:login}` p95 < 500ms
- `http_req_duration{endpoint:metrics}` p95 < 200ms

A summary JSON report is written to `tests/load/report.json` on completion.

## Interpreting results

- If `login` p95 exceeds 500ms with < 10 VUs, check `bcrypt` cost factor and
  database connection pool size.
- If `agents` 429 rate rises, the rate-limit middleware (default 120 req/60s
  per client+tenant+path) is throttling — tune `RATE_LIMIT_REQUESTS`.
- If `agents` 503 rate rises under load, the agent concurrency limiter is
  rejecting requests — tune `AGENT_CONCURRENCY_TENANT_LIMIT`.

## Adding scenarios

- **Chat run**: POST `/api/v1/chat/sessions` + stream `/api/v1/chat/sessions/{id}/stream`
- **Builder validate**: POST `/api/v1/agents/builder/validate`
- **Knowledge retrieval**: POST `/api/v1/knowledge/{id}/retrieval-test`

Each new scenario should declare its own `endpoint` tag so thresholds can be
scoped per-endpoint.
