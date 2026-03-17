#!/usr/bin/env sh

set -eu

cd /app

python scripts/wait_for_services.py 180 mysql:3306 redis:6379

ADMIN_PASSWORD="${ASD_ADMIN_PASSWORD:-Admin12345}"

should_init_demo_data() {
  case "${ASD_INIT_DEMO_DATA:-false}" in
    1|true|TRUE|True|yes|YES|Yes|y|Y)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

uv run manage.py migrate --noinput
uv run manage.py collectstatic --noinput

uv run manage.py bootstrap_system \
  --username "${ASD_ADMIN_USERNAME:-admin}" \
  --password "${ADMIN_PASSWORD}" \
  --real-name "${ASD_ADMIN_REAL_NAME:-系统管理员}" \
  --dept-code "${ASD_ROOT_DEPT_CODE:-ROOT}" \
  --dept-name "${ASD_ROOT_DEPT_NAME:-总部}" \
  --account-file "/deployment_runtime/accounts.md"

if should_init_demo_data; then
  echo "检测到 ASD_INIT_DEMO_DATA=${ASD_INIT_DEMO_DATA}，开始初始化示例数据。"
  uv run manage.py bootstrap_demo_data \
    --admin-username "${ASD_ADMIN_USERNAME:-admin}"
else
  echo "未启用示例数据初始化，仅保留基础账号与系统数据。"
fi
