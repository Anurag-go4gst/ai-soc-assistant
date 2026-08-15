#!/usr/bin/env bash
# Cloud Agent bootstrap for the AI-SOC Docker stack.
#
# The Cursor Cloud Agent VM is a nested container that ships without Docker: the
# default overlayfs graphdriver mount fails and same-bridge container traffic is
# dropped by the netfilter FORWARD chain. This script installs Docker and
# encapsulates the VM-specific setup so the canonical `docker compose` dev path
# works unchanged — self-contained, so it needs no prebuilt snapshot.
#
# Frontend node_modules lives on a Docker named volume (docker-compose.cloud-agent.yml)
# and is installed with `docker run npm ci` — both avoid npm crashes seen with an
# overlay bind mount and with `docker compose run` in this environment.
#
# Subcommands:
#   install  One-time-ish, idempotent: start dockerd, seed .env (dev secrets +
#            self-contained LLM mock mode on first seed only), build images,
#            install the frontend node_modules. Safe to re-run.
#   start    Per-boot: start dockerd, fix nested-bridge networking, bring the
#            stack up (postgres first so the backend migration does not race an
#            unready DB), wait for backend health, then install deps and start the
#            frontend. Idempotent; returns.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

log() { echo "[cloud-agent] $*"; }

# All stack commands go through the base compose file plus the Cloud-Agent
# override (named volume for frontend node_modules — see docker-compose.cloud-agent.yml).
dc() { docker compose -f docker-compose.yml -f docker-compose.cloud-agent.yml "$@"; }

ensure_docker_installed() {
  # Make the environment self-contained: the default Cloud Agent image ships
  # Python/Node/Chrome but not Docker. Install the engine + compose plugin +
  # fuse-overlayfs if absent. --force-confold answers the fuse.conf conffile
  # prompt non-interactively. Idempotent: a no-op once installed (e.g. when the
  # environment boots from a snapshot that already has Docker).
  if command -v docker >/dev/null 2>&1 && command -v fuse-overlayfs >/dev/null 2>&1; then
    return 0
  fi
  log "installing docker engine + compose plugin + fuse-overlayfs"
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    -o Dpkg::Options::="--force-confold" \
    docker.io docker-compose-v2 fuse-overlayfs
}

start_dockerd() {
  if docker info >/dev/null 2>&1; then
    log "docker daemon already running"
    return 0
  fi
  log "starting docker daemon (fuse-overlayfs storage driver)"
  sudo mkdir -p /etc/docker
  if [[ ! -f /etc/docker/daemon.json ]]; then
    # fuse-overlayfs works in the nested VM where the default overlayfs graphdriver
    # mount fails with "invalid argument". Disable the containerd snapshotter so the
    # classic graphdriver honors the storage-driver choice.
    echo '{ "storage-driver": "fuse-overlayfs", "features": { "containerd-snapshotter": false } }' \
      | sudo tee /etc/docker/daemon.json >/dev/null
  fi
  sudo bash -c 'nohup dockerd >/var/log/dockerd.log 2>&1 &'
  # Cold-init on a fresh /var/lib/docker (first ever boot) is much slower than a
  # warm start, so allow up to ~120s.
  for _ in $(seq 1 120); do
    docker info >/dev/null 2>&1 && break
    sleep 1
  done
  if ! docker info >/dev/null 2>&1; then
    log "ERROR: docker daemon failed to start"
    sudo tail -n 60 /var/log/dockerd.log >&2 || true
    exit 1
  fi
  # Let the invoking (non-root) user reach the socket without a fresh login shell.
  sudo chmod 666 /var/run/docker.sock 2>/dev/null || true
}

fix_bridge_networking() {
  # In the nested VM, new connections between two containers on the same bridge are
  # pushed through the netfilter FORWARD chain (bridge-nf-call-iptables=1) where
  # Docker's rules only accept traffic entering the bridge from outside, so
  # container-to-container connects time out. Disabling bridge netfilter lets the
  # Linux bridge switch that traffic at L2 (the usual host default).
  sudo sysctl -w net.bridge.bridge-nf-call-iptables=0  >/dev/null 2>&1 || true
  sudo sysctl -w net.bridge.bridge-nf-call-ip6tables=0 >/dev/null 2>&1 || true
}

seed_env() {
  local fresh=false
  [[ -f .env ]] || fresh=true
  # Seeds .env from env/profiles/<profile>.env.example when missing and keeps the
  # host ports + derived API/CORS keys consistent. Idempotent on a live stack.
  ./scripts/coe_port_autoselect.sh >/dev/null
  if [[ "${fresh}" == true ]]; then
    log "seeded fresh .env — filling dev-only auth secrets"
    if command -v openssl >/dev/null 2>&1; then
      sed -i "s|^APP_AUTH_PASSWORD=.*|APP_AUTH_PASSWORD=$(openssl rand -hex 16)|" .env
      sed -i "s|^APP_AUTH_SESSION_SECRET=.*|APP_AUTH_SESSION_SECRET=$(openssl rand -hex 32)|" .env
    fi
    # The Cloud Agent VM has no host llama-server; use the governed, self-contained
    # mock LLM mode so chat turns stay fast and dependency-free. Operators who wire a
    # real endpoint can edit .env; later boots preserve it.
    sed -i 's|^AI_SOC_LLM_MODE=local|AI_SOC_LLM_MODE=mock|' .env
  fi
}

prepare_frontend_deps() {
  # Populate the frontend node_modules named volume with a SINGLE, non-concurrent
  # clean install BEFORE the frontend service starts. The Cloud-Agent override
  # points the service at this volume and makes it run `npm run dev` directly, so
  # this is the only place deps are installed (no concurrent installs racing the
  # same tree). Use `npm ci` (clean, lockfile-based) to avoid the incremental
  # rename path that intermittently crashes npm in the nested VM. Retry to ride
  # out npm flakiness; the volume persists into the snapshot so later boots warm.
  # Use plain `docker run`, not `docker compose run`: the latter reliably crashes
  # npm here ("Exit handler never called!"), while `docker run` with the same
  # mounts installs cleanly. Mount the source and the shared node_modules volume
  # (fixed name from docker-compose.cloud-agent.yml) so the service reuses it.
  local attempt
  for attempt in 1 2 3; do
    if docker run --rm \
        -v "${REPO_ROOT}/frontend:/app" \
        -v ai_soc_frontend_node_modules:/app/node_modules \
        -w /app node:22-alpine \
        sh -c 'npm ci --no-audit --no-fund'; then
      log "frontend node_modules ready (attempt ${attempt})"
      return 0
    fi
    log "npm ci failed (attempt ${attempt}); retrying"
    sleep 3
  done
  log "WARNING: frontend node_modules not confirmed after retries"
  return 1
}

up_backend_stack() {
  log "starting postgres and waiting for readiness"
  dc up -d postgres
  for _ in $(seq 1 60); do
    dc exec -T postgres pg_isready -U ai_soc -d ai_soc_assistant >/dev/null 2>&1 && break
    sleep 1
  done
  log "starting backend"
  dc up -d backend
}

ensure_frontend() {
  # Deps are already installed into the named volume, and the Cloud-Agent override
  # makes the service run `npm run dev` directly, so Vite comes up quickly. Wait
  # for it; only re-prepare + recreate if the container actually exited.
  local port url recreated=0 status
  port="$(source "${REPO_ROOT}/scripts/lib/dotenv.sh"; dotenv_get "${REPO_ROOT}/.env" AI_SOC_FRONTEND_HOST_PORT 3010)"
  url="http://127.0.0.1:${port}/"
  log "starting frontend and waiting for it (${url})"
  dc up -d frontend
  for _ in $(seq 1 100); do
    if curl -fsS --max-time 3 "${url}" >/dev/null 2>&1; then
      log "frontend: OK"
      return 0
    fi
    status="$(dc ps -q frontend | xargs -r docker inspect -f '{{.State.Status}}' 2>/dev/null || true)"
    if [ "${status}" = "exited" ] && [ "${recreated}" -lt 2 ]; then
      recreated=$((recreated + 1))
      log "frontend exited — re-preparing deps and restarting (${recreated}/2)"
      prepare_frontend_deps || true
      dc up -d --force-recreate frontend >/dev/null 2>&1 || true
    fi
    sleep 3
  done
  log "WARNING: frontend did not become reachable; check 'docker compose logs frontend'"
}

wait_health() {
  local port health
  port="$(source "${REPO_ROOT}/scripts/lib/dotenv.sh"; dotenv_get "${REPO_ROOT}/.env" AI_SOC_BACKEND_HOST_PORT 8010)"
  health="http://127.0.0.1:${port}/health"
  log "waiting for backend health (${health})"
  for _ in $(seq 1 60); do
    if curl -fsS --max-time 3 "${health}" >/dev/null 2>&1; then
      log "backend health: OK"
      return 0
    fi
    sleep 2
  done
  # One recovery attempt in case the backend lost the DB race on a cold start.
  log "backend not healthy yet — restarting backend once"
  dc up -d backend
  for _ in $(seq 1 30); do
    curl -fsS --max-time 3 "${health}" >/dev/null 2>&1 && { log "backend health: OK"; return 0; }
    sleep 2
  done
  log "ERROR: backend did not become healthy"
  dc ps
  exit 1
}

case "${1:-start}" in
  install)
    ensure_docker_installed
    start_dockerd
    seed_env
    log "building images"
    dc build
    log "preparing frontend node_modules"
    prepare_frontend_deps || true
    log "install complete"
    ;;
  start)
    ensure_docker_installed
    start_dockerd
    fix_bridge_networking
    seed_env
    up_backend_stack
    wait_health
    prepare_frontend_deps || true
    ensure_frontend
    log "stack is up:"
    dc ps
    ;;
  *)
    echo "usage: $0 {install|start}" >&2
    exit 2
    ;;
esac
