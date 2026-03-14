#!/usr/bin/env bash

set -euo pipefail

FULLSTACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HEALTH_URL="${ASD_MONITOR_HEALTH_URL:-http://127.0.0.1:8000/api/v1/system/health/detail/}"
ALERT_WEBHOOK_URL="${ASD_ALERT_WEBHOOK_URL:-}"
ALERT_EMAIL="${ASD_ALERT_EMAIL:-}"
REDIS_HOST="${REDIS_HOST:-127.0.0.1}"
REDIS_PORT="${REDIS_PORT:-6379}"
CHECK_REDIS=true
CHECK_WORKER=true
CHECK_BEAT=true

usage() {
  cat <<'EOF'
用法：
  ./ops/monitor_services.sh [--health-url URL] [--webhook URL] [--email EMAIL]
                             [--skip-redis] [--skip-worker] [--skip-beat]

说明：
  1. 默认检查后端详细健康接口、Redis 端口、Celery Worker、Celery Beat。
  2. 当后端状态不是 ok，或本地依赖服务未运行时，脚本会返回非 0。
  3. 若设置告警 Webhook 或告警邮箱，会在失败时自动尝试发送通知。
EOF
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

send_webhook_alert() {
  local title="$1"
  local message="$2"

  if [[ -z "${ALERT_WEBHOOK_URL}" ]]; then
    return 0
  fi

  local payload
  payload="$(python3 - "${title}" "${message}" <<'PY'
import json
import sys

title = sys.argv[1]
message = sys.argv[2]
print(json.dumps({"title": title, "message": message}, ensure_ascii=False))
PY
)"

  curl --silent --show-error --fail \
    -H "Content-Type: application/json" \
    -d "${payload}" \
    "${ALERT_WEBHOOK_URL}" >/dev/null
}

send_email_alert() {
  local title="$1"
  local message="$2"

  if [[ -z "${ALERT_EMAIL}" ]]; then
    return 0
  fi

  if ! command -v mail >/dev/null 2>&1; then
    echo "未找到 mail 命令，跳过邮件告警发送。"
    return 0
  fi

  printf '%s\n' "${message}" | mail -s "${title}" "${ALERT_EMAIL}"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --health-url)
        HEALTH_URL="$2"
        shift 2
        ;;
      --webhook)
        ALERT_WEBHOOK_URL="$2"
        shift 2
        ;;
      --email)
        ALERT_EMAIL="$2"
        shift 2
        ;;
      --skip-redis)
        CHECK_REDIS=false
        shift
        ;;
      --skip-worker)
        CHECK_WORKER=false
        shift
        ;;
      --skip-beat)
        CHECK_BEAT=false
        shift
        ;;
      help|-h|--help)
        usage
        exit 0
        ;;
      *)
        echo "不支持的参数：$1"
        usage
        exit 1
        ;;
    esac
  done
}

main() {
  require_command curl
  require_command python3

  parse_args "$@"

  local alerts=()
  local health_response
  local overall_status="unknown"
  local detail_lines=()

  if health_response="$(curl --silent --show-error --fail --max-time 5 "${HEALTH_URL}")"; then
    if mapfile -t detail_lines < <(printf '%s' "${health_response}" | python3 - <<'PY'
import json
import sys

payload = json.load(sys.stdin)
data = payload.get("data") or {}
print(data.get("status", "unknown"))

for check_name, check_data in (data.get("checks") or {}).items():
    status = check_data.get("status", "unknown")
    message = check_data.get("message", "")
    print(f"{check_name}: {status} - {message}")
PY
); then
      overall_status="${detail_lines[0]:-unknown}"
      if [[ "${overall_status}" != "ok" ]]; then
        alerts+=("后端详细健康检查状态为 ${overall_status}。")
      fi
    else
      alerts+=("健康检查接口返回内容无法解析。")
    fi
  else
    alerts+=("无法访问后端详细健康接口：${HEALTH_URL}")
  fi

  if ${CHECK_REDIS} && ! port_is_open "${REDIS_HOST}" "${REDIS_PORT}"; then
    alerts+=("Redis 端口不可达：${REDIS_HOST}:${REDIS_PORT}")
  fi

  if ${CHECK_WORKER} && ! pgrep -af "celery .* worker" >/dev/null 2>&1; then
    alerts+=("未检测到 Celery Worker 进程。")
  fi

  if ${CHECK_BEAT} && ! pgrep -af "celery .* beat" >/dev/null 2>&1; then
    alerts+=("未检测到 Celery Beat 进程。")
  fi

  echo "巡检时间：$(date '+%Y-%m-%d %H:%M:%S')"
  echo "健康接口：${HEALTH_URL}"
  if [[ ${#detail_lines[@]} -gt 1 ]]; then
    printf '%s\n' "${detail_lines[@]:1}"
  fi

  if [[ ${#alerts[@]} -eq 0 ]]; then
    echo "巡检通过，当前未发现异常。"
    return 0
  fi

  local alert_title="ASDSystem 服务巡检告警"
  local alert_body
  alert_body="$(printf '%s\n' "${alerts[@]}")"

  echo "巡检失败："
  printf '%s\n' "${alerts[@]}"

  if ! send_webhook_alert "${alert_title}" "${alert_body}"; then
    echo "Webhook 告警发送失败。"
  fi

  if ! send_email_alert "${alert_title}" "${alert_body}"; then
    echo "邮件告警发送失败。"
  fi

  return 1
}

main "$@"
