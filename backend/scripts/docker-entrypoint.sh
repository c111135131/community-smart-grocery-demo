#!/bin/sh
# Container start-up: wait for PostgreSQL, apply migrations, seed demo data, serve the API.
# Migrations and seeding are idempotent, so restarting the container is safe and never
# resets stock or order history.
set -e

python -m app.wait_for_db --timeout "${DB_WAIT_TIMEOUT:-60}"
alembic upgrade head
python -m app.seed
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
