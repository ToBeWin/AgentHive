# AgentHive Remote Infrastructure Development

This mode runs only infrastructure on a small server while the AgentHive backend,
frontend, and worker run on the developer machine.

## Server Layout

```text
/opt/agenthive/
├── docker-compose.infra.yml
├── .env.infra
├── infra/postgres/init/
│   ├── 01_extensions.sql
│   └── 02_create_litellm_database.sh
└── infra/litellm/config.yaml
```

`docker-compose.infra.yml` mounts `LITELLM_CONFIG_FILE`, which defaults to
`./infra/litellm/config.yaml`. Keep that default for the shipped layout; a
reviewed server-specific config may use another relative path by setting
`LITELLM_CONFIG_FILE` in `.env.infra`.

The infrastructure compose file binds PostgreSQL, Redis, and MinIO to
`127.0.0.1` on the server. Do not expose these ports directly to the public
internet. Use an SSH tunnel from your local machine.

## Services

```text
PostgreSQL + pgvector: 127.0.0.1:5432 on the server
Redis:                 127.0.0.1:6379 on the server
MinIO API:             127.0.0.1:9000 on the server
MinIO Console:         127.0.0.1:9001 on the server
LiteLLM Proxy:         127.0.0.1:4000 on the server
```

## Local SSH Tunnel

Recommended local launch command:

```bash
scripts/dev-remote-infra.sh
```

This command starts the SSH tunnel, runs backend migrations, starts FastAPI,
starts the media Celery worker, starts the Vite frontend, and prints the
setup/readiness responses. It keeps all local processes in one terminal and
stops them together on `Ctrl+C`.

PostgreSQL, Redis, and MinIO are treated as mandatory for local development.
LiteLLM is probed with the `LITELLM_MASTER_KEY` from `backend/.env` and
reported, but a failed LiteLLM `/health` check does not stop the tunnel or
local app startup. This lets teams keep developing the core platform and direct
OpenAI-compatible providers while investigating a LiteLLM image pull, startup,
auth, or network issue separately.

If you need to debug pieces independently, start the tunnel manually:

```bash
ssh -i ~/.ssh/agenthive_codex_ed25519 -N \
  -L 15432:127.0.0.1:5432 \
  -L 16379:127.0.0.1:6379 \
  -L 19000:127.0.0.1:9000 \
  -L 19001:127.0.0.1:9001 \
  -L 14000:127.0.0.1:4000 \
  ubuntu@123.207.181.198
```

Keep this terminal open while developing locally.

## Local Backend Environment

Copy the template and replace the three server-generated secrets:

```bash
cp backend/.env.remote-infra.example backend/.env
```

Then run migrations and demo data from your local backend:

```bash
cd backend
PYTHONPATH=. python scripts/init_db.py
PYTHONPATH=. python scripts/seed_demo.py
PYTHONPATH=. python scripts/check_db.py
```

When using `scripts/dev-remote-infra.sh`, the script runs migrations
automatically. Add `--seed-demo` if the demo tenant should be refreshed before
the local services start.

After the backend and frontend are running, execute the HTTP smoke checks:

```bash
scripts/smoke-local.sh
```

The smoke check logs in with the demo administrator, validates Agent modules,
Agent instances, model governance, media model catalog, knowledge retrieval,
chat messages, and the customer-service Agent run path through real HTTP calls.

## Server Operations

```bash
cd /opt/agenthive
docker compose --env-file .env.infra -f docker-compose.infra.yml ps
docker compose --env-file .env.infra -f docker-compose.infra.yml logs -f --tail=100
docker compose --env-file .env.infra -f docker-compose.infra.yml up -d
docker compose --env-file .env.infra -f docker-compose.infra.yml down
```

Do not use `down -v` unless you intentionally want to delete all database,
Redis, and MinIO data.

For servers in mainland China, set `LITELLM_IMAGE` in `.env.infra` to a
reachable GHCR mirror such as:

```bash
LITELLM_IMAGE=ghcr.nju.edu.cn/berriai/litellm:main-latest
```

Keep the compose file unchanged and switch only the environment variable, so
overseas deployments can use the acceptance-tested immutable image tag from `.env.example`.
