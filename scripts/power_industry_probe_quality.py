"""Quality gates shared by the three disjoint power-industry probe runners."""

from __future__ import annotations

from typing import Any


_SHAPE_EXPECTATIONS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("containment_action_request", "ir_containment_advisory", ("containment advisory", "staged guidance")),
    ("regulatory_reporting", "regulatory_knowledge", ("cert-in", "legal authority", "compliance")),
    ("log_source_health", "source_health", ("source health", "blind spot", "ingestion")),
    ("baselining_request", "baselining", ("baseline", "descriptive", "timechart")),
    ("incident_timeline", "timeline_reconstruction", ("timeline", "chronolog", "caus")),
    ("insider_threat", "insider_dlp", ("insider", "exfil", "data theft")),
    ("supply_chain_integrity", "supply_chain_firmware_integrity", ("signing certificate", "supply-chain", "vendor")),
    ("process_aware_anomaly", "process_aware_ot", ("grid-physics", "grid operator", "grid operations", "agc")),
    ("ti_advisory_to_detection_mapping", "ti_advisory_mapping", ("advisory", "logged today", "hunt gap")),
)


def evaluate_row(row: dict[str, Any]) -> list[str]:
    if row.get("status") != "ok":
        return ["pipeline_error"]
    observed = row.get("observed") or {}
    summary = str(observed.get("summary_excerpt") or "").lower()
    violations: list[str] = []

    signal_class = str(observed.get("signal_class") or "unknown")
    if signal_class != "unknown" and (
        "no specialised ot family" in summary
        or "firewall, dns, proxy, and endpoint telemetry" in summary
    ):
        violations.append(f"recognised_signal_returned_generic:{signal_class}")

    if observed.get("payload_has_spl") and not observed.get("card_has_spl"):
        violations.append("payload_spl_dropped_from_card")

    stress = str(row.get("stress_axis") or "")
    for token, expected_shape, markers in _SHAPE_EXPECTATIONS:
        if token not in stress:
            continue
        if observed.get("answer_shape") != expected_shape:
            violations.append(
                f"answer_shape_mismatch:expected={expected_shape}:actual={observed.get('answer_shape')}"
            )
        if not any(marker in summary for marker in markers):
            violations.append(f"answer_shape_not_visible:{expected_shape}")
        if expected_shape == "regulatory_knowledge" and observed.get("payload_has_spl"):
            violations.append("regulatory_shape_returned_spl")
        break
    return violations


def collect_violations(result: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for row in result.get("rows") or []:
        reasons = evaluate_row(row)
        if reasons:
            failures.append({"question_id": row.get("question_id"), "reasons": reasons})
    return failures
