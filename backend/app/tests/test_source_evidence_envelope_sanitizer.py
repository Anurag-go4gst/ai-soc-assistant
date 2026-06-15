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
