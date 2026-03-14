#!/usr/bin/env bash

set -euo pipefail

FULLSTACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${FULLSTACK_DIR}/backend"
DEFAULT_ENV_FILE="${BACKEND_DIR}/.env"

require_command() {
  local command_name="$1"
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "未找到命令：${command_name}"
    exit 1
  fi
}

load_backend_env() {
  local env_file="${1:-${DEFAULT_ENV_FILE}}"

  if [[ ! -f "${env_file}" ]]; then
    echo "未找到环境变量文件：${env_file}"
    exit 1
  fi

  set -a
  # shellcheck disable=SC1090
  source "${env_file}"
  set +a
}

resolve_backend_path() {
  local raw_path="$1"
  if [[ "${raw_path}" = /* ]]; then
    echo "${raw_path}"
  else
    echo "${BACKEND_DIR}/${raw_path}"
  fi
}

resolve_root_path() {
  local raw_path="$1"
  if [[ "${raw_path}" = /* ]]; then
    echo "${raw_path}"
  else
    echo "${FULLSTACK_DIR}/${raw_path}"
  fi
}

timestamp_utc() {
  date -u +"%Y%m%dT%H%M%SZ"
}
