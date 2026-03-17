#!/usr/bin/env sh

set -eu

cd /app

python scripts/wait_for_services.py 180 mysql:3306 redis:6379

ADMIN_PASSWORD="${ASD_ADMIN_PASSWORD:-Admin12345}"

should_force_bootstrap() {
  case "${ASD_FORCE_BOOTSTRAP:-false}" in
    1|true|TRUE|True|yes|YES|Yes|y|Y)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

check_bootstrap_state() {
  uv run manage.py check_bootstrap_state \
    --username "${ASD_ADMIN_USERNAME:-admin}" \
    --dept-code "${ASD_ROOT_DEPT_CODE:-ROOT}" \
    --account-file "/deployment_runtime/accounts.md"
}

uv run manage.py migrate --noinput
uv run manage.py collectstatic --noinput

BOOTSTRAP_STATE_OUTPUT="$(check_bootstrap_state)"

if should_force_bootstrap || printf '%s\n' "${BOOTSTRAP_STATE_OUTPUT}" | grep -q '^BOOTSTRAP_REQUIRED=true$'; then
  echo "检测到基础系统数据未就绪或需要同步，开始执行基础初始化。"
  printf '%s\n' "${BOOTSTRAP_STATE_OUTPUT}"
  uv run manage.py bootstrap_system \
    --username "${ASD_ADMIN_USERNAME:-admin}" \
    --password "${ADMIN_PASSWORD}" \
    --real-name "${ASD_ADMIN_REAL_NAME:-系统管理员}" \
    --dept-code "${ASD_ROOT_DEPT_CODE:-ROOT}" \
    --dept-name "${ASD_ROOT_DEPT_NAME:-总部}" \
    --account-file "/deployment_runtime/accounts.md" \
    --preserve-existing-passwords
else
  echo "基础系统数据已就绪，跳过基础初始化。"
fi

echo "当前部署流程仅初始化基础账号与系统数据。"
echo "如需补充示例业务数据，请在部署完成后手动执行 scripts/init_demo_data.sh。"
