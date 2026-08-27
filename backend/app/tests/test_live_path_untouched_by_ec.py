"""Live /chat path must remain untouched by Experience Center demo modules."""

from __future__ import annotations

import hashlib
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
    "frontend/src/api/ecClient.ts",
    "backend/app/api/routes_scenarios.py",
    "backend/app/main.py",
    "backend/app/tests/test_experience_center_response.py",
    "backend/app/tests/test_s1_governed_splunk_investigation.py",
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
    "frontend/src/api/ecClient.ts",
    "backend/app/api/routes_scenarios.py",
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
        for path in unapproved_freeze_offenders_in(changed)
        if not any(path.startswith(prefix) for prefix in EC_ALLOWED_PREFIXES)
        and path not in ITEM_26_COMPAT_CLEANUP_PATHS
        and not path.startswith("docs/evals/")
        and path not in {".cursor/hooks/.loop-asap-requested"}
    ]
    assert not offenders, f"EC work touched forbidden live paths: {offenders}"


# Advanced from bf7c3046 (RACES start) to b296a78 on 2026-08-18. Three freeze
# files legitimately changed in between, none of them RACES drift:
#   backend/app/chat/pipeline.py            — bfd9bdc, MCP capability governance
#   backend/app/orchestration/mcp_execution_gate.py — 2a9d105/8408170, exact-call
#                                             AUTH0 authorization (security fix)
#   frontend/src/components/ChatPanel.tsx   — 7c37580/b296a78, the ratified
#                                             legacy-EC demoMode convergence
# The freeze still means what it said; the baseline just no longer straddles
# approved non-RACES work. Advanced through canonical investigation P5: P0-P5
# intentionally changed the production authority path and did not import EC
# fixtures or demo authority into it. Advanced again through P8 at 949f7f4c:
# P7 added a bounded read-only PlanDelta edge to the existing Resource Planner
# graph, and P8 added the governed two-axis outcome projection in pipeline.py.
# Neither change came from RACES/EC work or introduced demo authority. The P8
# follow-up replaces lifecycle inference with its explicit default-off rollout flag.
# Advanced again through P10-P13 at 9f1ec922: P10 added the remediation planning
# lifecycle (pipeline.py seam, responses.py fields, a new ChatPanel card), P11 added
# the production action gate under app/actions/, and P13 mapped a stale investigation
# decision to a governed 409. All of it is production investigation work; none of it
# came from RACES/EC or imported demo authority into the live path.
# Advanced through the final architecture-conformance correction at 08c8b40c: the
# production routes removed an EC shortcut, P7 joined the canonical RP/AUTH0 seam,
# and P11 wired approved action execution. These are approved production authority
# corrections; the freeze continues from their exact reviewed commit.
# Advanced to 3a5f500104fb7a9ba609fc70aeb4af5894cee2eb (fix(spl): enforce request
# authority and semantic fidelity), the only commit since 08c8b40c that modified a
# protected freeze path. Audited before approval: the pipeline.py change is uniformly
# tightening — execution_eligible/execution_enabled pinned false, mcp_allowed narrowed,
# optimization_revalidation_approved false, and the replacement authoring predicate is
# strictly more restrictive than the one it replaced (it additionally requires
# sufficient_for_spl_authoring and response_shape == "spl_only"). All four deletions are
# replaced by stricter variants. No Final RQC, normalized_spl, exact-call, MCP, HIL/RBAC,
# Resource Planner, or evidence authority was weakened, and the commit touches no
# app/demo/ file, so it is production SPL governance work rather than RACES/EC work.
# Operator-approved for this commit only; later protected-file changes are NOT blessed,
# which is why the baseline is pinned to 3a5f5001 and not to HEAD.
# Advanced to 615069e6ca9cdb3d40b51d6a2f071346ecf3d6a2 after P0.1-A review and
# explicit P0.1-B approval. The protected f1f523cd change binds canonical Splunk
# arguments into exact-call AUTH0 and reuses them for connector execution, which
# strengthens mutation and substitution rejection. It does not change execution
# eligibility or weaken HIL/RBAC; candidate SPL remains non-executable and LLMs
# cannot call MCP. It imports no EC/demo authority and changes no write/remediation
# authority. The baseline is pinned to 615069e6, not HEAD. All future protected
# edits still require STOP plus explicit operator approval.
# Advanced to 5921f1d0cf569695db97ef0fd277ffdac8ec5338 after explicit operator
# approval of P2-FINAL-RQC-PIPELINE-WIRING and P2-FINAL-RQC-RACES-BASELINE. The
# protected pipeline.py change only forwards the already-governed Final RQC into
# existing SPL authoring producers (utility authoring and generate_llm_spl_via_plan).
# It does not change RQC construction, routing, T1-T4 merge order, execution
# eligibility, MCP, AUTH0, HIL, RBAC, write/remediation, or EC/demo authority.
# Candidate SPL remains non-executable; missing/malformed RQC still degrades.
# The freeze detector observed backend/app/chat/pipeline.py vs 615069e6 before
# this advancement. The baseline is pinned to 5921f1d0, not HEAD. All future
# protected edits still require STOP plus explicit operator approval.
# Advanced to 27970ea4d10f0e894c8adb4214e18cd46e24b28e after explicit operator
# approval of P8-D-CHATPANEL-SCENARIO-PICKER
# (docs/evals/p8_d/protected_change_packet.md). Production /chat empty state
# removes DemoScenarioPicker, StarterPrompts, and handleRunDemo only. Experience
# Center /scenarios is untouched. No routing, MCP, HIL vocabulary, write
# authority, or backend wire-contract rename. The freeze detector observed
# frontend/src/components/ChatPanel.tsx vs 5921f1d0 before this advancement.
# Baseline pinned to 27970ea4, not HEAD.
RACES_BASELINE_SHA = "27970ea4d10f0e894c8adb4214e18cd46e24b28e"

# Post-P10 convergence items 3.4 and 3.6 are operator-requested production work,
# not EC/RACES changes. Content hashes make this baseline advance exact and
# clone-stable without weakening the freeze for any future byte change.
RACES_APPROVED_PROTECTED_BLOB_SHA256 = {
    "backend/app/chat/pipeline.py": "4e443938e4c92dafb24443ad6ef7d39413140af3d54018bef4f9b0b3c9747e25",
    "backend/app/schemas/responses.py": "e8dfaa87e0b1db1c0c6ceccb74fa66f95a7604c90cbd531eb6c52a30ff3a8d7c",
    # Post-P10 5.4: envelope_version threaded into AUTH0 grant mint paths (additive).
    "backend/app/orchestration/mcp_execution_gate.py": "b12b0a054a43f3476ffab308329475b7a18c979fb786cce2196ba3fbfb6c2fad",
}


def _git_name_only(rev_range: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", rev_range],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def freeze_offenders_in(paths: list[str]) -> list[str]:
    return [
        path
        for path in paths
        if any(path == freeze or path.startswith(freeze) for freeze in RACES_FREEZE_PATHS)
    ]


def unapproved_freeze_offenders_in(paths: list[str]) -> list[str]:
    offenders: list[str] = []
    for path in freeze_offenders_in(paths):
        approved_hash = RACES_APPROVED_PROTECTED_BLOB_SHA256.get(path)
        candidate = REPO / path
        if approved_hash and candidate.is_file():
            actual_hash = hashlib.sha256(candidate.read_bytes()).hexdigest()
            if actual_hash == approved_hash:
                continue
        offenders.append(path)
    return offenders


def _changed_paths() -> list[str]:
    return _git_name_only("HEAD")


def test_races_freeze_files_not_in_working_tree() -> None:
    """RACES must never modify production /chat contracts or ChatPanel."""
    offenders = unapproved_freeze_offenders_in(_changed_paths())
    assert not offenders, f"RACES freeze files appear in git diff: {offenders}"


def test_races_freeze_files_unchanged_since_baseline() -> None:
    """Committed RACES work must not touch freeze files relative to bf7c304."""
    changed = _git_name_only(f"{RACES_BASELINE_SHA}...HEAD")
    offenders = unapproved_freeze_offenders_in(changed)
    assert not offenders, (
        f"RACES commits modified freeze files vs {RACES_BASELINE_SHA}: {offenders}"
    )


def test_races_freeze_detector_flags_frozen_paths_without_editing_them() -> None:
    offenders = freeze_offenders_in(
        [
            "backend/app/demo/scenarios.py",
            "frontend/src/components/ChatPanel.tsx",
            "backend/app/chat/pipeline.py",
            "backend/app/graph/chat_workflow.py",
            "plans/2026-08-16_2310_races-experience-center.md",
        ]
    )
    assert offenders == [
        "frontend/src/components/ChatPanel.tsx",
        "backend/app/chat/pipeline.py",
        "backend/app/graph/chat_workflow.py",
    ]


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
    changed = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert not unapproved_freeze_offenders_in(changed)


def test_ec_q1_ticket_does_not_call_production_actions() -> None:
    payload = run_demo_scenario("firewall_deny_coordinated_attack")
    for path in (REPO / "backend/app/demo").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "from app.api.routes_actions" in text or "import routes_actions" in text:
            raise AssertionError(f"{path} imports production action routes")
        if "ProposedActionsPanel" in text or "components.ChatPanel" in text:
            raise AssertionError(f"{path} references production chat/action UI")
    actions = ((payload.get("analyst_response") or {}).get("interactive_actions") or [])
    ticket = next(item for item in actions if item.get("id") == "open_p1_incident_ticket")
    assert ticket["provenance"] == "simulated_phase10_action"
    assert ticket["production_side_effect"] is False
