#!/usr/bin/env bash

set -euo pipefail

FULLSTACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${FULLSTACK_DIR}/backend"
DOCKER_DIR="${FULLSTACK_DIR}/docker"
COMPOSE_FILE="${DOCKER_DIR}/docker-compose.yaml"
RUNTIME_DIR="${FULLSTACK_DIR}/runtime/services"
PID_DIR="${RUNTIME_DIR}/pids"
LOG_DIR="${RUNTIME_DIR}/logs"

BACKEND_HOST="127.0.0.1"
BACKEND_PORT="8000"
REDIS_HOST="127.0.0.1"
REDIS_PORT="6379"
BACKEND_HEALTH_URL="http://${BACKEND_HOST}:${BACKEND_PORT}/api/v1/system/health/"
CELERY_APP="config.celery:app"

BACKEND_PID_FILE="${PID_DIR}/backend.pid"
WORKER_PID_FILE="${PID_DIR}/worker.pid"
BEAT_PID_FILE="${PID_DIR}/beat.pid"
REDIS_MARKER_FILE="${PID_DIR}/redis.managed"

usage() {
  cat <<'EOF'
用法：
  ./scripts/manage_services.sh start [all|redis|backend|worker|beat]
  ./scripts/manage_services.sh stop [all|redis|backend|worker|beat]
  ./scripts/manage_services.sh restart [all|redis|backend|worker|beat]
  ./scripts/manage_services.sh status
  ./scripts/manage_services.sh logs <backend|worker|beat|redis>

说明：
  1. start 默认按 all 处理，会检查 Redis、后端、Celery Worker、Celery Beat。
  2. stop 只停止脚本自己拉起的进程，不会终止外部已存在的服务。
  3. status 会区分“脚本管理中”与“外部已运行”两种状态。
EOF
}

ensure_runtime_dirs() {
  mkdir -p "${PID_DIR}" "${LOG_DIR}"
}

require_command() {
  local command_name="$1"
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "未找到命令：${command_name}"
    exit 1
  fi
}

port_is_open() {
  local host="$1"
  local port="$2"
  (echo >"/dev/tcp/${host}/${port}") >/dev/null 2>&1
}

read_pid() {
  local pid_file="$1"
  if [[ -f "${pid_file}" ]]; then
    tr -d '[:space:]' < "${pid_file}"
  fi
}

is_pid_running() {
  local pid="${1:-}"
  [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1
}

cleanup_stale_pid() {
  local pid_file="$1"
  local pid
  pid="$(read_pid "${pid_file}")"
  if [[ -n "${pid}" ]] && ! is_pid_running "${pid}"; then
    rm -f "${pid_file}"
  fi
}

wait_for_port() {
  local host="$1"
  local port="$2"
  local retries="${3:-20}"
  local delay_seconds="${4:-1}"

  local attempt=1
  while (( attempt <= retries )); do
    if port_is_open "${host}" "${port}"; then
      return 0
    fi
    sleep "${delay_seconds}"
    attempt=$((attempt + 1))
  done

  return 1
}

wait_for_http() {
  local url="$1"
  local retries="${2:-30}"
  local delay_seconds="${3:-1}"

  local attempt=1
  while (( attempt <= retries )); do
    if curl --silent --fail "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep "${delay_seconds}"
    attempt=$((attempt + 1))
  done

  return 1
}

external_process_line() {
  local service_name="$1"

  if ! command -v pgrep >/dev/null 2>&1; then
    return 0
  fi

  case "${service_name}" in
    backend)
      pgrep -af "manage.py runserver .*:${BACKEND_PORT}" | head -n 1 || true
      ;;
    worker)
      pgrep -af "celery .* worker" | head -n 1 || true
      ;;
    beat)
      pgrep -af "celery .* beat" | head -n 1 || true
      ;;
    *)
      true
      ;;
  esac
}

service_log_file() {
  local service_name="$1"
  echo "${LOG_DIR}/${service_name}.log"
}

start_background_service() {
  local service_name="$1"
  local pid_file="$2"
  local command_text="$3"
  local log_file
  log_file="$(service_log_file "${service_name}")"

  cleanup_stale_pid "${pid_file}"

  local pid
  pid="$(read_pid "${pid_file}")"
  if is_pid_running "${pid}"; then
    echo "${service_name} 已由脚本管理并处于运行中，PID=${pid}"
    return 0
  fi

  local external_line
  external_line="$(external_process_line "${service_name}")"
  if [[ -n "${external_line}" ]]; then
    echo "检测到外部 ${service_name} 进程已运行，脚本不重复拉起：${external_line}"
    return 0
  fi

  echo "正在启动 ${service_name} ..."
  # 使用 setsid + nohup 脱离当前终端，避免父进程结束时子进程被一并回收。
  if command -v setsid >/dev/null 2>&1; then
    setsid nohup bash -lc "${command_text}" </dev/null >>"${log_file}" 2>&1 &
  else
    nohup bash -lc "${command_text}" </dev/null >>"${log_file}" 2>&1 &
  fi
  pid=$!
  echo "${pid}" > "${pid_file}"
}

start_redis() {
  ensure_runtime_dirs

  if port_is_open "${REDIS_HOST}" "${REDIS_PORT}"; then
    if [[ -f "${REDIS_MARKER_FILE}" ]]; then
      echo "Redis 已由脚本拉起并处于运行中。"
    else
      echo "检测到外部 Redis 已运行，地址：${REDIS_HOST}:${REDIS_PORT}"
    fi
    return 0
  fi

  require_command docker
  if [[ ! -f "${COMPOSE_FILE}" ]]; then
    echo "未找到 Docker Compose 文件：${COMPOSE_FILE}"
    exit 1
  fi

  echo "Redis 未运行，正在通过 Docker Compose 启动 ..."
  (
    cd "${DOCKER_DIR}" &&
    docker compose -f "${COMPOSE_FILE}" up -d redis
  )

  if ! wait_for_port "${REDIS_HOST}" "${REDIS_PORT}" 30 1; then
    echo "Redis 启动超时，请检查 Docker 容器日志。"
    exit 1
  fi

  echo "managed" > "${REDIS_MARKER_FILE}"
  echo "Redis 已启动，地址：${REDIS_HOST}:${REDIS_PORT}"
}

start_backend() {
  ensure_runtime_dirs
  require_command uv

  cleanup_stale_pid "${BACKEND_PID_FILE}"

  local pid
  pid="$(read_pid "${BACKEND_PID_FILE}")"
  if is_pid_running "${pid}"; then
    echo "后端服务已由脚本管理并处于运行中，PID=${pid}"
    return 0
  fi

  if port_is_open "${BACKEND_HOST}" "${BACKEND_PORT}"; then
    echo "检测到 ${BACKEND_PORT} 端口已有后端服务，默认视为外部服务并跳过启动。"
    return 0
  fi

  start_background_service \
    "backend" \
    "${BACKEND_PID_FILE}" \
    "cd '${BACKEND_DIR}' && exec uv run manage.py runserver 0.0.0.0:${BACKEND_PORT}"

  pid="$(read_pid "${BACKEND_PID_FILE}")"
  if ! is_pid_running "${pid}"; then
    echo "后端服务启动失败，请查看日志：$(service_log_file backend)"
    exit 1
  fi

  if ! wait_for_http "${BACKEND_HEALTH_URL}" 30 1; then
    echo "后端服务健康检查未通过，请查看日志：$(service_log_file backend)"
    exit 1
  fi

  echo "后端服务已启动，健康地址：${BACKEND_HEALTH_URL}"
}

start_worker() {
  ensure_runtime_dirs
  require_command uv
  start_redis

  start_background_service \
    "worker" \
    "${WORKER_PID_FILE}" \
    "cd '${BACKEND_DIR}' && exec uv run celery -A '${CELERY_APP}' worker --loglevel=info"

  local pid
  pid="$(read_pid "${WORKER_PID_FILE}")"
  sleep 3
  if ! is_pid_running "${pid}"; then
    echo "Celery Worker 启动失败，请查看日志：$(service_log_file worker)"
    exit 1
  fi

  echo "Celery Worker 已启动，PID=${pid}"
}

start_beat() {
  ensure_runtime_dirs
  require_command uv
  start_redis

  start_background_service \
    "beat" \
    "${BEAT_PID_FILE}" \
    "cd '${BACKEND_DIR}' && exec uv run celery -A '${CELERY_APP}' beat --loglevel=info"

  local pid
  pid="$(read_pid "${BEAT_PID_FILE}")"
  sleep 3
  if ! is_pid_running "${pid}"; then
    echo "Celery Beat 启动失败，请查看日志：$(service_log_file beat)"
    exit 1
  fi

  echo "Celery Beat 已启动，PID=${pid}"
}

stop_managed_process() {
  local service_name="$1"
  local pid_file="$2"

  cleanup_stale_pid "${pid_file}"
  local pid
  pid="$(read_pid "${pid_file}")"
  if ! is_pid_running "${pid}"; then
    rm -f "${pid_file}"
    echo "${service_name} 当前没有由脚本管理的运行进程。"
    return 0
  fi

  echo "正在停止 ${service_name}，PID=${pid} ..."
  kill "${pid}" >/dev/null 2>&1 || true

  local attempt=1
  while (( attempt <= 10 )); do
    if ! is_pid_running "${pid}"; then
      rm -f "${pid_file}"
      echo "${service_name} 已停止。"
      return 0
    fi
    sleep 1
    attempt=$((attempt + 1))
  done

  kill -9 "${pid}" >/dev/null 2>&1 || true
  rm -f "${pid_file}"
  echo "${service_name} 已强制停止。"
}

stop_redis() {
  if [[ ! -f "${REDIS_MARKER_FILE}" ]]; then
    echo "Redis 未由脚本拉起，跳过停止。"
    return 0
  fi

  require_command docker
  echo "正在停止脚本拉起的 Redis 容器 ..."
  (
    cd "${DOCKER_DIR}" &&
    docker compose -f "${COMPOSE_FILE}" stop redis
  )
  rm -f "${REDIS_MARKER_FILE}"
  echo "Redis 已停止。"
}

print_status_line() {
  local label="$1"
  local status_text="$2"
  printf '%-14s %s\n' "${label}" "${status_text}"
}

status_backend() {
  cleanup_stale_pid "${BACKEND_PID_FILE}"
  local pid
  pid="$(read_pid "${BACKEND_PID_FILE}")"
  if is_pid_running "${pid}"; then
    print_status_line "backend" "运行中（脚本管理，PID=${pid}）"
    return
  fi

  if port_is_open "${BACKEND_HOST}" "${BACKEND_PORT}"; then
    print_status_line "backend" "运行中（外部服务，占用 ${BACKEND_PORT} 端口）"
    return
  fi

  print_status_line "backend" "未运行"
}

status_worker() {
  cleanup_stale_pid "${WORKER_PID_FILE}"
  local pid
  pid="$(read_pid "${WORKER_PID_FILE}")"
  if is_pid_running "${pid}"; then
    print_status_line "worker" "运行中（脚本管理，PID=${pid}）"
    return
  fi

  local external_line
  external_line="$(external_process_line worker)"
  if [[ -n "${external_line}" ]]; then
    print_status_line "worker" "运行中（外部进程）"
    return
  fi

  print_status_line "worker" "未运行"
}

status_beat() {
  cleanup_stale_pid "${BEAT_PID_FILE}"
  local pid
  pid="$(read_pid "${BEAT_PID_FILE}")"
  if is_pid_running "${pid}"; then
    print_status_line "beat" "运行中（脚本管理，PID=${pid}）"
    return
  fi

  local external_line
  external_line="$(external_process_line beat)"
  if [[ -n "${external_line}" ]]; then
    print_status_line "beat" "运行中（外部进程）"
    return
  fi

  print_status_line "beat" "未运行"
}

status_redis() {
  if port_is_open "${REDIS_HOST}" "${REDIS_PORT}"; then
    if [[ -f "${REDIS_MARKER_FILE}" ]]; then
      print_status_line "redis" "运行中（脚本管理，Docker Compose）"
    else
      print_status_line "redis" "运行中（外部服务，占用 ${REDIS_PORT} 端口）"
    fi
    return
  fi

  print_status_line "redis" "未运行"
}

show_logs() {
  local service_name="$1"

  case "${service_name}" in
    backend|worker|beat)
      local log_file
      log_file="$(service_log_file "${service_name}")"
      if [[ ! -f "${log_file}" ]]; then
        echo "暂无 ${service_name} 日志文件。"
        return 0
      fi
      tail -n 40 "${log_file}"
      ;;
    redis)
      if [[ ! -f "${REDIS_MARKER_FILE}" ]]; then
        echo "Redis 未由脚本拉起，无法统一输出日志。"
        return 0
      fi
      require_command docker
      (
        cd "${DOCKER_DIR}" &&
        docker compose -f "${COMPOSE_FILE}" logs --tail=40 redis
      )
      ;;
    *)
      echo "不支持的日志服务：${service_name}"
      exit 1
      ;;
  esac
}

start_target() {
  local target="${1:-all}"
  case "${target}" in
    all)
      start_redis
      start_backend
      start_worker
      start_beat
      ;;
    redis)
      start_redis
      ;;
    backend)
      start_backend
      ;;
    worker)
      start_worker
      ;;
    beat)
      start_beat
      ;;
    *)
      echo "不支持的启动目标：${target}"
      usage
      exit 1
      ;;
  esac
}

stop_target() {
  local target="${1:-all}"
  case "${target}" in
    all)
      stop_managed_process "Celery Beat" "${BEAT_PID_FILE}"
      stop_managed_process "Celery Worker" "${WORKER_PID_FILE}"
      stop_managed_process "后端服务" "${BACKEND_PID_FILE}"
      stop_redis
      ;;
    redis)
      stop_redis
      ;;
    backend)
      stop_managed_process "后端服务" "${BACKEND_PID_FILE}"
      ;;
    worker)
      stop_managed_process "Celery Worker" "${WORKER_PID_FILE}"
      ;;
    beat)
      stop_managed_process "Celery Beat" "${BEAT_PID_FILE}"
      ;;
    *)
      echo "不支持的停止目标：${target}"
      usage
      exit 1
      ;;
  esac
}

restart_target() {
  local target="${1:-all}"
  stop_target "${target}"
  start_target "${target}"
}

show_status() {
  ensure_runtime_dirs
  status_redis
  status_backend
  status_worker
  status_beat
  echo "日志目录：${LOG_DIR}"
}

main() {
  ensure_runtime_dirs

  local action="${1:-status}"
  local target="${2:-all}"

  case "${action}" in
    start)
      start_target "${target}"
      ;;
    stop)
      stop_target "${target}"
      ;;
    restart)
      restart_target "${target}"
      ;;
    status)
      show_status
      ;;
    logs)
      if [[ "${target}" == "all" ]]; then
        echo "logs 命令必须指定服务名称。"
        usage
        exit 1
      fi
      show_logs "${target}"
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
