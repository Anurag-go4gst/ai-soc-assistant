from __future__ import annotations

from app.splunk.spl_services import optimize_spl


def test_optimizer_uses_revalidation_approved_not_execution_eligible() -> None:
    result = optimize_spl("search index=pgcil_soc sourcetype=pgcil:auth | sort - count")

    assert "execution_eligible" not in result
    assert "revalidation_approved" in result
    assert isinstance(result["revalidation_approved"], bool)
