#!/usr/bin/env bash

set -euo pipefail

FULLSTACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${FULLSTACK_DIR}/backend"
FRONTEND_DIR="${FULLSTACK_DIR}/frontend"
COMPOSE_FILE="${FULLSTACK_DIR}/docker/docker-compose.deploy.yaml"
RUNTIME_DIR="${FULLSTACK_DIR}/runtime/deployment_runtime"
ACCOUNT_FILE="${RUNTIME_DIR}/accounts.md"
DEPLOY_STATE_FILE="${RUNTIME_DIR}/deploy_state.env"
HTTP_PORT="${ASD_HTTP_PORT:-8080}"
FORCE_BUILD="${ASD_FORCE_BUILD:-false}"

BACKEND_IMAGES=("asd-system-backend" "asd-system-backend-init" "asd-system-worker" "asd-system-beat")
FRONTEND_IMAGE="asd-system-frontend"
BUILD_TARGETS=()
BACKEND_CONTEXT_HASH=""
FRONTEND_CONTEXT_HASH=""
SAVED_BACKEND_CONTEXT_HASH=""
SAVED_FRONTEND_CONTEXT_HASH=""

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
  1. 默认执行 up，会自动判断是否需要构建镜像，并启动容器、执行迁移与基础初始化检查。
  2. 首次部署后，账号清单会输出到 runtime/deployment_runtime/accounts.md。
  3. 基础账号初始化只会在首次部署或基础数据缺失时自动执行，重复部署默认保留已有账号密码。
  4. 如需补充演示业务数据，请在部署完成后手动执行 ./scripts/init_demo_data.sh。
  5. 如需自定义端口或管理员账号，可在执行前设置环境变量，例如：
     ASD_HTTP_PORT=8080 ASD_ADMIN_PASSWORD=MyAdmin123 DJANGO_ALLOWED_HOSTS=demo.example.com,127.0.0.1 ./scripts/deploy.sh
  6. 如需强制重新构建本地镜像，可临时附加环境变量：
     ASD_FORCE_BUILD=true ./scripts/deploy.sh
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

is_truthy() {
  case "${1:-false}" in
    1|true|TRUE|True|yes|YES|Yes|y|Y)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

require_hash_tools() {
  require_command tar
  require_command sha256sum
}

compute_context_hash() {
  local base_dir="$1"
  shift

  local include_paths=()
  local relative_path
  for relative_path in "$@"; do
    if [[ -e "${base_dir}/${relative_path}" ]]; then
      include_paths+=("${relative_path}")
    fi
  done

  if [[ "${#include_paths[@]}" -eq 0 ]]; then
    echo ""
    return 0
  fi

  tar \
    --sort=name \
    --mtime='UTC 1970-01-01' \
    --owner=0 \
    --group=0 \
    --numeric-owner \
    -cf - \
    -C "${base_dir}" \
    "${include_paths[@]}" \
    | sha256sum \
    | awk '{print $1}'
}

load_deploy_state() {
  if [[ ! -f "${DEPLOY_STATE_FILE}" ]]; then
    return 0
  fi

  # shellcheck disable=SC1090
  source "${DEPLOY_STATE_FILE}"
}

write_deploy_state() {
  cat > "${DEPLOY_STATE_FILE}" <<EOF
SAVED_BACKEND_CONTEXT_HASH='${BACKEND_CONTEXT_HASH}'
SAVED_FRONTEND_CONTEXT_HASH='${FRONTEND_CONTEXT_HASH}'
EOF
}

image_exists() {
  local image_name="$1"
  docker image inspect "${image_name}:latest" >/dev/null 2>&1
}

calculate_context_hashes() {
  BACKEND_CONTEXT_HASH="$(compute_context_hash \
    "${BACKEND_DIR}" \
    Dockerfile \
    pyproject.toml \
    uv.lock \
    apps \
    config \
    scripts)"

  FRONTEND_CONTEXT_HASH="$(compute_context_hash \
    "${FRONTEND_DIR}" \
    Dockerfile \
    package.json \
    package-lock.json \
    src \
    public \
    nginx \
    vite.config.ts \
    tsconfig.json)"
}

resolve_build_targets() {
  BUILD_TARGETS=()

  if is_truthy "${FORCE_BUILD}"; then
    BUILD_TARGETS=(backend backend-init worker beat frontend)
    return 0
  fi

  local backend_requires_build=0
  local frontend_requires_build=0
  local image_name

  if [[ ! -f "${DEPLOY_STATE_FILE}" ]] || [[ "${BACKEND_CONTEXT_HASH}" != "${SAVED_BACKEND_CONTEXT_HASH:-}" ]]; then
    backend_requires_build=1
  fi
  for image_name in "${BACKEND_IMAGES[@]}"; do
    if ! image_exists "${image_name}"; then
      backend_requires_build=1
      break
    fi
  done

  if [[ ! -f "${DEPLOY_STATE_FILE}" ]] || [[ "${FRONTEND_CONTEXT_HASH}" != "${SAVED_FRONTEND_CONTEXT_HASH:-}" ]]; then
    frontend_requires_build=1
  fi
  if ! image_exists "${FRONTEND_IMAGE}"; then
    frontend_requires_build=1
  fi

  if [[ "${backend_requires_build}" -eq 1 ]]; then
    BUILD_TARGETS+=(backend backend-init worker beat)
  fi
  if [[ "${frontend_requires_build}" -eq 1 ]]; then
    BUILD_TARGETS+=(frontend)
  fi
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
  require_hash_tools
  load_deploy_state
  calculate_context_hashes
  resolve_build_targets

  echo "正在执行一键部署..."
  (
    cd "${FULLSTACK_DIR}" || exit 1

    if [[ "${#BUILD_TARGETS[@]}" -gt 0 ]]; then
      if is_truthy "${FORCE_BUILD}"; then
        echo "已启用强制构建，开始重新构建全部本地镜像..."
      else
        echo "检测到以下服务镜像需要重新构建：${BUILD_TARGETS[*]}"
      fi
      docker compose -f "${COMPOSE_FILE}" build "${BUILD_TARGETS[@]}"
    else
      echo "未检测到源码或镜像变化，直接复用现有镜像启动服务。"
    fi

    docker compose -f "${COMPOSE_FILE}" up -d
  )

  echo "正在等待前后端服务就绪..."
  if ! wait_for_deployment; then
    echo "部署后健康检查超时，请执行以下命令查看日志："
    echo "  ./scripts/deploy.sh logs backend-init"
    echo "  ./scripts/deploy.sh logs backend"
    exit 1
  fi

  write_deploy_state

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
