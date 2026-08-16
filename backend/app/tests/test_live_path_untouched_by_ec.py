"""Live /chat path must remain untouched by Experience Center demo modules."""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.demo.scenarios import list_demo_scenarios, run_demo_scenario
from app.schemas.responses import PlaceholderResponse

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
    "frontend/src/components/ec/",
    "frontend/src/pages/ScenariosPage.tsx",
)

# EC demo work must never edit these live-path surfaces (dispatch plan owns pipeline.py).
EC_FORBIDDEN_PREFIXES = (
    "backend/app/api/routes_chat.py",
    "backend/app/api/routes_chat_stream.py",
    "backend/app/api/routes_actions.py",
    "backend/app/chat/pipeline.py",
    "backend/app/graph/",
    "backend/app/planner/",
    "backend/app/routing/",
    "backend/app/schemas/responses.py",
    "backend/app/orchestration/mcp_execution_gate.py",
    "backend/app/safeguards/spl_validator.py",
    "frontend/src/components/ChatPanel.tsx",
)

RACES_FREEZE_PATHS = EC_FORBIDDEN_PREFIXES

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
    "frontend/src/components/ec/",
    "frontend/src/pages/ScenariosPage.tsx",
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


def _changed_paths() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def test_races_freeze_files_not_in_working_tree() -> None:
    """RACES must never modify production /chat contracts or ChatPanel."""
    changed = _changed_paths()
    offenders = [
        path
        for path in changed
        if any(path == freeze or path.startswith(freeze) for freeze in RACES_FREEZE_PATHS)
    ]
    assert not offenders, f"RACES freeze files appear in git diff: {offenders}"


def test_run_demo_scenario_still_constructs_placeholder_response() -> None:
    pickable = list_demo_scenarios()
    assert pickable, "expected at least one demo scenario"
    payload = run_demo_scenario(str(pickable[0]["scenario_id"]))
    response = PlaceholderResponse(**payload)
    assert response.trace_id
    assert response.message or response.analyst_summary


def test_no_app_demo_imports_in_pipeline_graph_planner() -> None:
    offenders: list[str] = []
    roots = [
        REPO / "backend/app/chat/pipeline.py",
        REPO / "backend/app/graph",
        REPO / "backend/app/planner",
    ]
    for root in roots:
        paths = [root] if root.is_file() else sorted(root.rglob("*.py"))
        for path in paths:
            text = path.read_text(encoding="utf-8")
            if "from app.demo" in text or "import app.demo" in text:
                offenders.append(str(path.relative_to(REPO)))
    assert not offenders, f"live authority modules imported app.demo: {offenders}"


def test_placeholder_response_schema_file_unchanged() -> None:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--", "backend/app/schemas/responses.py"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.stdout.strip() == ""


def test_ec_q1_ticket_does_not_call_production_actions() -> None:
    payload = run_demo_scenario("firewall_deny_coordinated_attack")
    for path in (REPO / "backend/app/demo").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "/api/actions" not in text, path
        assert "ProposedActionsPanel" not in text, path
        assert "ChatPanel" not in text, path
    actions = ((payload.get("analyst_response") or {}).get("interactive_actions") or [])
    ticket = next(item for item in actions if item.get("id") == "open_p1_incident_ticket")
    assert ticket["provenance"] == "simulated_phase10_action"
    assert ticket["production_side_effect"] is False
