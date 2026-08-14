"""Plan 6 C3 — KEEP 0 ADOPTED; no seam adoption, no fallback retirement.

C0 KEEP OFF is the production-authority context. C3 does not change
execution seams. Pins in test_execution_seam_coverage.py and
test_fallback_lifecycle_equivalence.py remain the inventory authority.
"""

from __future__ import annotations

from pathlib import Path

from app.chat import pipeline
from app.tests.test_execution_seam_coverage import SEAM_INVENTORY

_REPO = Path(__file__).resolve().parents[3]
_STOP = _REPO / "docs" / "evals" / "plan6" / "c3_stop_decision.md"


def test_c3_keep_zero_adopted_is_recorded() -> None:
    text = _STOP.read_text(encoding="utf-8")
    assert "P6_EXECUTION_SEAM_ADOPTION" in text
    assert "KEEP 0 ADOPTED" in text
    assert "Do not retire" in text or "do not retire" in text.lower()
    assert "CHANGE_LADDER" in text
    assert "_run_legacy_dispatch_fallback" in text


def test_inventory_stays_two_four_four_zero() -> None:
    classifications = [classification for _reaches, classification in SEAM_INVENTORY.values()]
    assert classifications.count("SEAM") == 2
    assert classifications.count("DECISION_REQUIRED") == 4
    assert classifications.count("KEEP_SEPARATE") == 4
    assert "ADOPT_CANDIDATE" not in classifications
    adopted = [path for path, (_reaches, classification) in SEAM_INVENTORY.items() if classification == "ADOPT_CANDIDATE"]
    assert adopted == []


def test_legacy_fallback_was_not_retired() -> None:
    assert hasattr(pipeline, "_run_legacy_dispatch_fallback")
    source = Path(pipeline.__file__).read_text(encoding="utf-8")
    hits = [
        line
        for line in source.splitlines()
        if "_run_legacy_dispatch_fallback(" in line and not line.strip().startswith("def ")
    ]
    assert len(hits) == 1, hits
