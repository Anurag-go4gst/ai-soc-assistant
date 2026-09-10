"""DET-validated hypothesis assessment against admitted SourceEvidence."""

from __future__ import annotations

from app.chat.hypothesis_assessment import (
    assess_hypotheses,
    public_hypothesis_lists,
    stable_hypothesis_items,
    validate_advisory_assessments,
)
from app.chat.contracts.investigation_outcome import derive_investigation_outcome
from app.synthesis.lab_runner import _build_deterministic_lab_draft
from app.synthesis.models import build_governed_synthesis_package
from app.actions.capability_policy import action_capability_for


H1 = "The executable itself is malicious."
H2 = "This is legitimate administrative activity."
H3 = "A legitimate administrative tool is being abused."


def _env(evidence_id: str, **preview: object) -> dict:
    return {
        "evidence_id": evidence_id,
        "source_type": "splunk_mcp",
        "collection_status": "collected",
        "result_count": 1,
        "fields_returned": list(preview),
        "preview_rows": [preview] if preview else [],
    }


def test_stable_ids_survive_reordering() -> None:
    first = stable_hypothesis_items([H1, H2, H3])
    prior = {"items": first}
    second = stable_hypothesis_items([H3, H1], prior)
    by_text = {item["text"]: item["hypothesis_id"] for item in second}
    assert by_text[H1] == "h1"
    assert by_text[H3] == "h3"


def test_support_requires_environment_refs_and_rationale() -> None:
    package = validate_advisory_assessments(
        hypotheses=[H1],
        advisory=[
            {
                "hypothesis_id": "h1",
                "assessment": "supported",
                "rationale": "Signed binary matches the process.",
                "supporting_source_refs": ["ev1"],
            }
        ],
        source_evidence=[_env("ev1", process="psexec.exe", signature_status="signed")],
    )
    assert package["items"][0]["assessment"] == "supported"
    supported, unconfirmed = public_hypothesis_lists(package)
    assert supported == [H1]
    assert unconfirmed == []


def test_weaken_case() -> None:
    package = validate_advisory_assessments(
        hypotheses=[H1, H2, H3],
        advisory=[
            {
                "hypothesis_id": "h1",
                "assessment": "weakened",
                "rationale": "Publisher signature reduces malware-binary premise.",
                "contradicting_source_refs": ["ev1"],
                "material_gap": "session versus abuse of legitimate tooling",
            }
        ],
        source_evidence=[_env("ev1", signature_status="signed", signer="Microsoft Corporation")],
    )
    item = package["items"][0]
    assert item["assessment"] == "weakened"
    assert item["public_state"] == "unconfirmed"
    supported, unconfirmed = public_hypothesis_lists(package)
    assert H1 in unconfirmed
    assert supported == []


def test_neutral_irrelevant_evidence_does_not_change_state() -> None:
    prior = validate_advisory_assessments(
        hypotheses=[H2],
        advisory=None,
        source_evidence=[_env("ev1", process="psexec.exe")],
    )
    package = validate_advisory_assessments(
        hypotheses=[H2],
        advisory=[
            {
                "hypothesis_id": "h1",
                "assessment": "unconfirmed",
                "rationale": "NTP offset is unrelated to this investigation.",
                "supporting_source_refs": ["ev2"],
            }
        ],
        source_evidence=[
            _env("ev1", process="psexec.exe"),
            _env("ev2", dest="time.windows.com", dest_port=123),
        ],
        prior=prior,
    )
    assert package["items"][0]["assessment"] == "unconfirmed"
    assert package["items"][0]["public_state"] == "unconfirmed"


def test_no_evidence_does_not_alter_hypotheses() -> None:
    package = validate_advisory_assessments(
        hypotheses=[H1, H2],
        advisory=[
            {
                "hypothesis_id": "h1",
                "assessment": "supported",
                "rationale": "should be ignored",
                "supporting_source_refs": ["ev1"],
            }
        ],
        source_evidence=[],
    )
    assert [item["assessment"] for item in package["items"]] == ["unconfirmed", "unconfirmed"]
    assert public_hypothesis_lists(package) == ([], [H1, H2])


def test_rag_only_cannot_promote() -> None:
    package = validate_advisory_assessments(
        hypotheses=[H1],
        advisory=[
            {
                "hypothesis_id": "h1",
                "assessment": "supported",
                "rationale": "Playbook mentions living-off-the-land.",
                "supporting_source_refs": ["ev_rag"],
            }
        ],
        source_evidence=[
            {
                "evidence_id": "ev_rag",
                "source_type": "rag",
                "plan_step_ref": "rag",
                "collection_status": "collected",
                "result_count": 1,
                "preview_rows": [{"title": "LOLBins"}],
            }
        ],
    )
    assert package["items"][0]["assessment"] == "unconfirmed"


def test_user_claim_cannot_promote() -> None:
    package = validate_advisory_assessments(
        hypotheses=[H1],
        advisory=[
            {
                "hypothesis_id": "h1",
                "assessment": "supported",
                "rationale": "Analyst said the host is compromised.",
                "supporting_source_refs": ["ev_user"],
            }
        ],
        source_evidence=[
            {
                "evidence_id": "ev_user",
                "source_type": "manual",
                "collection_status": "collected",
                "preview_rows": [{"claim": "compromised"}],
            }
        ],
    )
    assert package["items"][0]["assessment"] == "unconfirmed"


def test_failed_tool_is_not_negative_evidence() -> None:
    package = validate_advisory_assessments(
        hypotheses=[H2],
        advisory=[
            {
                "hypothesis_id": "h1",
                "assessment": "weakened",
                "rationale": "Search failed so the admin hypothesis is weaker.",
                "contradicting_source_refs": ["ev_fail"],
            }
        ],
        source_evidence=[
            {
                "evidence_id": "ev_fail",
                "source_type": "splunk_mcp",
                "collection_status": "failed",
                "tool_name": "splunk_run_query",
            }
        ],
    )
    assert package["items"][0]["assessment"] == "unconfirmed"


def test_absence_of_evidence_is_not_contradiction() -> None:
    package = validate_advisory_assessments(
        hypotheses=[H1],
        advisory=[
            {
                "hypothesis_id": "h1",
                "assessment": "weakened",
                "rationale": "No malware hash was returned.",
                "contradicting_source_refs": [],
            }
        ],
        source_evidence=[_env("ev1", process="psexec.exe")],
    )
    assert package["items"][0]["assessment"] == "unconfirmed"


def test_no_revision_needed_when_second_read_is_confirmatory() -> None:
    first = validate_advisory_assessments(
        hypotheses=[H3, H2],
        advisory=[
            {
                "hypothesis_id": "h1",
                "assessment": "supported",
                "rationale": "Persistence and C2 destination confirm abuse.",
                "supporting_source_refs": ["ev1"],
            }
        ],
        source_evidence=[_env("ev1", dest="203.0.113.77", action="scheduled_task_created")],
    )
    second = validate_advisory_assessments(
        hypotheses=[H3, H2],
        advisory=[
            {
                "hypothesis_id": "h1",
                "assessment": "supported",
                "rationale": "Additional confirmatory rows do not change the assessment.",
                "supporting_source_refs": ["ev1", "ev2"],
            }
        ],
        source_evidence=[
            _env("ev1", dest="203.0.113.77", action="scheduled_task_created"),
            _env("ev2", dest="203.0.113.77", bytes=12),
        ],
        prior=first,
    )
    assert first["items"][0]["assessment"] == "supported"
    assert second["items"][0]["assessment"] == "supported"
    assert "did not materially change" in second["evolution_summary"]


def test_generalization_sequences_are_evidence_bound() -> None:
    cases = [
        (
            ["malicious installer", "approved maintenance"],
            [_env("ev1", signature_status="signed", product_name="PsExec")],
            "weakened",
            "contradicting_source_refs",
        ),
        (
            ["account compromise", "benign travel"],
            [_env("ev1", src_country="FR", usual_country="FR", vpn="corporate")],
            "unconfirmed",
            "supporting_source_refs",
        ),
        (
            ["exfiltration", "sanctioned backup"],
            [_env("ev1", dest="backup.corp.local", bytes=940112, change_ticket="CHG-9")],
            "supported",
            "supporting_source_refs",
        ),
        (
            ["unauthorized scheduled task", "approved maintenance"],
            [_env("ev1", action="scheduled_task_created", author="svc.patch")],
            "unconfirmed",
            "supporting_source_refs",
        ),
        (
            ["suspicious external connection", "expected update service"],
            [_env("ev1", dest="203.0.113.77", dest_port=443)],
            "unconfirmed",
            "supporting_source_refs",
        ),
    ]
    for hypotheses, evidence, wanted, ref_field in cases:
        refs = [str(item["evidence_id"]) for item in evidence]
        advisory = [
            {
                "hypothesis_id": "h1",
                "assessment": wanted,
                "rationale": "Grounded in admitted environment evidence.",
                "supporting_source_refs": refs if ref_field == "supporting_source_refs" else [],
                "contradicting_source_refs": refs if ref_field == "contradicting_source_refs" else [],
            }
        ]
        package = validate_advisory_assessments(
            hypotheses=hypotheses,
            advisory=advisory,
            source_evidence=evidence,
        )
        assert package["items"][0]["assessment"] == wanted, hypotheses


def test_outcome_uses_assessments_not_substring_copy() -> None:
    package = validate_advisory_assessments(
        hypotheses=[H1, H3],
        advisory=[
            {
                "hypothesis_id": "h1",
                "assessment": "weakened",
                "rationale": "Signed admin binary.",
                "contradicting_source_refs": ["ev1"],
            },
            {
                "hypothesis_id": "h2",
                "assessment": "supported",
                "rationale": "Persistence plus unusual destination.",
                "supporting_source_refs": ["ev2"],
            },
        ],
        source_evidence=[
            _env("ev1", signature_status="signed"),
            _env("ev2", dest="203.0.113.77", action="scheduled_task_created"),
        ],
    )
    outcome = derive_investigation_outcome(
        investigation_plan={"hypotheses": [H1, H3]},
        evidence_state={"obtained": ["endpoint", "persistence"]},
        evidence_sufficiency={"status": "SUFFICIENT", "missing": []},
        structured_context={"structured_facts": []},
        hypothesis_assessments=package,
    )
    assert outcome.supported_hypotheses == [H3]
    assert H1 in outcome.unconfirmed_hypotheses
    assert "weakened" not in str(outcome.supported_hypotheses)
    evolution = outcome.provenance["hypothesis_assessment"]["evolution_summary"]
    assert "malicious" in evolution.lower()
    assert "h1" not in evolution


def test_synthesis_draft_includes_evolution_summary() -> None:
    package = validate_advisory_assessments(
        hypotheses=[H1, H3],
        advisory=[
            {
                "hypothesis_id": "h1",
                "assessment": "weakened",
                "rationale": "Signed administrative binary.",
                "contradicting_source_refs": ["ev1"],
            }
        ],
        source_evidence=[_env("ev1", signature_status="signed")],
    )
    outcome = derive_investigation_outcome(
        investigation_plan={"hypotheses": [H1, H3]},
        evidence_state={"obtained": ["endpoint"]},
        hypothesis_assessments=package,
        structured_context={"structured_facts": [{"statement": "psexec signed", "source_refs": ["ev1"]}]},
    )
    synth = build_governed_synthesis_package(
        structured_context={"trace_id": "t", "structured_facts": []},
        source_evidence=[_env("ev1", signature_status="signed")],
        mitre_mappings=[],
        action_capability=action_capability_for(None, None),
        investigation_outcome=outcome.model_dump(mode="json"),
    )
    draft = _build_deterministic_lab_draft(
        package=synth,
        structured_context={"structured_facts": []},
        source_evidence=[_env("ev1", signature_status="signed")],
        spl_validation=None,
        mitre_mappings=[],
        severity_label=None,
    )
    assert "signed administrative binary" in draft["analyst_summary"].lower()


def test_assess_hypotheses_uses_provider_output() -> None:
    result = assess_hypotheses(
        hypotheses=[H1],
        source_evidence=[_env("ev1", signature_status="signed")],
        raw_output_provider=lambda: (
            '{"hypothesis_assessments":[{"hypothesis_id":"h1","assessment":"weakened",'
            '"rationale":"Signed binary.","contradicting_source_refs":["ev1"]}]}'
        ),
    )
    assert result["items"][0]["assessment"] == "weakened"
    assert result["trace"]["attempted"] is True
