"""Stage 3K-Q4A coverage drafter CLI tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.coverage.coverage_models import CoverageGovernance, CoverageReadiness, PatternCoverageEntry
RUNTIME_MANIFEST = Path(__file__).resolve().parents[3] / "backend" / "app" / "coverage" / "pattern_coverage_v1.json"

from deterministic import draft_entry_deterministic
from draft_schema import CoverageDraftDocument
from io_utils import assert_not_manifest_path, draft_output_path, resolve_draft_path, write_draft_document
from llm_assist import assert_instruct_only, draft_entry_with_llm
from registries import DRAFTS_DIR, load_registry_snapshot
from validator import validate_draft_entry

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_deterministic_draft_validates_for_known_malicious_ips() -> None:
    snapshot = load_registry_snapshot()
    entry = draft_entry_deterministic(
        "Which hosts contacted known malicious IPs today?",
        "q0.q004",
        "ioc_correlation",
        snapshot,
    )
    errors, _warnings = validate_draft_entry(entry, snapshot)
    assert entry.coverage_group == "ioc_dependent"
    assert entry.lookup_ref == "known_bad_ip"
    assert not errors


def test_unknown_template_ref_rejected() -> None:
    snapshot = load_registry_snapshot()
    entry = _minimal_entry(template_ref="not_a_real_template")
    errors, _ = validate_draft_entry(entry, snapshot)
    assert any("unknown_template_ref" in item for item in errors)


def test_sample_only_template_ref_rejected() -> None:
    snapshot = load_registry_snapshot()
    entry = _minimal_entry(template_ref="sample_auth_failed_login_top_users_tstats")
    errors, _ = validate_draft_entry(entry, snapshot)
    assert any("sample_only_template_not_promoted" in item for item in errors)


def test_unknown_detection_ref_rejected() -> None:
    snapshot = load_registry_snapshot()
    entry = _minimal_entry(detection_ref="evil.detection")
    errors, _ = validate_draft_entry(entry, snapshot)
    assert any("unknown_detection_ref" in item for item in errors)


def test_unvetted_detection_ref_rejected() -> None:
    snapshot = load_registry_snapshot()
    entry = _minimal_entry(detection_ref="soc.c2.unvetted")
    errors, _ = validate_draft_entry(entry, snapshot)
    assert any("unvetted_detection_ref" in item for item in errors)


def test_unknown_lookup_ref_rejected() -> None:
    snapshot = load_registry_snapshot()
    entry = _minimal_entry(lookup_ref="fake_lookup")
    errors, _ = validate_draft_entry(entry, snapshot)
    assert any("unknown_lookup_ref" in item for item in errors)


def test_dependency_missing_allows_unknown_evidence_with_blocker() -> None:
    snapshot = load_registry_snapshot()
    entry = _minimal_entry(
        readiness=CoverageReadiness.DEPENDENCY_MISSING,
        evidence_contract_ref="not.in.catalog",
        expected_blockers=["missing_dependency:evidence_contract_ref"],
    )
    errors, _ = validate_draft_entry(entry, snapshot)
    assert not errors


def test_all_governance_flags_false_enforced() -> None:
    snapshot = load_registry_snapshot()
    entry = _minimal_entry()
    entry.governance.execution_authorized = True
    errors, _ = validate_draft_entry(entry, snapshot)
    assert any("execution_authorized_must_be_false" in item for item in errors)


def test_reasoning_model_rejected() -> None:
    with pytest.raises(ValueError, match="Reasoning"):
        assert_instruct_only(model_family="foundation-sec-reasoning", provider="cisco")


def test_fake_instruct_provider_output_validated_before_write(tmp_path: Path) -> None:
    snapshot = load_registry_snapshot()
    raw = (_FIXTURES / "llm_dga_entry.json").read_text(encoding="utf-8")

    entry, disagreements = draft_entry_with_llm(
        "Which DNS queries look like DGA activity?",
        "q0.q007",
        "dns_beaconing_dga_behavior",
        snapshot,
        llm_raw_output_provider=lambda: raw,
        model_family="instruct",
        provider="stub",
    )
    errors, _ = validate_draft_entry(entry, snapshot)
    assert entry.detection_ref == "soc.dga.v1"
    assert not errors
    assert isinstance(disagreements, list)


def test_drafter_writes_only_under_drafts_dir(tmp_path: Path) -> None:
    snapshot = load_registry_snapshot()
    entry = draft_entry_deterministic(
        "Which hosts contacted known malicious IPs today?",
        "q0.q004",
        "ioc_correlation",
        snapshot,
    )
    out = tmp_path / "draft_test.json"
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    # Use real drafts dir for resolve_draft_path guard
    target = draft_output_path(entry.question)
    document = CoverageDraftDocument(entry=entry)
    written = write_draft_document(document, target)
    assert DRAFTS_DIR.resolve() in written.resolve().parents
    written.unlink(missing_ok=True)


def test_refuses_manifest_path_as_output() -> None:
    with pytest.raises(ValueError, match="Refusing"):
        assert_not_manifest_path(RUNTIME_MANIFEST)


def test_resolve_draft_path_rejects_outside_drafts(tmp_path: Path) -> None:
    outside = tmp_path / "outside.json"
    with pytest.raises(ValueError, match="must be under"):
        resolve_draft_path(outside)


def test_drafter_cli_never_modifies_runtime_manifest(tmp_path: Path) -> None:
    before = RUNTIME_MANIFEST.read_text(encoding="utf-8")
    snapshot = load_registry_snapshot()
    entry = draft_entry_deterministic(
        "What happened for this notable?",
        "q0.q045",
        "case_state_lookup",
        snapshot,
    )
    target = draft_output_path(entry.question)
    write_draft_document(CoverageDraftDocument(entry=entry), target)
    after = RUNTIME_MANIFEST.read_text(encoding="utf-8")
    assert before == after
    target.unlink(missing_ok=True)


def _minimal_entry(**overrides: object) -> PatternCoverageEntry:
    base = {
        "coverage_id": "cov.test.minimal",
        "question_ref": "q0.q999",
        "question": "Test question?",
        "coverage_group": "template_only",
        "primary_skill": "aggregate_and_rank",
        "sub_invocations": [],
        "route_plan_shape": {
            "route_status": "route_ready",
            "primary_skill": "aggregate_and_rank",
            "pattern_id": "test",
            "operation_type": "top_n",
            "parameters": {},
        },
        "template_ref": None,
        "lookup_ref": None,
        "detection_family": None,
        "detection_ref": None,
        "evidence_contract_ref": "ranked_entities:user:failed_login_count",
        "readiness": CoverageReadiness.COE_SYNTHETIC_FIXTURE,
        "clarification_required": [],
        "expected_route_status": "route_ready",
        "expected_blockers": [],
        "governance": CoverageGovernance(),
        "notes": "",
    }
    base.update(overrides)
    return PatternCoverageEntry.model_validate(base)
