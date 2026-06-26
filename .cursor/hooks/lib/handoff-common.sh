#!/usr/bin/env bash
# Shared helpers for Cursor verify-handoff hooks.
set -euo pipefail

handoff_repo_root() {
  cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd
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
  done < <(git -C "$root" diff --name-only HEAD 2>/dev/null || true)

  while IFS= read -r f; do
    [[ -n "$f" ]] || continue
    [[ "$f" =~ $pattern ]] && return 0
  done < <(git -C "$root" diff --cached --name-only 2>/dev/null || true)

  while IFS= read -r f; do
    [[ -n "$f" ]] || continue
    [[ "$f" =~ $pattern ]] && return 0
  done < <(git -C "$root" ls-files --others --exclude-standard 2>/dev/null || true)

  return 1
}

verify_request_flag() {
  echo "$1/.cursor/hooks/.verify-requested"
}

# Arm verify follow-up for the current prompt (user typed "test" in beforeSubmitPrompt).
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

# Follow-up verify turn: only when user armed via "test" prompt and code changed.
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
  {
    git -C "$root" diff --name-only HEAD 2>/dev/null || true
    git -C "$root" diff --cached --name-only 2>/dev/null || true
    git -C "$root" ls-files --others --exclude-standard 2>/dev/null || true
  } | sort -u | grep -E "$pattern" || true
}
