#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "${SCRIPT_DIR}/common.sh"

HEALTH_URL="${ASD_MONITOR_HEALTH_URL:-http://127.0.0.1:8000/api/v1/system/health/detail/}"
ALERT_WEBHOOK_URL=""
ALERT_EMAIL=""
BACKEND_ENV_FILE="${ASD_MONITOR_BACKEND_ENV_FILE:-${DEFAULT_ENV_FILE}}"
MONITOR_REDIS_HOST=""
MONITOR_REDIS_PORT=""
CHECK_REDIS=true
CHECK_WORKER=true
CHECK_BEAT=true
TEST_ALERT=false
ALERT_SUBJECT="ASDSystem 服务巡检测试"
ALERT_MESSAGE=""
CONFIG_LOADED=false
declare -a WEBHOOK_HEADERS=()

usage() {
  cat <<'EOF'
用法：
  ./ops/monitor_services.sh [--health-url URL] [--webhook URL] [--email EMAIL]
                             [--backend-env FILE] [--webhook-header KEY:VALUE]
                             [--subject TEXT] [--message TEXT] [--test-alert]
                             [--skip-redis] [--skip-worker] [--skip-beat]

说明：
  1. 默认检查后端详细健康接口、Redis 端口、Celery Worker、Celery Beat。
  2. 当后端状态不是 ok，或本地依赖服务未运行时，脚本会返回非 0。
  3. 若设置告警 Webhook 或告警邮箱，会在失败时自动尝试发送通知。
  4. 使用 --test-alert 可主动验证真实 Webhook 和 SMTP 邮件链路。
EOF
}

port_is_open() {
  local host="$1"
  local port="$2"
  (echo >"/dev/tcp/${host}/${port}") >/dev/null 2>&1
}

load_monitor_config() {
  if [[ "${CONFIG_LOADED}" == "true" ]]; then
    return
  fi

  if [[ -f "${BACKEND_ENV_FILE}" ]]; then
    load_backend_env "${BACKEND_ENV_FILE}"
  fi

  if [[ -z "${ALERT_WEBHOOK_URL}" ]]; then
    ALERT_WEBHOOK_URL="${ASD_ALERT_WEBHOOK_URL:-}"
  fi
  if [[ -z "${ALERT_EMAIL}" ]]; then
    ALERT_EMAIL="${ASD_ALERT_EMAIL:-}"
  fi
  if [[ -z "${MONITOR_REDIS_HOST}" ]]; then
    MONITOR_REDIS_HOST="${REDIS_HOST:-127.0.0.1}"
  fi
  if [[ -z "${MONITOR_REDIS_PORT}" ]]; then
    MONITOR_REDIS_PORT="${REDIS_PORT:-6379}"
  fi
  if [[ -z "${ALERT_MESSAGE}" ]]; then
    ALERT_MESSAGE="这是一条 ASDSystem 主动巡检告警验证消息，发送时间：$(date '+%Y-%m-%d %H:%M:%S')"
  fi

  CONFIG_LOADED=true
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

  local curl_args=(
    --silent
    --show-error
    --fail
    -H "Content-Type: application/json"
  )
  local header
  for header in "${WEBHOOK_HEADERS[@]}"; do
    curl_args+=(-H "${header}")
  done

  curl "${curl_args[@]}" -d "${payload}" "${ALERT_WEBHOOK_URL}" >/dev/null
}

send_email_alert() {
  local title="$1"
  local message="$2"

  if [[ -z "${ALERT_EMAIL}" ]]; then
    return 0
  fi

  if [[ "${EMAIL_BACKEND:-}" != "django.core.mail.backends.smtp.EmailBackend" ]]; then
    echo "当前 EMAIL_BACKEND=${EMAIL_BACKEND:-未配置}，不是 SMTP 邮件后端，跳过邮件告警发送。"
    return 1
  fi

  python3 - "${title}" "${message}" "${ALERT_EMAIL}" <<'PY'
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage

title = sys.argv[1]
message = sys.argv[2]
receiver_emails = [item.strip() for item in sys.argv[3].split(",") if item.strip()]

host = os.environ.get("EMAIL_HOST", "").strip()
port = int(os.environ.get("EMAIL_PORT", "25").strip() or "25")
username = os.environ.get("EMAIL_HOST_USER", "").strip()
password = os.environ.get("EMAIL_HOST_PASSWORD", "").strip()
from_email = os.environ.get("DEFAULT_FROM_EMAIL", "").strip() or username
use_tls = os.environ.get("EMAIL_USE_TLS", "").strip().lower() in {"1", "true", "yes", "on"}
use_ssl = os.environ.get("EMAIL_USE_SSL", "").strip().lower() in {"1", "true", "yes", "on"}

if not host:
    raise SystemExit("未配置 EMAIL_HOST。")
if not from_email:
    raise SystemExit("未配置 DEFAULT_FROM_EMAIL。")
if not receiver_emails:
    raise SystemExit("未配置告警接收邮箱。")
if use_tls and use_ssl:
    raise SystemExit("EMAIL_USE_TLS 与 EMAIL_USE_SSL 不能同时启用。")

email = EmailMessage()
email["Subject"] = title
email["From"] = from_email
email["To"] = ", ".join(receiver_emails)
email.set_content(message)

smtp_timeout = 10
context = ssl.create_default_context()

if use_ssl:
    with smtplib.SMTP_SSL(host, port, timeout=smtp_timeout, context=context) as server:
        if username:
            server.login(username, password)
        server.send_message(email)
else:
    with smtplib.SMTP(host, port, timeout=smtp_timeout) as server:
        if use_tls:
            server.starttls(context=context)
        if username:
            server.login(username, password)
        server.send_message(email)
PY
}

run_test_alert() {
  local has_channel=0
  local has_failure=0

  echo "开始执行主动告警联调验证。"

  if [[ -n "${ALERT_WEBHOOK_URL}" ]]; then
    has_channel=1
    if send_webhook_alert "${ALERT_SUBJECT}" "${ALERT_MESSAGE}"; then
      echo "Webhook 测试发送成功。"
    else
      echo "Webhook 测试发送失败。"
      has_failure=1
    fi
  fi

  if [[ -n "${ALERT_EMAIL}" ]]; then
    has_channel=1
    if send_email_alert "${ALERT_SUBJECT}" "${ALERT_MESSAGE}"; then
      echo "SMTP 邮件测试发送成功。"
    else
      echo "SMTP 邮件测试发送失败。"
      has_failure=1
    fi
  fi

  if [[ "${has_channel}" -eq 0 ]]; then
    echo "未配置告警 Webhook 或告警邮箱，无法执行主动联调验证。"
    return 1
  fi

  if [[ "${has_failure}" -ne 0 ]]; then
    return 1
  fi

  echo "主动告警联调验证完成。"
  return 0
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
      --backend-env)
        BACKEND_ENV_FILE="$2"
        shift 2
        ;;
      --webhook-header)
        WEBHOOK_HEADERS+=("$2")
        shift 2
        ;;
      --subject)
        ALERT_SUBJECT="$2"
        shift 2
        ;;
      --message)
        ALERT_MESSAGE="$2"
        shift 2
        ;;
      --test-alert)
        TEST_ALERT=true
        shift
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
  load_monitor_config

  if [[ "${TEST_ALERT}" == "true" ]]; then
    run_test_alert
    return $?
  fi

  local alerts=()
  local health_response
  local overall_status="unknown"
  local detail_lines=()

  if health_response="$(curl --silent --show-error --fail --max-time 5 "${HEALTH_URL}")"; then
    if mapfile -t detail_lines < <(printf '%s' "${health_response}" | python3 -c '
import json
import sys

payload = json.load(sys.stdin)
data = payload.get("data") or {}
print(data.get("status", "unknown"))

for check_name, check_data in (data.get("checks") or {}).items():
    status = check_data.get("status", "unknown")
    message = check_data.get("message", "")
    print(f"{check_name}: {status} - {message}")
'); then
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

  if ${CHECK_REDIS} && ! port_is_open "${MONITOR_REDIS_HOST}" "${MONITOR_REDIS_PORT}"; then
    alerts+=("Redis 端口不可达：${MONITOR_REDIS_HOST}:${MONITOR_REDIS_PORT}")
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
