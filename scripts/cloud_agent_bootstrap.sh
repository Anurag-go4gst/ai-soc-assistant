#!/usr/bin/env bash
# Cloud Agent bootstrap for the AI-SOC Docker stack.
#
# The Cursor Cloud Agent VM is a nested container: the default Docker overlayfs
# mount fails and same-bridge container traffic is dropped by the netfilter
# FORWARD chain. This script encapsulates the VM-specific setup so the canonical
# `docker compose` dev path works unchanged.
#
# Subcommands:
#   install  One-time-ish, idempotent: start dockerd, seed .env (dev secrets +
#            self-contained LLM mock mode on first seed only), build images, warm
#            the frontend node_modules. Safe to re-run.
#   start    Per-boot: start dockerd, fix nested-bridge networking, bring the
#            stack up (postgres first so the backend migration does not race an
#            unready DB), then wait for backend health. Idempotent; returns.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

log() { echo "[cloud-agent] $*"; }

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
  for _ in $(seq 1 30); do
    docker info >/dev/null 2>&1 && break
    sleep 1
  done
  if ! docker info >/dev/null 2>&1; then
    log "ERROR: docker daemon failed to start"
    sudo tail -n 20 /var/log/dockerd.log >&2 || true
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

up_stack() {
  log "starting postgres and waiting for readiness"
  docker compose up -d postgres
  for _ in $(seq 1 60); do
    docker compose exec -T postgres pg_isready -U ai_soc -d ai_soc_assistant >/dev/null 2>&1 && break
    sleep 1
  done
  log "starting backend and frontend"
  docker compose up -d backend frontend
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
  docker compose up -d backend
  for _ in $(seq 1 30); do
    curl -fsS --max-time 3 "${health}" >/dev/null 2>&1 && { log "backend health: OK"; return 0; }
    sleep 2
  done
  log "ERROR: backend did not become healthy"
  docker compose ps
  exit 1
}

case "${1:-start}" in
  install)
    start_dockerd
    seed_env
    log "building images"
    docker compose build
    log "warming frontend node_modules"
    docker compose run --rm --no-deps --entrypoint sh frontend -c 'npm install' || true
    log "install complete"
    ;;
  start)
    start_dockerd
    fix_bridge_networking
    seed_env
    up_stack
    wait_health
    log "stack is up:"
    docker compose ps
    ;;
  *)
    echo "usage: $0 {install|start}" >&2
    exit 2
    ;;
esac
