#!/bin/bash
# Fetch the MITRE ATT&CK Enterprise STIX 2.1 bundle for the offline technique
# resolver (backend/app/threat/stix_resolver.py). Operator step, not run in CI —
# the ~51MB bundle is not committed to git (see backend/data/threat_intel/ in
# .gitignore). Run from the repo root.
set -euo pipefail

DEST_DIR="backend/data/threat_intel/attack"
DEST_FILE="${DEST_DIR}/enterprise-attack.json"
URL="https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack.json"

mkdir -p "${DEST_DIR}"
echo "Fetching ${URL} -> ${DEST_FILE}"
curl -fsSL "${URL}" -o "${DEST_FILE}.tmp"
mv "${DEST_FILE}.tmp" "${DEST_FILE}"

python3 -c "
import json
with open('${DEST_FILE}') as f:
    data = json.load(f)
count = sum(1 for o in data['objects'] if o.get('type') == 'attack-pattern')
print(f'OK: {count} attack-pattern objects loaded')
"

echo "Set AI_SOC_ATTACK_STIX_PATH=${DEST_FILE#backend/} in .env (relative to backend/ working dir), then restart the backend."
