#!/usr/bin/env sh

set -eu

cd /app

python scripts/wait_for_services.py 180 mysql:3306 redis:6379

ADMIN_PASSWORD="${ASD_ADMIN_PASSWORD:-}"
if [ -z "${ADMIN_PASSWORD}" ]; then
  # 未显式传入管理员密码时自动生成一次性密码，并写入账号清单文件。
  ADMIN_PASSWORD="$(python - <<'PY'
import secrets
import string

alphabet = string.ascii_letters + string.digits
password = "".join(secrets.choice(alphabet) for _ in range(16))
print(password)
PY
)"
fi

uv run manage.py migrate --noinput

uv run manage.py bootstrap_system \
  --username "${ASD_ADMIN_USERNAME:-admin}" \
  --password "${ADMIN_PASSWORD}" \
  --real-name "${ASD_ADMIN_REAL_NAME:-系统管理员}" \
  --dept-code "${ASD_ROOT_DEPT_CODE:-ROOT}" \
  --dept-name "${ASD_ROOT_DEPT_NAME:-总部}" \
  --account-file "/deployment_runtime/accounts.md"
