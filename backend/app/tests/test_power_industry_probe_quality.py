from __future__ import annotations

from scripts.power_industry_probe_quality import evaluate_row


def test_check_rejects_regulatory_spl_shape() -> None:
    row = {
        "status": "ok",
        "stress_axis": "regulatory_reporting + non_technical",
        "observed": {
            "answer_shape": "regulatory_knowledge",
            "signal_class": "unknown",
            "summary_excerpt": "CERT-In compliance guidance; verify with compliance because this is not legal authority.",
            "payload_has_spl": True,
            "card_has_spl": True,
        },
    }
    assert "regulatory_shape_returned_spl" in evaluate_row(row)


def test_check_rejects_payload_spl_dropped_from_card() -> None:
    row = {
        "status": "ok",
        "stress_axis": "out_of_catalog_protocol_hunt",
        "observed": {
            "answer_shape": "hunt",
            "signal_class": "protocol_command",
            "summary_excerpt": "Signal class: protocol command",
            "payload_has_spl": True,
            "card_has_spl": False,
        },
    }
    assert evaluate_row(row) == ["payload_spl_dropped_from_card"]


def test_check_accepts_visible_containment_shape() -> None:
    row = {
        "status": "ok",
        "stress_axis": "containment_action_request + safety_critical",
        "observed": {
            "answer_shape": "ir_containment_advisory",
            "signal_class": "unknown",
            "summary_excerpt": "IR / containment advisory with staged guidance and operations approval.",
            "payload_has_spl": False,
            "card_has_spl": False,
        },
    }
    assert evaluate_row(row) == []
