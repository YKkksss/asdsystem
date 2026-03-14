#!/usr/bin/env bash

set -euo pipefail

FULLSTACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${FULLSTACK_DIR}/backend"
FRONTEND_DIR="${FULLSTACK_DIR}/frontend"
RESULTS_DIR="${FULLSTACK_DIR}/runtime/test_results"
SUMMARY_FILE="${RESULTS_DIR}/summary.log"

MODE="${1:-all}"

check_command() {
  local command_name="$1"
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "未找到命令：${command_name}"
    exit 1
  fi
}

prepare_result_dirs() {
  mkdir -p "${RESULTS_DIR}/unit_tests" "${RESULTS_DIR}/API_tests"
  : > "${SUMMARY_FILE}"
}

print_header() {
  local title="$1"
  echo ""
  echo "=============================="
  echo "${title}"
  echo "=============================="
}

run_suite() {
  local suite_name="$1"
  local manifest_path="$2"
  local log_dir="${RESULTS_DIR}/${suite_name}"
  local total_count=0
  local passed_count=0
  local failed_count=0

  mkdir -p "${log_dir}"
  rm -f "${log_dir}"/*.log

  print_header "${suite_name} 开始执行"

  while IFS='|' read -r display_name test_label; do
    if [[ -z "${display_name// }" ]] || [[ "${display_name}" == \#* ]]; then
      continue
    fi

    total_count=$((total_count + 1))
    local safe_name
    safe_name="$(printf '%02d_%s' "${total_count}" "${test_label//./_}")"
    local log_file="${log_dir}/${safe_name}.log"

    echo "[开始] ${display_name}"
    echo "测试标签：${test_label}"
    echo "日志文件：${log_file}"

    if (
      cd "${BACKEND_DIR}" &&
      uv run manage.py test "${test_label}" --verbosity 2
    ) 2>&1 | tee "${log_file}"; then
      passed_count=$((passed_count + 1))
      echo "[成功] ${display_name}"
    else
      failed_count=$((failed_count + 1))
      echo "[失败] ${display_name}"
      echo "失败日志摘要："
      tail -n 20 "${log_file}" || true
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

  mkdir -p "${log_dir}"
  rm -f "${log_dir}"/*.log

  print_header "${suite_name} 开始执行"

  echo "[开始] 安装或校验 Playwright Chromium 浏览器"
  if (
    cd "${FRONTEND_DIR}" &&
    npx playwright install chromium
  ) 2>&1 | tee "${install_log}"; then
    echo "[成功] Playwright Chromium 浏览器已就绪"
  else
    echo "[失败] Playwright Chromium 浏览器安装失败"
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

  echo ""
  echo "[开始] 前端 E2E 联调测试"
  if (
    cd "${FRONTEND_DIR}" &&
    npm run e2e
  ) 2>&1 | tee "${run_log}"; then
    echo "[成功] 前端 E2E 联调测试"
    {
      echo "${suite_name} 汇总："
      echo "总测试集数：1"
      echo "成功数：1"
      echo "失败数：0"
      echo ""
    } | tee -a "${SUMMARY_FILE}"
    return 0
  fi

  echo "[失败] 前端 E2E 联调测试"
  tail -n 20 "${run_log}" || true
  {
    echo "${suite_name} 汇总："
    echo "总测试集数：1"
    echo "成功数：0"
    echo "失败数：1"
    echo ""
  } | tee -a "${SUMMARY_FILE}"
  return 1
}

main() {
  check_command uv
  prepare_result_dirs

  local unit_status=0
  local api_status=0
  local e2e_status=0

  case "${MODE}" in
    unit)
      run_suite "unit_tests" "${FULLSTACK_DIR}/tests/unit_tests/test_targets.txt" || unit_status=$?
      ;;
    api)
      run_suite "API_tests" "${FULLSTACK_DIR}/tests/API_tests/test_targets.txt" || api_status=$?
      ;;
    all)
      run_suite "unit_tests" "${FULLSTACK_DIR}/tests/unit_tests/test_targets.txt" || unit_status=$?
      run_suite "API_tests" "${FULLSTACK_DIR}/tests/API_tests/test_targets.txt" || api_status=$?
      ;;
    e2e)
      run_e2e_suite || e2e_status=$?
      ;;
    full)
      run_suite "unit_tests" "${FULLSTACK_DIR}/tests/unit_tests/test_targets.txt" || unit_status=$?
      run_suite "API_tests" "${FULLSTACK_DIR}/tests/API_tests/test_targets.txt" || api_status=$?
      run_e2e_suite || e2e_status=$?
      ;;
    *)
      echo "无效参数：${MODE}"
      echo "可用参数：unit、api、e2e、all、full"
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
