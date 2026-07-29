#!/bin/sh
set -e

echo "[entrypoint] Waiting for database (if any)..."
# Optional short delay when Postgres is starting (compose healthcheck usually enough)
if [ -n "$DATABASE_URL" ]; then
  python - <<'PY' || true
import os, time, sys
url = os.environ.get("DATABASE_URL", "")
if not url or url.startswith("sqlite"):
    sys.exit(0)
# Retry connect up to ~30s
try:
    import sqlalchemy
    from sqlalchemy import create_engine, text
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    engine = create_engine(url, pool_pre_ping=True)
    for i in range(15):
        try:
            with engine.connect() as c:
                c.execute(text("SELECT 1"))
            print("[entrypoint] Database is reachable.")
            break
        except Exception as e:
            print(f"[entrypoint] DB not ready ({e}); retry {i+1}/15...")
            time.sleep(2)
    else:
        print("[entrypoint] WARNING: database still not reachable; continuing.")
except Exception as e:
    print(f"[entrypoint] Skip wait: {e}")
PY
fi

if [ "${AUTO_MIGRATE:-true}" = "true" ] || [ "${AUTO_MIGRATE:-true}" = "1" ]; then
  echo "[entrypoint] Applying database migrations..."
  python scripts/db_upgrade.py || {
    echo "[entrypoint] Migration script failed; app factory may still auto-migrate."
  }
fi

echo "[entrypoint] Starting application..."
exec "$@"
