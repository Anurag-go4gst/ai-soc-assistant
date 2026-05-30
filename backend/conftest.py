"""Pytest path setup: repo root for ``contracts`` and ``test_harness`` imports."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_root = str(_REPO_ROOT)
if _root not in sys.path:
    sys.path.insert(0, _root)
