#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

OUTPUT_ROOT="${ASD_BACKUP_DIR:-${FULLSTACK_DIR}/runtime/backups}"
ENV_FILE="${DEFAULT_ENV_FILE}"
BACKUP_PREFIX="asd-backup"

usage() {
  cat <<'EOF'
用法：
  ./ops/backup_system.sh [--output-dir DIR] [--env-file FILE] [--prefix NAME]

说明：
  1. 默认从 backend/.env 读取数据库与邮件等配置。
  2. SQLite 模式会直接复制数据库文件，MySQL 模式会执行 mysqldump。
  3. 备份产物默认输出到 runtime/backups/ 下的时间戳目录。
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --output-dir)
        OUTPUT_ROOT="$2"
        shift 2
        ;;
      --env-file)
        ENV_FILE="$2"
        shift 2
        ;;
      --prefix)
        BACKUP_PREFIX="$2"
        shift 2
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

backup_database() {
  local backup_dir="$1"
  local manifest_file="$2"
  local db_engine="${DB_ENGINE:-sqlite}"

  case "${db_engine}" in
    sqlite)
      local sqlite_path
      sqlite_path="$(resolve_backend_path "${DB_NAME:-db.sqlite3}")"
      if [[ ! -f "${sqlite_path}" ]]; then
        echo "未找到 SQLite 数据库文件：${sqlite_path}"
        exit 1
      fi
      cp "${sqlite_path}" "${backup_dir}/database.sqlite3"
      echo "BACKUP_DATABASE_FILE=database.sqlite3" >> "${manifest_file}"
      ;;
    mysql)
      require_command mysqldump
      local dump_file="${backup_dir}/database.sql"
      local mysql_args=(
        "--host=${DB_HOST:-127.0.0.1}"
        "--port=${DB_PORT:-3306}"
        "--user=${DB_USER:-root}"
        "--single-transaction"
        "--quick"
        "--routines"
        "--triggers"
      )
      if [[ -n "${DB_PASSWORD:-}" ]]; then
        mysql_args+=("--password=${DB_PASSWORD}")
      fi
      mysqldump "${mysql_args[@]}" "${DB_NAME}" > "${dump_file}"
      echo "BACKUP_DATABASE_FILE=database.sql" >> "${manifest_file}"
      ;;
    *)
      echo "不支持的数据库引擎：${db_engine}"
      exit 1
      ;;
  esac
}

main() {
  parse_args "$@"
  load_backend_env "${ENV_FILE}"

  local resolved_output_root
  resolved_output_root="$(resolve_root_path "${OUTPUT_ROOT}")"
  local timestamp
  timestamp="$(timestamp_utc)"
  local backup_dir="${resolved_output_root}/${BACKUP_PREFIX}-${timestamp}"
  local manifest_file="${backup_dir}/manifest.env"

  mkdir -p "${backup_dir}"

  {
    echo "BACKUP_CREATED_AT=${timestamp}"
    echo "BACKUP_DB_ENGINE=${DB_ENGINE:-sqlite}"
    echo "BACKUP_DB_NAME=${DB_NAME:-db.sqlite3}"
    echo "BACKUP_ENV_FILE=backend.env.backup"
    echo "BACKUP_MEDIA_ARCHIVE=media.tar.gz"
  } > "${manifest_file}"

  backup_database "${backup_dir}" "${manifest_file}"

  if [[ -d "${BACKEND_DIR}/media" ]]; then
    tar -czf "${backup_dir}/media.tar.gz" -C "${BACKEND_DIR}" media
    echo "BACKUP_MEDIA_INCLUDED=true" >> "${manifest_file}"
  else
    echo "BACKUP_MEDIA_INCLUDED=false" >> "${manifest_file}"
  fi

  if [[ -f "${ENV_FILE}" ]]; then
    cp "${ENV_FILE}" "${backup_dir}/backend.env.backup"
    echo "BACKUP_ENV_INCLUDED=true" >> "${manifest_file}"
  else
    echo "BACKUP_ENV_INCLUDED=false" >> "${manifest_file}"
  fi

  if command -v sha256sum >/dev/null 2>&1; then
    (
      cd "${backup_dir}" &&
      sha256sum ./* > SHA256SUMS
    )
  fi

  echo "备份完成：${backup_dir}"
}

main "$@"
