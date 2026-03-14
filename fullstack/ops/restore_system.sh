#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

ENV_FILE="${DEFAULT_ENV_FILE}"
RESTORE_ENV=false
CONFIRM_RESTORE=false
BACKUP_DIR=""

usage() {
  cat <<'EOF'
用法：
  ./ops/restore_system.sh --backup-dir DIR [--env-file FILE] [--restore-env] --yes

说明：
  1. 为避免误恢复，必须显式传入 --yes。
  2. 恢复前请先停止后端、Celery Worker、Celery Beat 等写入进程。
  3. SQLite 恢复会覆盖数据库文件，MySQL 恢复会导入 SQL 备份。
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --backup-dir)
        BACKUP_DIR="$2"
        shift 2
        ;;
      --env-file)
        ENV_FILE="$2"
        shift 2
        ;;
      --restore-env)
        RESTORE_ENV=true
        shift
        ;;
      --yes)
        CONFIRM_RESTORE=true
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

restore_database() {
  local backup_dir="$1"
  local timestamp="$2"
  local database_file="${backup_dir}/${BACKUP_DATABASE_FILE}"

  if [[ ! -f "${database_file}" ]]; then
    echo "未找到数据库备份文件：${database_file}"
    exit 1
  fi

  case "${DB_ENGINE:-sqlite}" in
    sqlite)
      local sqlite_path
      sqlite_path="$(resolve_backend_path "${DB_NAME:-db.sqlite3}")"
      mkdir -p "$(dirname "${sqlite_path}")"
      if [[ -f "${sqlite_path}" ]]; then
        mv "${sqlite_path}" "${sqlite_path}.before-restore-${timestamp}"
      fi
      cp "${database_file}" "${sqlite_path}"
      ;;
    mysql)
      require_command mysql
      local mysql_args=(
        "--host=${DB_HOST:-127.0.0.1}"
        "--port=${DB_PORT:-3306}"
        "--user=${DB_USER:-root}"
      )
      if [[ -n "${DB_PASSWORD:-}" ]]; then
        mysql_args+=("--password=${DB_PASSWORD}")
      fi
      mysql "${mysql_args[@]}" "${DB_NAME}" < "${database_file}"
      ;;
    *)
      echo "不支持的数据库引擎：${DB_ENGINE:-unknown}"
      exit 1
      ;;
  esac
}

restore_media() {
  local backup_dir="$1"
  local timestamp="$2"
  local media_archive="${backup_dir}/${BACKUP_MEDIA_ARCHIVE}"

  if [[ ! -f "${media_archive}" ]]; then
    return 0
  fi

  if [[ -d "${BACKEND_DIR}/media" ]]; then
    mv "${BACKEND_DIR}/media" "${BACKEND_DIR}/media.before-restore-${timestamp}"
  fi

  tar -xzf "${media_archive}" -C "${BACKEND_DIR}"
}

restore_env_file() {
  local backup_dir="$1"
  local env_backup_file="${backup_dir}/${BACKUP_ENV_FILE}"

  if [[ ! -f "${env_backup_file}" ]]; then
    echo "备份中未包含环境变量文件，跳过恢复。"
    return 0
  fi

  cp "${env_backup_file}" "${ENV_FILE}"
}

main() {
  parse_args "$@"

  if [[ -z "${BACKUP_DIR}" ]]; then
    echo "必须指定 --backup-dir。"
    usage
    exit 1
  fi

  if [[ "${CONFIRM_RESTORE}" != true ]]; then
    echo "恢复操作具有覆盖风险，请追加 --yes 后再执行。"
    exit 1
  fi

  BACKUP_DIR="$(resolve_root_path "${BACKUP_DIR}")"
  local manifest_file="${BACKUP_DIR}/manifest.env"
  if [[ ! -f "${manifest_file}" ]]; then
    echo "未找到备份清单文件：${manifest_file}"
    exit 1
  fi

  load_backend_env "${ENV_FILE}"
  # shellcheck disable=SC1090
  source "${manifest_file}"

  if [[ "${DB_ENGINE:-sqlite}" != "${BACKUP_DB_ENGINE:-sqlite}" ]]; then
    echo "当前环境数据库引擎与备份不一致：当前=${DB_ENGINE:-sqlite}，备份=${BACKUP_DB_ENGINE:-sqlite}"
    exit 1
  fi

  local timestamp
  timestamp="$(timestamp_utc)"

  restore_database "${BACKUP_DIR}" "${timestamp}"
  restore_media "${BACKUP_DIR}" "${timestamp}"

  if [[ "${RESTORE_ENV}" == true ]]; then
    restore_env_file "${BACKUP_DIR}"
  fi

  echo "恢复完成，备份目录：${BACKUP_DIR}"
}

main "$@"
