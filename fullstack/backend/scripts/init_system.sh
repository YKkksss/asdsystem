#!/usr/bin/env sh

set -eu

cd /app

python scripts/wait_for_services.py 180 mysql:3306 redis:6379

uv run manage.py migrate --noinput

uv run manage.py bootstrap_system \
  --username "${ASD_ADMIN_USERNAME:-admin}" \
  --password "${ASD_ADMIN_PASSWORD:-Admin12345}" \
  --real-name "${ASD_ADMIN_REAL_NAME:-系统管理员}" \
  --dept-code "${ASD_ROOT_DEPT_CODE:-ROOT}" \
  --dept-name "${ASD_ROOT_DEPT_NAME:-总部}" \
  --account-file "/deployment_runtime/accounts.md"
