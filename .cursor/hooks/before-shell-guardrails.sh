#!/usr/bin/env bash
# Shell guardrails for agent terminals (fail-closed on dangerous git/docker patterns).
set -euo pipefail

input="$(cat)"
command="$(echo "$input" | jq -r '.command // empty')"

deny() {
  local user_msg="$1"
  local agent_msg="$2"
  jq -n \
    --arg um "$user_msg" \
    --arg am "$agent_msg" \
    '{permission: "deny", user_message: $um, agent_message: $am}'
  exit 0
}

ask() {
  local user_msg="$1"
  local agent_msg="$2"
  jq -n \
    --arg um "$user_msg" \
    --arg am "$agent_msg" \
    '{permission: "ask", user_message: $um, agent_message: $am}'
  exit 0
}

if [[ -z "$command" ]]; then
  jq -n '{permission: "allow"}'
  exit 0
fi

# Block force-push to main/master
if echo "$command" | grep -qE 'git push .*(-f|--force).* (origin )?(main|master)\b'; then
  deny \
    "Force push to main/master is blocked by project hook." \
    "Use a normal push or ask the user explicitly before force-pushing protected branches."
fi

# Block staging .env
if echo "$command" | grep -qE 'git add .*\.env\b|git add -A|git add \.'; then
  if echo "$command" | grep -qE '\.env\b|git add -A|git add \.'; then
    ask \
      "This may stage .env or broad secrets. Confirm no secrets are included." \
      "Prefer explicit file paths; never commit .env (AGENTS.md / hooks.md)."
  fi
fi

# Warn on public docker port binding (project binds 127.0.0.1 only)
if echo "$command" | grep -qE 'docker compose.*(-p|--publish|-P)|--publish'; then
  if echo "$command" | grep -qE '0\.0\.0\.0:[0-9]+|:80:|:443:|:8010:|:3010:'; then
    ask \
      "Docker publish may expose a service publicly. This repo binds to 127.0.0.1 only." \
      "Review docker-compose.yml — do not expose backend/frontend/db ports publicly."
  fi
fi

# Block git config mutations (user rule)
if echo "$command" | grep -qE 'git config (set|unset|--global|--system)'; then
  deny \
    "git config changes are blocked by project policy." \
    "Do not modify git config in agent sessions."
fi

jq -n '{permission: "allow"}'
