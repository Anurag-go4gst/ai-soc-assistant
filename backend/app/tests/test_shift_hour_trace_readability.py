from __future__ import annotations

from app.spl.user_constraint_bindings import build_user_constraint_bindings

_WINEVENT_OFF_SHIFT = (
    "Run a Splunk search on the wineventlog index for Event ID 4624 (Successful Logon) "
    "originating from substation subnets outside normal shift hours."
)


def test_shift_hour_trace_does_not_mark_profile_hours_unsupported() -> None:
    bindings = build_user_constraint_bindings(_WINEVENT_OFF_SHIFT)
    reasons = [str(item.get("reason") or "") for item in bindings.unbound_constraints]
    assert not any("unsupported_slot:normal_shift" in reason for reason in reasons)
    trace = bindings.debug_trace.get("shift_hour_binding_trace") or {}
    assert trace.get("status") == "fixed_off_shift_hour_constraint_applied"
    off_shift = next(
        c for c in bindings.semantic_constraints if c.get("constraint_type") == "off_shift_filter"
    )
    assert off_shift.get("trace_note") == "fixed_off_shift_hour_constraint_applied"
