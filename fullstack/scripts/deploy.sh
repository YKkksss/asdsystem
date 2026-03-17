#!/usr/bin/env bash

set -euo pipefail

FULLSTACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${FULLSTACK_DIR}/docker/docker-compose.deploy.yaml"
RUNTIME_DIR="${FULLSTACK_DIR}/runtime/deployment_runtime"
ACCOUNT_FILE="${RUNTIME_DIR}/accounts.md"
HTTP_PORT="${ASD_HTTP_PORT:-8080}"

usage() {
  cat <<'EOF'
用法：
  ./scripts/deploy.sh
  ./scripts/deploy.sh up
  ./scripts/deploy.sh down
  ./scripts/deploy.sh restart
  ./scripts/deploy.sh status
  ./scripts/deploy.sh logs [service]

说明：
  1. 默认执行 up，会自动构建镜像、启动容器、执行迁移并初始化基础账号。
  2. 首次部署后，账号清单会输出到 runtime/deployment_runtime/accounts.md。
  3. 如需自定义端口或管理员账号，可在执行前设置环境变量，例如：
     ASD_HTTP_PORT=8080 ASD_ADMIN_PASSWORD=MyAdmin123 DJANGO_ALLOWED_HOSTS=demo.example.com,127.0.0.1 ./scripts/deploy.sh
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
    echo "当前 Docker 未安装 Compose 插件，无法执行一键部署。"
    exit 1
  fi
}

ensure_runtime_dirs() {
  mkdir -p "${RUNTIME_DIR}"
}

wait_for_deployment() {
  local max_attempts=120
  local attempt=1
  local frontend_url="http://127.0.0.1:${HTTP_PORT}"
  local backend_url="${frontend_url}/api/v1/system/health/"

  while (( attempt <= max_attempts )); do
    if curl --silent --fail "${frontend_url}" >/dev/null 2>&1 && curl --silent --fail "${backend_url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
    attempt=$((attempt + 1))
  done

  return 1
}

show_accounts() {
  if [[ -f "${ACCOUNT_FILE}" ]]; then
    echo
    echo "初始化账号清单：${ACCOUNT_FILE}"
    sed -n '1,120p' "${ACCOUNT_FILE}"
    return
  fi

  echo
  echo "未检测到账号清单文件，请优先查看 backend-init 日志或重新执行部署。"
  echo "管理员：admin / ${ASD_ADMIN_PASSWORD:-Admin12345}"
  echo "档案员：archivist / Archivist12345"
  echo "借阅人：borrower / Borrower12345"
  echo "审计员：auditor / Auditor12345"
}

up() {
  ensure_runtime_dirs
  require_docker_compose
  require_command curl

  echo "正在执行一键部署..."
  (
    # 当前阶段先固定关闭示例业务数据初始化，避免更新部署时覆盖已有演示数据。
    export ASD_INIT_DEMO_DATA="false"
    cd "${FULLSTACK_DIR}" &&
    docker compose -f "${COMPOSE_FILE}" up -d --build
  )

  echo "正在等待前后端服务就绪..."
  if ! wait_for_deployment; then
    echo "部署后健康检查超时，请执行以下命令查看日志："
    echo "  ./scripts/deploy.sh logs backend-init"
    echo "  ./scripts/deploy.sh logs backend"
    exit 1
  fi

  echo "一键部署完成。"
  echo "前端地址：http://127.0.0.1:${HTTP_PORT}"
  echo "其他设备访问：http://服务器IP或域名:${HTTP_PORT}"
  echo "后端健康检查：http://127.0.0.1:${HTTP_PORT}/api/v1/system/health/"
  show_accounts
}

down() {
  require_docker_compose
  (
    cd "${FULLSTACK_DIR}" &&
    docker compose -f "${COMPOSE_FILE}" down
  )
}

restart() {
  down
  up
}

status() {
  require_docker_compose
  (
    cd "${FULLSTACK_DIR}" &&
    docker compose -f "${COMPOSE_FILE}" ps
  )
}

logs() {
  require_docker_compose
  local service_name="${1:-}"
  if [[ -n "${service_name}" ]]; then
    (
      cd "${FULLSTACK_DIR}" &&
      docker compose -f "${COMPOSE_FILE}" logs --tail=200 "${service_name}"
    )
    return
  fi

  (
    cd "${FULLSTACK_DIR}" &&
    docker compose -f "${COMPOSE_FILE}" logs --tail=200
  )
}

main() {
  local action="${1:-up}"
  local service_name="${2:-}"

  case "${action}" in
    up)
      up
      ;;
    down)
      down
      ;;
    restart)
      restart
      ;;
    status)
      status
      ;;
    logs)
      logs "${service_name}"
      ;;
    help|-h|--help)
      usage
      ;;
    *)
      echo "不支持的操作：${action}"
      usage
      exit 1
      ;;
  esac
}

main "${1:-}" "${2:-}"
