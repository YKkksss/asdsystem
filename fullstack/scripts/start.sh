#!/usr/bin/env bash

set -euo pipefail

FULLSTACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${FULLSTACK_DIR}/frontend"
BACKEND_DIR="${FULLSTACK_DIR}/backend"
CELERY_APP="config.celery:app"

print_menu() {
  cat >&2 <<'EOF'
请选择要启动的服务：
1. 启动前端开发服务
2. 启动后端开发服务
3. 启动 Celery Worker
4. 启动 Celery Beat
EOF
}

check_command() {
  local command_name="$1"

  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "未找到命令：${command_name}，请先安装对应运行环境。"
    exit 1
  fi
}

start_frontend() {
  check_command npm

  if [ ! -d "${FRONTEND_DIR}" ]; then
    echo "前端目录不存在：${FRONTEND_DIR}"
    exit 1
  fi

  echo "正在启动前端开发服务..."
  echo "目录：${FRONTEND_DIR}"
  echo "本机访问：http://127.0.0.1:5173"
  echo "内网访问：http://服务器内网IP:5173"
  cd "${FRONTEND_DIR}"
  exec npm run dev
}

start_backend() {
  check_command uv

  if [ ! -d "${BACKEND_DIR}" ]; then
    echo "后端目录不存在：${BACKEND_DIR}"
    exit 1
  fi

  echo "正在启动后端开发服务..."
  echo "目录：${BACKEND_DIR}"
  cd "${BACKEND_DIR}"
  exec uv run manage.py runserver 0.0.0.0:8000
}

start_celery_worker() {
  check_command uv

  if [ ! -d "${BACKEND_DIR}" ]; then
    echo "后端目录不存在：${BACKEND_DIR}"
    exit 1
  fi

  echo "正在启动 Celery Worker..."
  echo "目录：${BACKEND_DIR}"
  echo "应用：${CELERY_APP}"
  echo "提示：请先确保 Redis 可用，否则异步任务无法正常消费。"
  cd "${BACKEND_DIR}"
  exec uv run celery -A "${CELERY_APP}" worker --loglevel=info
}

start_celery_beat() {
  check_command uv

  if [ ! -d "${BACKEND_DIR}" ]; then
    echo "后端目录不存在：${BACKEND_DIR}"
    exit 1
  fi

  echo "正在启动 Celery Beat..."
  echo "目录：${BACKEND_DIR}"
  echo "应用：${CELERY_APP}"
  echo "提示：请先确保 Redis 可用，否则定时任务无法正常投递。"
  cd "${BACKEND_DIR}"
  exec uv run celery -A "${CELERY_APP}" beat --loglevel=info
}

resolve_choice() {
  local input_choice="${1:-}"

  if [ -n "${input_choice}" ]; then
    echo "${input_choice}"
    return
  fi

  print_menu
  read -r -p "请输入选项 [1-4]：" input_choice
  echo "${input_choice}"
}

main() {
  local choice
  choice="$(resolve_choice "${1:-}")"
  choice="${choice//[[:space:]]/}"

  case "${choice}" in
    1)
      start_frontend
      ;;
    2)
      start_backend
      ;;
    3)
      start_celery_worker
      ;;
    4)
      start_celery_beat
      ;;
    *)
      echo "无效选项：${choice}，请输入 1、2、3 或 4。"
      exit 1
      ;;
  esac
}

main "${1:-}"
