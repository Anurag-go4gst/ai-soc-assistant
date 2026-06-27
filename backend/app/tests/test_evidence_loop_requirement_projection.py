from __future__ import annotations

from app.chat.pipeline import _loop_required_produces


def test_evidence_loop_returns_to_plan_for_missing_lookup() -> None:
    requirements = _loop_required_produces(
        {
            "row_authority_summary": {
                "row_authority_status": "exact_known_needs_lookup",
                "blockers": ["lookup_artifact_required"],
            }
        }
    )

    assert requirements == ["lookup_dependency"]


def test_evidence_loop_returns_to_plan_for_missing_source_profile() -> None:
    requirements = _loop_required_produces(
        {
            "source_profile_binding_summary": {
                "environment_kb_is_telemetry": False,
                "source_profile_bindings_missing": [
                    {"profile_key": "ot_network_index", "slot": "index"},
                ],
            }
        }
    )

    assert requirements == ["source_profile"]


def test_evidence_loop_carries_missing_required_evidence() -> None:
    requirements = _loop_required_produces(
        {
            "missing_required_evidence": ["mfa_status", "post_login_activity"],
            "evidence_needs": ["mfa_status"],
        }
    )

    assert requirements == ["mfa_status", "post_login_activity"]


def test_evidence_loop_degrades_when_required_mcp_disabled() -> None:
    requirements = _loop_required_produces(
        {
            "mcp_allowed": None,
            "row_authority_summary": {
                "row_authority_status": "exact_known_needs_detection_binding",
            },
            "source_profile_binding_summary": {
                "source_profile_bindings_missing": [
                    {"profile_key": "vpn_index", "slot": "vpn_index"},
                ],
            },
        }
    )

    assert requirements == ["detection_binding", "source_profile"]
