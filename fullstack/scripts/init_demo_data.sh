#!/usr/bin/env bash

set -euo pipefail

FULLSTACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${FULLSTACK_DIR}/backend"
COMPOSE_FILE="${FULLSTACK_DIR}/docker/docker-compose.deploy.yaml"

MODE="${1:-docker}"
ADMIN_USERNAME="${ASD_ADMIN_USERNAME:-admin}"
ARCHIVIST_USERNAME="${ASD_ARCHIVIST_USERNAME:-archivist}"
BORROWER_USERNAME="${ASD_BORROWER_USERNAME:-borrower}"
AUDITOR_USERNAME="${ASD_AUDITOR_USERNAME:-auditor}"

usage() {
  cat <<'EOF'
用法：
  ./scripts/init_demo_data.sh
  ./scripts/init_demo_data.sh docker
  ./scripts/init_demo_data.sh local

说明：
  1. 默认使用 docker 模式，在已部署的容器环境中执行示例数据初始化。
  2. local 模式用于本地后端开发环境，会直接进入 backend/ 执行 manage.py 命令。
  3. 该脚本可重复执行，底层 bootstrap_demo_data 命令具备幂等性。
  4. 执行前请先确保基础账号已经初始化完成。
EOF
}

require_command() {
  local command_name="$1"
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "未找到命令：${command_name}"
    exit 1
  fi
}

require_docker_compose() {
  require_command docker
  if ! docker compose version >/dev/null 2>&1; then
    echo "当前 Docker 未安装 Compose 插件，无法在容器环境中初始化示例数据。"
    exit 1
  fi
}

build_bootstrap_args() {
  DEMO_ARGS=(
    "bootstrap_demo_data"
    "--admin-username" "${ADMIN_USERNAME}"
    "--archivist-username" "${ARCHIVIST_USERNAME}"
    "--borrower-username" "${BORROWER_USERNAME}"
    "--auditor-username" "${AUDITOR_USERNAME}"
  )
}

run_in_docker() {
  require_docker_compose
  build_bootstrap_args

  if ! (
    cd "${FULLSTACK_DIR}" &&
    docker compose -f "${COMPOSE_FILE}" ps --status running backend | grep -q "backend"
  ); then
    echo "未检测到正在运行的 backend 服务，请先执行 ./scripts/deploy.sh 完成部署。"
    exit 1
  fi

  echo "正在容器环境中初始化示例业务数据..."
  (
    cd "${FULLSTACK_DIR}" &&
    docker compose -f "${COMPOSE_FILE}" exec -T backend uv run manage.py "${DEMO_ARGS[@]}"
  )
}

run_in_local() {
  require_command uv
  build_bootstrap_args

  echo "正在本地后端环境中初始化示例业务数据..."
  (
    cd "${BACKEND_DIR}" &&
    uv run manage.py "${DEMO_ARGS[@]}"
  )
}

main() {
  case "${MODE}" in
    docker)
      run_in_docker
      ;;
    local)
      run_in_local
      ;;
    help|-h|--help)
      usage
      return 0
      ;;
    *)
      echo "不支持的模式：${MODE}"
      usage
      exit 1
      ;;
  esac

  echo "示例业务数据初始化完成。"
}

main
