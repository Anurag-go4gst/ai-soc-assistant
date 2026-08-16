"""Plan 8 SPL1 — negative controls for silent mandatory-constraint loss."""

from __future__ import annotations

from app.spl.rqc_constraint_preservation import apply_rqc_constraint_preservation


def test_service_account_constraint_cannot_disappear() -> None:
    rqc = {
        "time_scope": "earliest=-24h latest=now",
        "entities": {"account_type": "service_account", "source_ip": ["203.0.113.24"]},
    }
    validation = {
        "approved": True,
        "normalized_spl": (
            "search index=pgcil_soc sourcetype=pgcil:auth src=203.0.113.24 "
            "earliest=-24h latest=now | stats count by src | head 50"
        ),
        "reject_reasons": [],
    }
    updated = apply_rqc_constraint_preservation(
        validation,
        spl=validation["normalized_spl"],
        resolved_query_contract=rqc,
    )
    assert updated["approved"] is False
    assert updated["normalized_spl"] is None
    assert "rqc_constraint_dropped:account_type" in updated["reject_reasons"]
