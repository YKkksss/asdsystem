#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

trap 'echo "[ERR] line=$LINENO cmd=$BASH_COMMAND" >&2; exit 1' ERR

FULLSTACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec "${FULLSTACK_DIR}/scripts/run_tests.sh" api
