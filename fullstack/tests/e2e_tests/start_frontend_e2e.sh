#!/usr/bin/env bash

set -euo pipefail

FULLSTACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FRONTEND_DIR="${FULLSTACK_DIR}/frontend"

export VITE_API_BASE_URL="http://127.0.0.1:8001/api/v1"

cd "${FRONTEND_DIR}"
exec npm run dev -- --host 127.0.0.1 --port 4174
