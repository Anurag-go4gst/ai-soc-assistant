#!/usr/bin/env bash
# Containerised /chat canonical path smoke (plan item 29).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -f .env ]]; then
  echo "ERROR: repo-root .env is missing (copy from .env.example for smoke)." >&2
  exit 1
fi

# Isolated compose project + ports so smoke does not collide with the primary stack.
export SMOKE_RUN_ID="${SMOKE_RUN_ID:-$(date +%Y%m%d%H%M%S)-$$}"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-aisoc-item29-${SMOKE_RUN_ID}}"
export AI_SOC_BACKEND_HOST_PORT="${AI_SOC_BACKEND_HOST_PORT:-18020}"
export AI_SOC_NGINX_HOST_PORT="${AI_SOC_NGINX_HOST_PORT:-18080}"
export AI_SOC_POSTGRES_HOST_PORT="${AI_SOC_POSTGRES_HOST_PORT:-15440}"
export AI_SOC_FRONTEND_HOST_PORT="${AI_SOC_FRONTEND_HOST_PORT:-13040}"
export AI_SOC_PUBLIC_API_BASE_URL="${AI_SOC_PUBLIC_API_BASE_URL:-http://127.0.0.1:${AI_SOC_NGINX_HOST_PORT}/api}"
export SMOKE_SOURCE_COMMIT="${SMOKE_SOURCE_COMMIT:-$(git rev-parse HEAD 2>/dev/null || echo unknown)}"

echo "SMOKE_COMPOSE project=${COMPOSE_PROJECT_NAME} nginx_port=${AI_SOC_NGINX_HOST_PORT} backend_port=${AI_SOC_BACKEND_HOST_PORT} pg_port=${AI_SOC_POSTGRES_HOST_PORT} source_commit=${SMOKE_SOURCE_COMMIT}"

PYTHONPATH=backend:. python3 scripts/smoke_canonical_paths_runner.py "$@"
