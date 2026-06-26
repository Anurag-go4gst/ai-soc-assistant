#!/usr/bin/env bash
# Shared helpers for Cursor verify-handoff hooks.
set -euo pipefail

handoff_repo_root() {
  cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd
}

all_changed_paths() {
  local root="$1"
  {
    git -C "$root" diff --name-only HEAD 2>/dev/null || true
    git -C "$root" diff --cached --name-only 2>/dev/null || true
    git -C "$root" ls-files --others --exclude-standard 2>/dev/null || true
  } | sort -u
}

# True when the working tree has uncommitted changes under code/test paths
# (not docs-only, eval baselines, or agent local state).
has_meaningful_code_changes() {
  local root="$1"
  local pattern='^(backend/|frontend/|scripts/|test_harness/)'
  local f

  if ! git -C "$root" rev-parse --git-dir >/dev/null 2>&1; then
    return 1
  fi

  while IFS= read -r f; do
    [[ -n "$f" ]] || continue
    [[ "$f" =~ $pattern ]] && return 0
  done < <(all_changed_paths "$root")

  return 1
}

verify_request_flag() {
  echo "$1/.cursor/hooks/.verify-requested"
}

# Arm verify follow-up for the current prompt (user typed "test this" in beforeSubmitPrompt).
arm_verify_request() {
  local root="$1"
  local flag
  flag="$(verify_request_flag "$root")"
  mkdir -p "$(dirname "$flag")"
  date -u +"%Y-%m-%dT%H:%M:%SZ" >"$flag"
}

disarm_verify_request() {
  local root="$1"
  rm -f "$(verify_request_flag "$root")"
}

is_verify_requested() {
  local root="$1"
  [[ -f "$(verify_request_flag "$root")" ]]
}

# Follow-up verify turn: only when user armed via "test this" prompt and code changed.
# Legacy hard-off: touch .cursor/hooks/DISABLE_VERIFY_ON_STOP
should_verify_followup() {
  local root="$1"
  local disable="$root/.cursor/hooks/DISABLE_VERIFY_ON_STOP"
  [[ -f "$disable" ]] && return 1
  is_verify_requested "$root" || return 1
  has_meaningful_code_changes "$root"
}

changed_code_paths() {
  local root="$1"
  local pattern='^(backend/|frontend/|scripts/|test_harness/)'
  all_changed_paths "$root" | grep -E "$pattern" || true
}

# --- Prod / deploy actions (driven by changed paths) ---

needs_frontend_build() {
  local root="$1"
  local f pattern='^frontend/(src/|index\.html$|tailwind\.config\.|postcss\.config\.|vite\.config\.)'
  while IFS= read -r f; do
    [[ -n "$f" ]] || continue
    [[ "$f" =~ $pattern ]] && return 0
  done < <(all_changed_paths "$root")
  return 1
}

needs_docker_rebuild() {
  local root="$1"
  local f pattern='^(backend/pyproject\.toml$|backend/Dockerfile$|frontend/Dockerfile$|docker-compose(\.|$)|frontend/package(-lock)?\.json$)'
  while IFS= read -r f; do
    [[ -n "$f" ]] || continue
    [[ "$f" =~ $pattern ]] && return 0
  done < <(all_changed_paths "$root")
  return 1
}

needs_backend_restart() {
  local root="$1"
  local f
  needs_docker_rebuild "$root" && return 1
  while IFS= read -r f; do
    [[ -n "$f" ]] || continue
    [[ "$f" =~ ^backend/ ]] && return 0
  done < <(all_changed_paths "$root")
  return 1
}

branch_ahead_of_upstream() {
  local root="$1" count
  if ! git -C "$root" rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then
    return 1
  fi
  count="$(git -C "$root" rev-list --count '@{u}..HEAD' 2>/dev/null || echo 0)"
  [[ "${count:-0}" -gt 0 ]]
}

# Markdown block for .cursor/last-handoff.md (prod deploy section).
deploy_actions_markdown() {
  local root="$1"
  local any=0

  if needs_frontend_build "$root"; then
  any=1
  cat <<'EOF'
8. **Frontend prod static** (`frontend/src` or UI config changed) — publish to Nginx `frontend/dist`:
   ```bash
   cd frontend && npm run build
   ```
EOF
  fi

  if needs_docker_rebuild "$root"; then
  any=1
  cat <<'EOF'
9. **Docker stack** (`pyproject.toml`, `Dockerfile`, `docker-compose`, or `package.json` deps changed):
   ```bash
   docker compose build && docker compose up -d
   ```
EOF
  elif needs_backend_restart "$root"; then
  any=1
  cat <<'EOF'
9. **Backend reload** (`backend/` changed; uvicorn `--reload` usually picks this up). If prod behavior looks stale:
   ```bash
   docker compose restart backend
   ```
   Then confirm: `curl -s http://127.0.0.1:8010/health`
EOF
  fi

  if branch_ahead_of_upstream "$root"; then
  any=1
  cat <<'EOF'
10. **Remote deploy** — branch is ahead of upstream; push when ready (prod on another host needs this):
   ```bash
   git push
   ```
   Do not push unless the user asked.
EOF
  fi

  if [[ "$any" -eq 0 ]]; then
    echo "8. **Prod deploy** — no frontend build, docker rebuild, or backend restart required for the current diff."
  fi
}

# One-line summary for stop/subagent follow-up messages.
deploy_actions_followup_summary() {
  local root="$1" parts=()
  needs_frontend_build "$root" && parts+=("run \`cd frontend && npm run build\` for public UI")
  if needs_docker_rebuild "$root"; then
    parts+=("run \`docker compose build && docker compose up -d\`")
  elif needs_backend_restart "$root"; then
    parts+=("confirm backend health or \`docker compose restart backend\` if changes look stale")
  fi
  branch_ahead_of_upstream "$root" && parts+=("remind user to \`git push\` if prod is remote — only when asked")
  if [[ ${#parts[@]} -eq 0 ]]; then
    echo "No frontend build or docker restart required for this diff."
  else
    local joined="" part
    for part in "${parts[@]}"; do
      if [[ -n "$joined" ]]; then
        joined+="; "
      fi
      joined+="$part"
    done
    echo "${joined}."
  fi
}
