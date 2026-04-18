#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PG_BIN="/opt/homebrew/opt/postgresql@16/bin"
PG_DATA="$ROOT_DIR/.postgres-data"
PG_RUN="$ROOT_DIR/.postgres-run"
PG_LOG="$PG_RUN/postgres.log"
PG_PORT="5432"

mkdir -p "$PG_DATA" "$PG_RUN"

if [ ! -f "$PG_DATA/PG_VERSION" ]; then
  "$PG_BIN/initdb" -D "$PG_DATA" -U postgres --auth=trust
fi

if "$PG_BIN/pg_isready" -h "$PG_RUN" -p "$PG_PORT" -U postgres >/dev/null 2>&1; then
  echo "PostgreSQL is already running on socket $PG_RUN"
else
  "$PG_BIN/pg_ctl" -D "$PG_DATA" -l "$PG_LOG" -o "-k $PG_RUN -p $PG_PORT" start
fi

if ! "$PG_BIN/psql" -h "$PG_RUN" -p "$PG_PORT" -U postgres -lqt | cut -d \| -f 1 | grep -qw "finance_tracker"; then
  "$PG_BIN/createdb" -h "$PG_RUN" -p "$PG_PORT" -U postgres finance_tracker
fi

echo "PostgreSQL is running on socket $PG_RUN"
