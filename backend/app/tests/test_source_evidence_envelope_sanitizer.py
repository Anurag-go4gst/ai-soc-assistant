from __future__ import annotations

from app.evidence.source_evidence import build_source_evidence

JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.sigsigsigsig"


def test_envelope_rows_are_sanitized() -> None:
    # Live executed-search rows arrive on the envelope; they must be redacted
    # like the legacy preview path (regression guard for the envelope bypass).
    execution = {
        "status": "executed",
        "result_count": 1,
        "selected_mcp_server": "mcp_splunk",
        "selected_mcp_tool": "splunk_run_query",
        "executed_spl": "search index=pgcil_soc",
        "splunk_result_envelope": {
            "status": "ok",
            "schema_confirmed": True,
            "fields": ["host", "raw_event"],
            "rows": [{"host": "DB-PROD-02", "raw_event": f"login token {JWT} accepted"}],
            "warnings": [],
        },
    }
    evidence = build_source_evidence(
        trace_id="t-env",
        query="show me the events",
        selected_skill="spl_generation",
        spl_validation={"normalized_spl": "search index=pgcil_soc earliest=-1h latest=now"},
        execution=execution,
    )
    splunk = next(item for item in evidence if item["source_type"] == "splunk_mcp")
    serialized = str(splunk["preview_rows"])
    assert JWT not in serialized
    assert "[redacted]" in serialized


def test_reference_dataset_evidence_skips_keyword_scrub_but_keeps_secret_backstop() -> None:
    from app.evidence.source_evidence import build_provider_source_evidence

    evidence = build_provider_source_evidence(
        trace_id="trace-ref",
        source_type="reference_dataset",
        source_name="reference_registry",
        collection_status="collected",
        query_or_request_summary="T1110.003",
        result_count=1,
        preview_rows=[{"name": "Password Spraying", "description": "Uses a single password."}],
    )
    row = evidence["preview_rows"][0]
    assert row["name"] == "Password Spraying"
    assert "single password" in row["description"]


def test_non_reference_evidence_still_scrubs_sensitive_keywords() -> None:
    from app.evidence.source_evidence import build_provider_source_evidence

    evidence = build_provider_source_evidence(
        trace_id="trace-mcp",
        source_type="splunk_mcp",
        source_name="splunk",
        collection_status="collected",
        query_or_request_summary=None,
        result_count=1,
        preview_rows=[{"note": "user password reset requested"}],
    )
    row = evidence["preview_rows"][0]
    assert "[redacted]" in row["note"]
    assert "password" not in row["note"].lower()


def test_reference_dataset_evidence_does_not_trip_sensitivity_flags() -> None:
    # Live regression 2026-07-05: once keyword_scrub was correctly disabled for
    # reference-dataset technique text, _sensitivity_flags (a second, redundant
    # scan of the same rows) re-flagged the very words we deliberately kept,
    # which fed context_sufficiency's "sensitive leak" rule and forced every
    # ATT&CK/ATLAS taxonomy answer into blocked_by_policy + human review.
    from app.evidence.source_evidence import build_provider_source_evidence

    evidence = build_provider_source_evidence(
        trace_id="trace-ref-2",
        source_type="reference_dataset",
        source_name="reference_registry",
        collection_status="collected",
        query_or_request_summary="T1531",
        result_count=1,
        preview_rows=[
            {
                "name": "Account Access Removal",
                "description": "Adversaries may change credentials or revoke access to accounts.",
            }
        ],
    )
    assert evidence["sensitivity_flags"] == []


def test_non_reference_evidence_still_scrubs_row_text_before_sensitivity_check() -> None:
    # Unchanged prior behavior (not this fix's concern): non-reference rows are
    # scrubbed BEFORE _sensitivity_flags runs, so the flag itself stays empty
    # (the pattern it looks for was already replaced) — the actual protection
    # is the row text, asserted here and by the other non-reference test above.
    from app.evidence.source_evidence import build_provider_source_evidence

    evidence = build_provider_source_evidence(
        trace_id="trace-mcp-2",
        source_type="splunk_mcp",
        source_name="splunk",
        collection_status="collected",
        query_or_request_summary=None,
        result_count=1,
        preview_rows=[{"note": "user password reset requested"}],
    )
    assert "[redacted]" in evidence["preview_rows"][0]["note"]
    assert evidence["sensitivity_flags"] == []
