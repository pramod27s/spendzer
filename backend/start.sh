#!/bin/sh
# Container entrypoint: migrate, seed, train the category model, serve.
set -e
alembic upgrade head
python -m app.seed.seed
python -m app.ml.train || echo "ML model training failed; the ML layer stays off"
if [ "${SEED_DEMO:-false}" = "true" ]; then
  python -m app.seed.demo
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
