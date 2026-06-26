#!/usr/bin/env bash
# Claude Code PreToolUse: block writes to secret / credential paths.
# Exit 2 = deny the tool call; stderr is shown to Claude.
set -euo pipefail

input="$(cat)"
path="$(echo "$input" | jq -r '.tool_input.file_path // .tool_input.path // empty')"
[[ -z "$path" ]] && exit 0

base="$(basename "$path")"

# Allow .env.example / .env.*.example templates.
case "$base" in
  *.example) exit 0 ;;
esac

case "$base" in
  .env|.env.*)
    echo "Blocked write to secret path: $path. Never commit or overwrite .env files; use .env.example for templates." >&2
    exit 2
    ;;
esac

case "$path" in
  *credentials*.json|*secrets*.json|*.pem|*.key)
    echo "Blocked write to credential-like path: $path. Do not create or modify credential files in the repo." >&2
    exit 2
    ;;
esac

exit 0
