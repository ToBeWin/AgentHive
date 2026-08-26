#!/bin/sh
set -eu

# LiteLLM owns its Prisma schema and migration lifecycle. It must never share
# AgentHive's business database, even when both services use one PostgreSQL instance.
litellm_database="${LITELLM_POSTGRES_DB:-litellm}"
agenthive_database="${POSTGRES_DB:-agenthive}"

if [ "${litellm_database}" = "${agenthive_database}" ]; then
    printf '%s\n' 'ERROR: LITELLM_POSTGRES_DB must differ from POSTGRES_DB (AgentHive business database).' >&2
    exit 1
fi

psql --set=ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${agenthive_database}" \
    --set=litellm_database="${litellm_database}" <<'SQL'
SELECT format('CREATE DATABASE %I', :'litellm_database')
WHERE NOT EXISTS (
    SELECT 1 FROM pg_database WHERE datname = :'litellm_database'
) \gexec
SQL
