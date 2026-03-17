#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

trap 'echo "[ERR] line=$LINENO cmd=$BASH_COMMAND" >&2' ERR

FULLSTACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${FULLSTACK_DIR}/backend"
FRONTEND_DIR="${FULLSTACK_DIR}/frontend"
RESULTS_DIR="${FULLSTACK_DIR}/runtime/test_results"
SUMMARY_FILE="${RESULTS_DIR}/summary.log"
TMP_DIR=""
MODE="${1:-all}"

cleanup() {
  if [[ -n "${TMP_DIR}" && -d "${TMP_DIR}" ]]; then
    rm -rf "${TMP_DIR}"
  fi
}

trap cleanup EXIT INT TERM

check_command() {
  local command_name="$1"
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "未找到命令：${command_name}" >&2
    exit 1
  fi
}

prepare_result_dirs() {
  mkdir -p "${RESULTS_DIR}/unit_tests" "${RESULTS_DIR}/API_tests" "${RESULTS_DIR}/e2e_tests"
  TMP_DIR="$(mktemp -d "${RESULTS_DIR}/.run_tmp.XXXXXX")"
  : > "${SUMMARY_FILE}"
}

print_header() {
  local title="$1"
  echo ""
  echo "=============================="
  echo "${title}"
  echo "=============================="
}

count_manifest_cases() {
  local manifest_path="$1"
  awk -F'|' '
    /^[[:space:]]*#/ { next }
    NF < 2 { next }
    $1 ~ /^[[:space:]]*$/ { next }
    { count += 1 }
    END { print count + 0 }
  ' "${manifest_path}"
}

run_django_case() {
  local display_name="$1"
  local test_label="$2"
  local log_file="$3"
  local start_ts elapsed status_code

  start_ts="$(date +%s)"
  echo "[开始] ${display_name}"
  echo "测试标签：${test_label}"
  echo "日志文件：${log_file}"

  set +e
  (
    cd "${BACKEND_DIR}" &&
    uv run manage.py test "${test_label}" --verbosity 2
  ) 2>&1 | tee "${log_file}"
  status_code=${PIPESTATUS[0]}
  set -e

  elapsed="$(( $(date +%s) - start_ts ))"
  echo "耗时：${elapsed}s"

  if [[ "${status_code}" -eq 0 ]]; then
    echo "[成功] ${display_name}"
    return 0
  fi

  echo "[失败] ${display_name}"
  echo "失败原因：Django 测试进程退出码 ${status_code}"
  echo "失败日志摘要："
  tail -n 20 "${log_file}" || true
  return 1
}

run_manifest_suite() {
  local suite_name="$1"
  local manifest_path="$2"
  local log_dir="${RESULTS_DIR}/${suite_name}"
  local total_count passed_count failed_count case_index

  if [[ ! -f "${manifest_path}" ]]; then
    echo "未找到测试清单：${manifest_path}" >&2
    return 1
  fi

  mkdir -p "${log_dir}"
  rm -f "${log_dir}"/*.log

  total_count="$(count_manifest_cases "${manifest_path}")"
  passed_count=0
  failed_count=0
  case_index=0

  print_header "${suite_name} 开始执行"

  while IFS='|' read -r display_name test_label; do
    if [[ -z "${display_name// }" ]] || [[ "${display_name}" == \#* ]]; then
      continue
    fi

    case_index=$((case_index + 1))
    local safe_name log_file
    safe_name="$(printf '%02d_%s' "${case_index}" "${test_label//./_}")"
    log_file="${log_dir}/${safe_name}.log"

    echo "[用例 ${case_index}/${total_count}] ${display_name}"
    if run_django_case "${display_name}" "${test_label}" "${log_file}"; then
      passed_count=$((passed_count + 1))
    else
      failed_count=$((failed_count + 1))
    fi
    echo ""
  done < "${manifest_path}"

  {
    echo "${suite_name} 汇总："
    echo "总测试集数：${total_count}"
    echo "成功数：${passed_count}"
    echo "失败数：${failed_count}"
    echo ""
  } | tee -a "${SUMMARY_FILE}"

  if [[ "${failed_count}" -gt 0 ]]; then
    return 1
  fi
  return 0
}

run_e2e_suite() {
  local suite_name="e2e_tests"
  local log_dir="${RESULTS_DIR}/${suite_name}"
  local install_log="${log_dir}/01_playwright_install.log"
  local run_log="${log_dir}/02_playwright_run.log"

  check_command npm
  check_command npx

  mkdir -p "${log_dir}"
  rm -f "${log_dir}"/*.log

  print_header "${suite_name} 开始执行"

  echo "[开始] 安装或校验 Playwright Chromium 浏览器"
  set +e
  (
    cd "${FRONTEND_DIR}" &&
    npx playwright install chromium
  ) 2>&1 | tee "${install_log}"
  local install_status=${PIPESTATUS[0]}
  set -e
  if [[ "${install_status}" -ne 0 ]]; then
    echo "[失败] Playwright Chromium 浏览器安装失败"
    echo "失败原因：npx playwright install chromium 退出码 ${install_status}"
    tail -n 20 "${install_log}" || true
    {
      echo "${suite_name} 汇总："
      echo "总测试集数：1"
      echo "成功数：0"
      echo "失败数：1"
      echo ""
    } | tee -a "${SUMMARY_FILE}"
    return 1
  fi
  echo "[成功] Playwright Chromium 浏览器已就绪"
  echo ""

  echo "[开始] 前端 E2E 联调测试"
  set +e
  (
    cd "${FRONTEND_DIR}" &&
    npm run e2e
  ) 2>&1 | tee "${run_log}"
  local run_status=${PIPESTATUS[0]}
  set -e
  if [[ "${run_status}" -ne 0 ]]; then
    echo "[失败] 前端 E2E 联调测试"
    echo "失败原因：npm run e2e 退出码 ${run_status}"
    tail -n 20 "${run_log}" || true
    {
      echo "${suite_name} 汇总："
      echo "总测试集数：1"
      echo "成功数：0"
      echo "失败数：1"
      echo ""
    } | tee -a "${SUMMARY_FILE}"
    return 1
  fi

  echo "[成功] 前端 E2E 联调测试"
  {
    echo "${suite_name} 汇总："
    echo "总测试集数：1"
    echo "成功数：1"
    echo "失败数：0"
    echo ""
  } | tee -a "${SUMMARY_FILE}"
  return 0
}

main() {
  check_command uv
  check_command tee
  check_command awk
  check_command mktemp
  prepare_result_dirs

  local unit_status=0
  local api_status=0
  local e2e_status=0

  case "${MODE}" in
    unit)
      run_manifest_suite "unit_tests" "${FULLSTACK_DIR}/tests/unit_tests/test_targets.txt" || unit_status=$?
      ;;
    api)
      run_manifest_suite "API_tests" "${FULLSTACK_DIR}/tests/API_tests/test_targets.txt" || api_status=$?
      ;;
    all)
      run_manifest_suite "unit_tests" "${FULLSTACK_DIR}/tests/unit_tests/test_targets.txt" || unit_status=$?
      run_manifest_suite "API_tests" "${FULLSTACK_DIR}/tests/API_tests/test_targets.txt" || api_status=$?
      ;;
    e2e)
      run_e2e_suite || e2e_status=$?
      ;;
    full)
      run_manifest_suite "unit_tests" "${FULLSTACK_DIR}/tests/unit_tests/test_targets.txt" || unit_status=$?
      run_manifest_suite "API_tests" "${FULLSTACK_DIR}/tests/API_tests/test_targets.txt" || api_status=$?
      run_e2e_suite || e2e_status=$?
      ;;
    *)
      echo "无效参数：${MODE}" >&2
      echo "可用参数：unit、api、e2e、all、full" >&2
      exit 1
      ;;
  esac

  print_header "测试执行完成"
  cat "${SUMMARY_FILE}"
  echo "汇总日志：${SUMMARY_FILE}"

  if [[ "${unit_status}" -ne 0 ]] || [[ "${api_status}" -ne 0 ]] || [[ "${e2e_status}" -ne 0 ]]; then
    exit 1
  fi
}

main
