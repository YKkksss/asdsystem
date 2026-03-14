#!/usr/bin/env bash

set -euo pipefail

FULLSTACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="${FULLSTACK_DIR}/backend"
RUNTIME_DIR="${FULLSTACK_DIR}/runtime/test_results/e2e_runtime"
DB_PATH="${RUNTIME_DIR}/e2e.sqlite3"
ACCOUNT_FILE="${RUNTIME_DIR}/e2e_accounts.md"

mkdir -p "${RUNTIME_DIR}"
rm -f "${DB_PATH}"

export DB_ENGINE=sqlite
export DB_NAME="${DB_PATH}"
export DJANGO_DEBUG=true
export DJANGO_ALLOWED_HOSTS="127.0.0.1,localhost"
export DJANGO_CORS_ALLOW_ALL=true
export CELERY_TASK_ALWAYS_EAGER=true
export EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"

cd "${BACKEND_DIR}"
uv run manage.py migrate --noinput
uv run manage.py bootstrap_system \
  --username admin \
  --password Admin12345 \
  --real-name 系统管理员 \
  --account-file "${ACCOUNT_FILE}"
exec uv run manage.py runserver 127.0.0.1:8001
