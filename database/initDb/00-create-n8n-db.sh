#!/usr/bin/env bash
set -euo pipefail

POSTGRES_N8N_USER="${POSTGRES_N8N_USER:-n8n_user}"
POSTGRES_N8N_PASSWORD="${POSTGRES_N8N_PASSWORD:-n8n}"
POSTGRES_N8N_DB="${POSTGRES_N8N_DB:-n8n_db}"

psql_admin() {
	psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres "$@"
}

psql_n8n_db() {
	psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_N8N_DB" "$@"
}

strip_ws() {
	local value="$1"
	value="${value//[[:space:]]/}"
	printf '%s' "$value"
}

role_exists=$(psql_admin -tAc "SELECT 1 FROM pg_roles WHERE rolname = '$POSTGRES_N8N_USER';" || true)
if [ "$(strip_ws "$role_exists")" != "1" ]; then
	psql_admin -c "CREATE ROLE \"$POSTGRES_N8N_USER\" LOGIN PASSWORD '$POSTGRES_N8N_PASSWORD';"
fi

db_exists=$(psql_admin -tAc "SELECT 1 FROM pg_database WHERE datname = '$POSTGRES_N8N_DB';" || true)
if [ "$(strip_ws "$db_exists")" != "1" ]; then
	psql_admin -c "CREATE DATABASE \"$POSTGRES_N8N_DB\" OWNER \"$POSTGRES_N8N_USER\";"
fi

psql_n8n_db <<-EOSQL
ALTER SCHEMA public OWNER TO "$POSTGRES_N8N_USER";
GRANT ALL ON SCHEMA public TO "$POSTGRES_N8N_USER";
EOSQL