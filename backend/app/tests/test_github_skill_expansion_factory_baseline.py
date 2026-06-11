"""Phase 0B GitHub Skill Expansion Factory baseline validation."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.api.routes_knowledge import export_mapping_artifact

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
DISCOVERY_GENERATOR = SCRIPTS_DIR / "build_github_skill_discovery_index.py"
TRIAGE_SCRIPT = SCRIPTS_DIR / "score_github_skill_triage.py"
FACTORY_ARTIFACTS_SCRIPT = SCRIPTS_DIR / "build_github_skill_factory_artifacts.py"
CROSSWALK_PATH = REPO_ROOT / "docs" / "evals" / "soc_capability_crosswalk.json"

INTAKE_PATH = REPO_ROOT / "docs" / "skills" / "github_skill_intake_register.json"
DISCOVERY_PATH = REPO_ROOT / "docs" / "skills" / "github_skill_discovery_index.json"
TRIAGE_PATH = REPO_ROOT / "docs" / "skills" / "github_skill_triage_scores.json"
PROPOSED_PATH = REPO_ROOT / "docs" / "skills" / "proposed_use_cases_from_github.json"
STATUS_MATRIX_JSON = REPO_ROOT / "docs" / "skills" / "skill_enrichment_status_matrix.json"
PENDING_JSON = REPO_ROOT / "docs" / "skills" / "pending_skill_enrichment_backlog.json"

REQUIRED_GITHUB_SKILLS = {
    "detecting-rdp-brute-force-attacks",
    "triaging-security-alerts-in-splunk",
    "analyzing-email-headers-for-phishing-investigation",
    "hunting-for-anomalous-powershell-execution",
    "hunting-for-command-and-control-beaconing",
    "triaging-security-incident-with-ir-playbook",
    # WS2 T2.4 deferred-class intake batch (2026-06-11)
    "building-threat-intelligence-enrichment-in-splunk",
    "automating-ioc-enrichment",
    "performing-asset-criticality-scoring-for-vulns",
    "configuring-windows-event-logging-for-detection",
    "implementing-alert-fatigue-reduction",
    "analyzing-ransomware-encryption-mechanisms",
}


@pytest.fixture(scope="module")
def fixture_clone(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("github-skill-fixture")
    for skill_id, title, domain in (
        ("detecting-rdp-brute-force-attacks", "Detecting RDP Brute Force Attacks", "identity-access-management"),
        ("future-skill-candidate", "Future Skill Candidate", "soc-operations"),
    ):
        skill_dir = root / "skills" / skill_id
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"""---
name: {skill_id}
description: Defensive Splunk triage workflow for analysts.
domain: cybersecurity
subdomain: {domain}
tags:
  - splunk
  - blue-team
mitre_attack:
  - T1110.001
---
# {title}

## Overview
Defensive investigation guidance only.
This body must not appear in generated discovery artifacts.
""",
            encoding="utf-8",
        )
    return root


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS_DIR))
    spec.loader.exec_module(module)
    return module


def test_discovery_generator_works_against_fixture(fixture_clone: Path) -> None:
    module = _load_module(DISCOVERY_GENERATOR, "build_github_skill_discovery_index")
    warnings: list[str] = []
    payload = module.build_discovery_index(fixture_clone, warnings)

    assert payload["row_counts"]["skills"] >= 2
    skill_ids = {row["github_skill_id"] for row in payload["skills"]}
    assert "detecting-rdp-brute-force-attacks" in skill_ids
    assert "future-skill-candidate" in skill_ids
    accepted = payload["skills"]
    brute = next(row for row in accepted if row["github_skill_id"] == "detecting-rdp-brute-force-attacks")
    assert brute["review_status"] == "accepted_for_enrichment"
    assert brute["decision"] == "accept"
    rendered = json.dumps(payload)
    assert "This body must not appear" not in rendered
    assert "Defensive investigation guidance only" not in rendered


def test_discovery_generator_fails_clearly_without_clone() -> None:
    module = _load_module(DISCOVERY_GENERATOR, "build_github_skill_discovery_index_missing")
    exit_code = module.main(["--fixture-root", "/tmp/does-not-exist-ai-soc-factory-test"])
    assert exit_code == 1


def test_committed_discovery_artifact_schema() -> None:
    payload = json.loads(DISCOVERY_PATH.read_text(encoding="utf-8"))
    assert payload["schema_version"]
    assert payload["row_counts"]["skills"] >= 7
    assert payload["row_counts"]["accepted_for_enrichment"] == 12
    assert payload["row_counts"]["intake_register_records"] == 12
    skill_ids = {row["github_skill_id"] for row in payload["skills"]}
    assert REQUIRED_GITHUB_SKILLS.issubset(skill_ids)


def test_triage_artifact_schema_and_no_auto_accept() -> None:
    payload = json.loads(TRIAGE_PATH.read_text(encoding="utf-8"))
    assert payload["schema_version"]
    assert payload["scoring_model_version"]
    assert payload["row_counts"]["scores"] >= 7
    assert all(row.get("recommended_decision") != "accept" for row in payload["scores"])
    accepted_only = [
        row
        for row in payload["scores"]
        if row.get("recommended_decision") == "accept_for_enrichment_only"
    ]
    assert len(accepted_only) == 12


def test_proposed_use_cases_not_runtime_active() -> None:
    payload = json.loads(PROPOSED_PATH.read_text(encoding="utf-8"))
    assert payload["row_counts"]["proposed_use_cases"] >= 1
    for row in payload["proposed_use_cases"]:
        assert row["runtime_support_status"] != "runtime_active"
        assert row["runtime_support_status"] == "metadata_only"
        assert row.get("github_acceptance_not_runtime_activation") is True


def test_all_github_derived_rows_are_non_runtime() -> None:
    crosswalk = json.loads(CROSSWALK_PATH.read_text(encoding="utf-8"))
    for row in crosswalk["github_skill_rows"]:
        assert row["runtime_support_status"] != "runtime_active"
        assert row.get("runtime_skill") is False
        if row.get("decision") == "accept":
            assert row.get("acceptance_means") == "accepted_for_enrichment_only"
    for row in crosswalk.get("proposed_use_case_rows") or []:
        assert row.get("runtime_support_status") != "runtime_active"


def test_intake_register_reviewed_skills_have_decision_reason() -> None:
    intake = json.loads(INTAKE_PATH.read_text(encoding="utf-8"))
    for record in intake["records"]:
        assert record["github_skill_id"] in REQUIRED_GITHUB_SKILLS
        assert record.get("decision") in {"accept", "reject", "defer", "duplicate", "blocked", "needs_review"}
        if record.get("decision") in {"accept", "reject", "defer", "duplicate", "blocked"}:
            assert record.get("decision_reason")


def test_knowledge_exports_include_phase0b_artifacts() -> None:
    for artifact in (
        "github_skill_discovery_index",
        "github_skill_triage_scores",
        "proposed_use_cases_from_github",
        "skill_enrichment_status_matrix",
        "pending_skill_enrichment_backlog",
        "soc_capability_crosswalk",
    ):
        response = export_mapping_artifact(artifact, file_format="json")
        payload = json.loads(response.body)
        assert payload["artifact"] == artifact

    status_payload = json.loads(
        export_mapping_artifact("skill_enrichment_status_matrix", file_format="json").body
    )
    assert status_payload.get("export_kind") == "json_backed"

    backlog_payload = json.loads(
        export_mapping_artifact("pending_skill_enrichment_backlog", file_format="json").body
    )
    assert backlog_payload.get("export_kind") == "json_backed"


def test_crosswalk_includes_factory_visibility() -> None:
    crosswalk = json.loads(CROSSWALK_PATH.read_text(encoding="utf-8"))
    assert crosswalk.get("factory_visibility")
    assert crosswalk["row_counts"].get("discovery_skills", 0) >= 7
    assert crosswalk["row_counts"].get("triage_scores", 0) >= 7
    brute = next(
        row
        for row in crosswalk["github_skill_rows"]
        if row["github_skill_id"] == "detecting-rdp-brute-force-attacks"
    )
    assert brute["factory_visibility"]["discovery_present"] is True
    assert brute["factory_visibility"]["triage_recommended_decision"] == "accept_for_enrichment_only"


def test_no_runtime_chat_modules_touched() -> None:
    chat_routes = (REPO_ROOT / "backend" / "app" / "api" / "routes_chat.py").read_text(encoding="utf-8")
    assert "github_skill_discovery_index" not in chat_routes
    assert "build_github_skill_discovery_index" not in chat_routes


def test_factory_generators_check_against_committed_artifacts() -> None:
    for script in (DISCOVERY_GENERATOR, TRIAGE_SCRIPT, FACTORY_ARTIFACTS_SCRIPT):
        result = subprocess.run(
            [sys.executable, str(script), "--check"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr or result.stdout
