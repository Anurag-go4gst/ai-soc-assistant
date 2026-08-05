#!/usr/bin/env bash
# Pick free host ports for the AI-SOC Docker stack and write them into repo-root .env.
#
# Why this exists: docker-compose.yml publishes three host ports (backend, frontend,
# postgres). On a COE host those defaults are often already taken, and three derived
# keys (AI_SOC_PUBLIC_API_BASE_URL, AI_SOC_CORS_ALLOWED_ORIGINS, DATABASE_URL callers)
# must move with them. Hand-editing them one at a time is the usual source of a broken
# bring-up, so this script makes the whole selection atomic and idempotent.
#
# Idempotent: ports already published by THIS compose project count as free, so
# re-running against a live stack does not shuffle ports.
#
# Usage:
#   scripts/coe_port_autoselect.sh              # apply changes to .env
#   scripts/coe_port_autoselect.sh --dry-run    # print what would change
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
fi

ENV_FILE="${REPO_ROOT}/.env"
PROFILE_DEFAULT="coe"

if [[ ! -f "${ENV_FILE}" ]]; then
  PROFILE="${AI_SOC_ENV_PROFILE:-${PROFILE_DEFAULT}}"
  SEED="env/profiles/${PROFILE}.env.example"
  if [[ ! -f "${SEED}" ]]; then
    echo "ERROR: no .env and no seed profile at ${SEED}" >&2
    exit 1
  fi
  echo "no .env found — seeding from ${SEED}"
  if [[ "${DRY_RUN}" != true ]]; then
    cp "${SEED}" "${ENV_FILE}"
    echo "NOTE: fill operator secrets in .env (APP_AUTH_PASSWORD, APP_AUTH_SESSION_SECRET, tokens) before serving traffic." >&2
  fi
fi

# shellcheck source=lib/dotenv.sh
source "${REPO_ROOT}/scripts/lib/dotenv.sh"

AI_SOC_HOST_BIND="$(dotenv_get "${ENV_FILE}" AI_SOC_HOST_BIND 127.0.0.1)"
AI_SOC_BACKEND_HOST_PORT="$(dotenv_get "${ENV_FILE}" AI_SOC_BACKEND_HOST_PORT 8010)"
AI_SOC_FRONTEND_HOST_PORT="$(dotenv_get "${ENV_FILE}" AI_SOC_FRONTEND_HOST_PORT 3010)"
AI_SOC_POSTGRES_HOST_PORT="$(dotenv_get "${ENV_FILE}" AI_SOC_POSTGRES_HOST_PORT 5434)"
AI_SOC_CORS_ALLOWED_ORIGINS="$(dotenv_get "${ENV_FILE}" AI_SOC_CORS_ALLOWED_ORIGINS)"

HOST_BIND="${AI_SOC_HOST_BIND:-127.0.0.1}"
COMPOSE_PROJECT="$(dotenv_get "${ENV_FILE}" COMPOSE_PROJECT_NAME "$(basename "${REPO_ROOT}")")"

# Ports currently published by our own compose project. Treated as available so a
# re-run on a running stack is a no-op instead of a pointless port walk.
# `docker compose port <service> <container_port>` prints "host:port" when the
# service is up, and nothing when it is not.
own_published_port() {
  local service="$1" container_port="$2" mapped
  mapped="$(docker compose port "${service}" "${container_port}" 2>/dev/null || true)"
  [[ -z "${mapped}" ]] && return 0
  printf '%s' "${mapped##*:}"
}

OWN_PORTS="$(
  own_published_port backend 8010
  echo
  own_published_port frontend 3010
  echo
  own_published_port postgres 5432
  echo
)"

is_own_port() {
  [[ -n "$1" ]] && grep -qx "$1" <<<"${OWN_PORTS}"
}

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltnH 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${port}\$"
    return $?
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
    return $?
  fi
  echo "ERROR: neither ss nor lsof available — cannot verify port ${port}" >&2
  exit 1
}

# Ports chosen earlier in this same run are not yet bound, so track them explicitly.
CLAIMED=()
is_claimed() {
  local port="$1" c
  for c in "${CLAIMED[@]:-}"; do
    [[ "${c}" == "${port}" ]] && return 0
  done
  return 1
}

pick_port() {
  local label="$1" preferred="$2" candidate="${2}" limit=200
  local i
  for ((i = 0; i < limit; i++)); do
    candidate=$((preferred + i))
    if is_claimed "${candidate}"; then
      continue
    fi
    if is_own_port "${candidate}"; then
      CLAIMED+=("${candidate}")
      echo "  ${label}: ${candidate} held by this stack (keeping)" >&2
      printf '%s' "${candidate}"
      return 0
    fi
    if ! port_in_use "${candidate}"; then
      CLAIMED+=("${candidate}")
      if [[ "${candidate}" != "${preferred}" ]]; then
        echo "  ${label}: ${preferred} busy -> ${candidate}" >&2
      else
        echo "  ${label}: ${preferred} free" >&2
      fi
      printf '%s' "${candidate}"
      return 0
    fi
  done
  echo "ERROR: no free port for ${label} in range ${preferred}-$((preferred + limit))" >&2
  exit 1
}

echo "== AI-SOC port auto-select (project: ${COMPOSE_PROJECT}) =="
BACKEND_PORT="$(pick_port backend "${AI_SOC_BACKEND_HOST_PORT:-8010}")"
FRONTEND_PORT="$(pick_port frontend "${AI_SOC_FRONTEND_HOST_PORT:-3010}")"
POSTGRES_PORT="$(pick_port postgres "${AI_SOC_POSTGRES_HOST_PORT:-5434}")"

PUBLIC_API="http://${HOST_BIND}:${BACKEND_PORT}/api"

# Preserve any operator-added origins (e.g. the COE hostname); only rewrite the
# loopback entries, whose port must track the frontend publish port.
rebuild_cors() {
  local existing="${AI_SOC_CORS_ALLOWED_ORIGINS:-}" out=() origin
  out+=("http://localhost:${FRONTEND_PORT}" "http://127.0.0.1:${FRONTEND_PORT}")
  IFS=',' read -r -a parts <<<"${existing}"
  for origin in "${parts[@]:-}"; do
    origin="$(echo "${origin}" | tr -d '[:space:]')"
    [[ -z "${origin}" ]] && continue
    [[ "${origin}" == *"localhost:"* || "${origin}" == *"127.0.0.1:"* ]] && continue
    out+=("${origin}")
  done
  local IFS=','
  printf '%s' "${out[*]}"
}
CORS_ORIGINS="$(rebuild_cors)"

set_env_key() {
  local key="$1" value="$2"
  local current
  current="$(grep -E "^${key}=" "${ENV_FILE}" | tail -n1 | cut -d= -f2- || true)"
  if [[ "${current}" == "${value}" ]]; then
    echo "  ${key}=${value} (unchanged)"
    return 0
  fi
  echo "  ${key}=${value}"
  [[ "${DRY_RUN}" == true ]] && return 0
  if grep -qE "^${key}=" "${ENV_FILE}"; then
    # Value may contain '/' and ':', so use a delimiter that cannot appear in a URL.
    sed -i.bak -E "s|^${key}=.*|${key}=${value}|" "${ENV_FILE}"
    rm -f "${ENV_FILE}.bak"
  else
    printf '%s=%s\n' "${key}" "${value}" >>"${ENV_FILE}"
  fi
}

echo ""
echo "== writing .env =="
set_env_key AI_SOC_HOST_BIND "${HOST_BIND}"
set_env_key AI_SOC_BACKEND_HOST_PORT "${BACKEND_PORT}"
set_env_key AI_SOC_FRONTEND_HOST_PORT "${FRONTEND_PORT}"
set_env_key AI_SOC_POSTGRES_HOST_PORT "${POSTGRES_PORT}"
set_env_key AI_SOC_PUBLIC_API_BASE_URL "${PUBLIC_API}"
set_env_key AI_SOC_CORS_ALLOWED_ORIGINS "${CORS_ORIGINS}"
# Pin the compose project so a repo copied under a different directory name does not
# orphan the previous stack's containers (a second common source of port conflicts).
set_env_key COMPOSE_PROJECT_NAME "${COMPOSE_PROJECT}"
# BACKEND_PORT / FRONTEND_PORT in .env are container-side and stay 8010/3010 —
# only the *_HOST_PORT keys move. Do not rewrite them here.

echo ""
if [[ "${DRY_RUN}" == true ]]; then
  echo "DRY RUN — no changes written."
else
  echo "PORT AUTOSELECT: OK"
fi
echo "  backend   http://${HOST_BIND}:${BACKEND_PORT}"
echo "  frontend  http://${HOST_BIND}:${FRONTEND_PORT}"
echo "  postgres  ${HOST_BIND}:${POSTGRES_PORT}"
