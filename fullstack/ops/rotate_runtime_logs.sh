#!/usr/bin/env bash

set -euo pipefail

FULLSTACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-all}"
MAX_SIZE_MB="${ASD_LOG_MAX_SIZE_MB:-20}"
BACKUP_COUNT="${ASD_LOG_BACKUP_COUNT:-7}"
MAX_SIZE_BYTES=$((MAX_SIZE_MB * 1024 * 1024))
ROTATED_COUNT=0

TARGET_DIRS=(
  "${FULLSTACK_DIR}/runtime/services/logs"
  "${FULLSTACK_DIR}/backend/logs"
)

usage() {
  cat <<'EOF'
用法：
  ./ops/rotate_runtime_logs.sh [all|backend|worker|beat]

说明：
  1. 默认同时检查 runtime/services/logs 和 backend/logs。
  2. 单个日志文件超过 ASD_LOG_MAX_SIZE_MB 后会按 .1 ~ .N 方式轮转。
  3. 默认保留 ASD_LOG_BACKUP_COUNT=7 份历史日志。
EOF
}

matches_target() {
  local file_name="$1"

  case "${TARGET}" in
    all)
      return 0
      ;;
    backend)
      [[ "${file_name}" == "backend.log" || "${file_name}" == "backend-error.log" ]]
      ;;
    worker)
      [[ "${file_name}" == "worker.log" ]]
      ;;
    beat)
      [[ "${file_name}" == "beat.log" ]]
      ;;
    help|-h|--help)
      usage
      exit 0
      ;;
    *)
      echo "不支持的轮转目标：${TARGET}"
      usage
      exit 1
      ;;
  esac
}

rotate_log_file() {
  local log_file="$1"
  local file_size
  file_size="$(wc -c < "${log_file}")"

  if (( file_size < MAX_SIZE_BYTES )); then
    return 0
  fi

  rm -f "${log_file}.${BACKUP_COUNT}"
  for ((index = BACKUP_COUNT - 1; index >= 1; index--)); do
    if [[ -f "${log_file}.${index}" ]]; then
      mv "${log_file}.${index}" "${log_file}.$((index + 1))"
    fi
  done

  mv "${log_file}" "${log_file}.1"
  : > "${log_file}"
  ROTATED_COUNT=$((ROTATED_COUNT + 1))
  echo "已轮转日志：${log_file}"
}

main() {
  for directory in "${TARGET_DIRS[@]}"; do
    if [[ ! -d "${directory}" ]]; then
      continue
    fi

    while IFS= read -r log_file; do
      local_name="$(basename "${log_file}")"
      if matches_target "${local_name}"; then
        rotate_log_file "${log_file}"
      fi
    done < <(find "${directory}" -maxdepth 1 -type f -name "*.log" | sort)
  done

  if (( ROTATED_COUNT == 0 )); then
    echo "本次未发现需要轮转的日志文件。"
    return 0
  fi

  echo "日志轮转完成，共处理 ${ROTATED_COUNT} 个文件。"
}

main
