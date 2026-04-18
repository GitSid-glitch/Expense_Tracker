#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PG_BIN="/opt/homebrew/opt/postgresql@16/bin"
PG_DATA="$ROOT_DIR/.postgres-data"

if [ ! -f "$PG_DATA/postmaster.pid" ]; then
  echo "PostgreSQL is not running."
  exit 0
fi

"$PG_BIN/pg_ctl" -D "$PG_DATA" stop
