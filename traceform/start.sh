#!/bin/sh
set -e
echo "Running database migrations..."
python -m db.migrate
echo "Starting TraceForm API..."
exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
