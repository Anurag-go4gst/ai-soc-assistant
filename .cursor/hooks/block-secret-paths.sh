#!/usr/bin/env bash
# Block agent writes to secret / credential paths.
set -euo pipefail

input="$(cat)"
path="$(echo "$input" | jq -r '.tool_input.path // .tool_input.file_path // .tool_input.target_notebook // empty')"

if [[ -z "$path" ]]; then
  echo '{"permission": "allow"}'
  exit 0
fi

case "$path" in
  .env|.env.*|*/.env|*/.env.*)
    jq -n \
      --arg p "$path" \
      '{permission: "deny", user_message: ("Blocked write to secret path: " + $p), agent_message: "Never commit or overwrite .env files. Use .env.example for templates."}'
    exit 0
    ;;
  *credentials*.json|*secrets*.json|*.pem|*.key)
    jq -n \
      --arg p "$path" \
      '{permission: "deny", user_message: ("Blocked write to credential-like path: " + $p), agent_message: "Do not create or modify credential files in the repo."}'
    exit 0
    ;;
esac

echo '{"permission": "allow"}'
exit 0
