from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
TOOL_DIR = ROOT / "tools" / "coverage_authoring"
for path in (str(BACKEND), str(TOOL_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)
