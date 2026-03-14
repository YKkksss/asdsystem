#!/usr/bin/env bash

set -euo pipefail

FULLSTACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec "${FULLSTACK_DIR}/scripts/run_tests.sh" api
