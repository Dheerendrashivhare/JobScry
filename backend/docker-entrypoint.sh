#!/usr/bin/env sh
set -e

# Only the API container migrates (RUN_MIGRATIONS=1). The worker and beat containers
# start from the same image but must NOT race each other applying the same revision.
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    echo "[entrypoint] applying database migrations..."
    alembic upgrade head
    echo "[entrypoint] migrations up to date."
fi

exec "$@"
