#!/usr/bin/env bash
# Godínez IndustrialEngineer — Production startup script
# Flow: wait for DB → alembic upgrade head → exec uvicorn
set -euo pipefail

echo "── Godínez IndustrialEngineer ──────────────────────────────────"
echo "   $(date -u '+%Y-%m-%dT%H:%M:%SZ')"

DB_URL="${DATABASE_URL:-off}"

# ── Wait for database ─────────────────────────────────────────────
if [[ "$DB_URL" != "off" ]]; then
    echo "Waiting for database..."
    python - <<'PYEOF'
import os, sys, time
from sqlalchemy import create_engine, text

url = os.environ["DATABASE_URL"]
for attempt in range(1, 31):
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"  Database ready (attempt {attempt})")
        sys.exit(0)
    except Exception as exc:
        print(f"  Not ready ({attempt}/30): {exc}")
        time.sleep(2)

print("ERROR: Database did not become ready in 60 s", file=sys.stderr)
sys.exit(1)
PYEOF

    # ── Run migrations ────────────────────────────────────────────
    echo "Running Alembic migrations..."
    alembic upgrade head
    echo "Migrations complete."
fi

# ── Worker count ──────────────────────────────────────────────────
# SQLite doesn't support concurrent writes from multiple processes.
if [[ "$DB_URL" == "sqlite"* ]] || [[ "$DB_URL" == "off" ]]; then
    EFFECTIVE_WORKERS=1
else
    EFFECTIVE_WORKERS="${WORKERS:-2}"
fi

echo "Starting uvicorn: ${EFFECTIVE_WORKERS} worker(s) on port ${PORT:-8000}"

# exec replaces the shell so Docker SIGTERM reaches uvicorn directly (graceful shutdown).
exec uvicorn src.api.app:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "$EFFECTIVE_WORKERS" \
    --timeout-keep-alive 30 \
    --access-log \
    --log-level "${LOG_LEVEL:-info}"
