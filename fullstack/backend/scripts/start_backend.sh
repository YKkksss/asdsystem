#!/usr/bin/env sh

set -eu

cd /app

python scripts/wait_for_services.py 180 mysql:3306 redis:6379

exec uv run manage.py runserver 0.0.0.0:8000
