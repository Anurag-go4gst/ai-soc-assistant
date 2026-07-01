#!/usr/bin/env bash
# Select an AI-SOC environment profile and sync AI_SOC_ENV_PROFILE into repo-root .env.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROFILE="${1:?Usage: $0 <profile-id>   (e.g. coe or development)}"
MANIFEST="$ROOT/env/profiles/manifest.json"
EXAMPLE="$ROOT/env/profiles/${PROFILE}.env.example"
ACTIVE="$ROOT/env/active.profile"
ROOT_ENV="$ROOT/.env"

if [[ ! -f "$EXAMPLE" ]]; then
  echo "ERROR: Profile '$PROFILE' not found at $EXAMPLE" >&2
  echo "Available profiles (from manifest):" >&2
  if command -v jq >/dev/null 2>&1 && [[ -f "$MANIFEST" ]]; then
    jq -r '.profiles[].id' "$MANIFEST" >&2
  else
    ls -1 "$ROOT/env/profiles/"*.env.example 2>/dev/null | xargs -n1 basename | sed 's/.env.example$//' >&2
  fi
  exit 1
fi

echo "$PROFILE" > "$ACTIVE"

# Merge AI_SOC_ENV_PROFILE into root .env without dropping other secret lines.
if [[ -f "$ROOT_ENV" ]]; then
  grep -v '^AI_SOC_ENV_PROFILE=' "$ROOT_ENV" > "${ROOT_ENV}.tmp" || true
else
  if [[ -f "$ROOT/env/secrets.example" ]]; then
    cp "$ROOT/env/secrets.example" "${ROOT_ENV}.tmp"
    grep -v '^AI_SOC_ENV_PROFILE=' "${ROOT_ENV}.tmp" > "${ROOT_ENV}.tmp2" || true
    mv "${ROOT_ENV}.tmp2" "${ROOT_ENV}.tmp"
  else
    : > "${ROOT_ENV}.tmp"
  fi
fi
echo "AI_SOC_ENV_PROFILE=$PROFILE" >> "${ROOT_ENV}.tmp"
mv "${ROOT_ENV}.tmp" "$ROOT_ENV"

echo "Selected profile: $PROFILE"
echo "  active file:    $ACTIVE"
echo "  profile config: $EXAMPLE"
echo "  root secrets:   $ROOT_ENV"
echo ""
echo "Restart backend to apply:"
echo "  docker compose up -d --force-recreate backend"
