"""Phase 11 demo readiness — documentation and Knowledge export sync only.

Asserts cutover/demo docs exist, all ten Phase 10 validation sheets are
Knowledge-exportable, and regression wiring is present. No /chat behavior.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from app.api.routes_knowledge import export_mapping_artifact
from app.knowledge.mapping_exports import SOC_VALIDATION_ARTIFACTS

REPO_ROOT = Path(__file__).resolve().parents[3]

EXPECTED_VALIDATION_ARTIFACTS = frozenset(
    {
        "soc_validation_use_cases",
        "soc_validation_spl_templates",
        "soc_validation_mitre",
        "soc_validation_questions",
        "soc_validation_github_enrichment",
        "soc_validation_github_batch_intake",
        "soc_validation_rag_sop",
        "soc_validation_pending_backlog",
        "soc_validation_combination_matrix",
        "soc_validation_demo_scenarios",
    }
)

FLAG_MATRIX_DOC = REPO_ROOT / "docs" / "demo" / "flag_cutover_matrix.md"
DEMO_SCENARIOS_DOC = REPO_ROOT / "docs" / "demo" / "demo_scenarios_readiness.md"
REGRESSION_SCRIPT = REPO_ROOT / "scripts" / "run_stage3_governance_regression.sh"
VALIDATION_CHECK_SCRIPT = REPO_ROOT / "scripts" / "build_soc_validation_sheets.py"


def test_all_phase10_validation_artifacts_registered() -> None:
    assert set(SOC_VALIDATION_ARTIFACTS) == EXPECTED_VALIDATION_ARTIFACTS


@pytest.mark.parametrize("artifact", sorted(EXPECTED_VALIDATION_ARTIFACTS))
def test_phase10_validation_knowledge_exports(artifact: str) -> None:
    response = export_mapping_artifact(artifact, file_format="json")
    payload = json.loads(response.body)
    assert payload["artifact"] == artifact
    assert payload["export_kind"] == "json_backed"
    assert payload["source_file"].startswith("docs/validation/")
    assert isinstance(payload["rows"], list)
    assert len(payload["rows"]) >= 1


def test_flag_cutover_matrix_doc_exists() -> None:
    text = FLAG_MATRIX_DOC.read_text(encoding="utf-8")
    assert "Safe manual demo" in text or "Profile 2" in text
    assert "MCP_GLOBAL_EXECUTION_ENABLED" in text
    assert "LANGGRAPH_ORCHESTRATION_ENABLED" in text
    assert "fan-out/fan-in" in text.lower() or "fan-out" in text


def test_demo_scenarios_readiness_doc_exists() -> None:
    text = DEMO_SCENARIOS_DOC.read_text(encoding="utf-8")
    for phrase in (
        "Failed login followed by success",
        "Brute-force SOP",
        "DNS beaconing",
        "Suspicious PowerShell",
        "MITRE-only without alert context",
        "Enrichment-only phishing",
        "Unsafe execution",
    ):
        assert phrase in text, phrase


def test_governance_regression_includes_validation_check() -> None:
    script = REGRESSION_SCRIPT.read_text(encoding="utf-8")
    assert "build_soc_validation_sheets.py --check" in script
    assert "test_soc_validation_package_phase10.py" in script


def test_validation_sheet_check_runs() -> None:
    result = subprocess.run(
        ["python3", str(VALIDATION_CHECK_SCRIPT), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
