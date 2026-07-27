"""Live /chat path must remain untouched by Experience Center demo modules."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

# Paths that may change alongside EC work (tests, trace_panels demo branches, etc.).
EC_ALLOWED_PREFIXES = (
    "backend/app/demo/",
    "backend/app/governance/trace_panels.py",
    "backend/app/tests/test_ec_",
    "backend/app/tests/test_demo_scenarios_stage3jd.py",
    "backend/app/tests/test_experience_center_governance_stage3m_ec.py",
    "backend/app/tests/test_experience_center_canonical_purity.py",
    "backend/app/tests/test_live_path_untouched_by_ec.py",
    "frontend/src/components/EcVisualLanesPanel.tsx",
    "frontend/src/components/ChatBubble.tsx",
    "frontend/src/components/DemoScenarioPicker.tsx",
    "frontend/src/components/ExperienceCenterGovernancePanels.tsx",
    "frontend/src/components/InvestigationProgressPanel.tsx",
    "frontend/src/lib/investigationProgress.ts",
    "frontend/src/types/api.ts",
)

# EC demo work must never edit these live-path surfaces (dispatch plan owns pipeline.py).
EC_FORBIDDEN_PREFIXES = (
    "backend/app/api/routes_chat.py",
    "backend/app/graph/",
    "backend/app/planner/",
    "backend/app/routing/",
)

# Plan item 26 — dead compatibility branches only; may ship in the same commit as 26a EC fixtures.
ITEM_26_COMPAT_CLEANUP_PATHS = (
    "backend/app/planner/executor.py",
    "backend/app/planner/plan_promotion_merge.py",
)

EC_SCOPE_PREFIXES = (
    "backend/app/demo/",
    "frontend/src/components/EcVisualLanesPanel.tsx",
    "frontend/src/components/ChatBubble.tsx",
    "frontend/src/components/DemoScenarioPicker.tsx",
    "frontend/src/components/ExperienceCenterGovernancePanels.tsx",
    "frontend/src/components/InvestigationProgressPanel.tsx",
    "frontend/src/lib/investigationProgress.ts",
)


def test_ec_changes_stay_within_allowlist() -> None:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    changed = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not changed:
        return
    if not any(
        path.startswith(prefix)
        for path in changed
        for prefix in EC_SCOPE_PREFIXES
    ):
        return
    offenders = [
        path
        for path in changed
        if any(path.startswith(prefix) for prefix in EC_FORBIDDEN_PREFIXES)
        and not any(path.startswith(prefix) for prefix in EC_ALLOWED_PREFIXES)
        and path not in ITEM_26_COMPAT_CLEANUP_PATHS
        and not path.startswith("docs/evals/")
        and path not in {".cursor/hooks/.loop-asap-requested"}
    ]
    assert not offenders, f"EC work touched forbidden live paths: {offenders}"
