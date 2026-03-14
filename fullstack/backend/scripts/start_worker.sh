#!/usr/bin/env sh

set -eu

cd /app

python scripts/wait_for_services.py 180 mysql:3306 redis:6379

exec uv run celery -A config.celery:app worker --loglevel=info
