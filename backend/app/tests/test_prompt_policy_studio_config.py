"""P4 — Studio configuration model: validation, redaction, permissions, rollback."""

from __future__ import annotations

import pytest

from app.llm.policy.evaluation import contract_for_role
from app.llm.policy.registry import ROLE_CONTRACTS
from app.llm.policy.studio_config import (
    EDITABLE_FIELDS,
    IMMUTABLE_FIELDS,
    MAX_INSTRUCTION_CHARS,
    STUDIO_CONFIG_VERSION,
    StudioPermissionError,
    StudioValidationError,
    build_audit_entry,
    can_activate_draft,
    redact,
    require_permission,
    validate_draft,
)

_DRAFTER = {"prompt_studio_draft"}
_ACTIVATOR = {"prompt_studio_draft", "prompt_studio_activate"}


def _valid(**over):
    base = {"system_instruction": "A new stable governance rule for this role."}
    base.update(over)
    return base


def test_config_version_is_declared() -> None:
    assert STUDIO_CONFIG_VERSION == "prompt_studio_config_v1"


# --- allowlist, not denylist ------------------------------------------------


def test_editable_and_immutable_sets_do_not_overlap() -> None:
    assert not set(EDITABLE_FIELDS) & set(IMMUTABLE_FIELDS)


@pytest.mark.parametrize("field_name", IMMUTABLE_FIELDS)
def test_immutable_fields_are_refused(field_name: str) -> None:
    """Authority, validator, schema and posture must not be Studio-editable."""
    with pytest.raises(StudioValidationError, match="not editable"):
        validate_draft("shape_advisor", {field_name: "x"}, granted_permissions=_DRAFTER)


def test_unknown_field_is_refused_not_ignored() -> None:
    """Silently dropping an edit is how an operator believes a change took effect."""
    with pytest.raises(StudioValidationError, match="unknown draft field"):
        validate_draft("shape_advisor", {"temperature": 0.9}, granted_permissions=_DRAFTER)


@pytest.mark.parametrize("field_name", EDITABLE_FIELDS)
def test_editable_fields_are_accepted(field_name: str) -> None:
    value = "1.2.3" if field_name == "prompt_version" else "governed value"
    result = validate_draft("shape_advisor", {field_name: value}, granted_permissions=_DRAFTER)
    assert result.admissible is True
    assert result.changed_fields == (field_name,)


def test_authority_cannot_be_granted_through_the_studio() -> None:
    with pytest.raises(StudioValidationError):
        validate_draft(
            "shape_advisor",
            {"allowed_authority": ["mcp_invocation_authority"]},
            granted_permissions=_DRAFTER,
        )


# --- validation without persistence, and no secret echo ---------------------


def test_draft_is_validated_without_persisting() -> None:
    before = ROLE_CONTRACTS["shape_advisor"].system_instruction
    validate_draft("shape_advisor", _valid(), granted_permissions=_DRAFTER)
    assert ROLE_CONTRACTS["shape_advisor"].system_instruction == before


def test_preview_is_redacted_and_never_echoes_the_value() -> None:
    secret_ish = "a very specific instruction body that must not come back"
    result = validate_draft(
        "shape_advisor", {"system_instruction": secret_ish}, granted_permissions=_DRAFTER
    )
    assert secret_ish not in str(result.redacted_preview)
    assert result.redacted_preview["system_instruction"] == f"<{len(secret_ish)} chars>"


def test_redact_never_returns_the_input() -> None:
    assert redact("supersecret") == "<11 chars>"


@pytest.mark.parametrize(
    "payload",
    [
        "Authorization: Bearer sk_live_ABCDEFGHIJKLMNOPQRST",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0",
        'use {"api_key":"abcdef1234567890"} for the call',
    ],
)
def test_credential_material_in_a_draft_is_refused(payload: str) -> None:
    with pytest.raises(StudioValidationError, match="credential material"):
        validate_draft(
            "shape_advisor", {"system_instruction": payload}, granted_permissions=_DRAFTER
        )


def test_validation_error_does_not_repeat_the_offending_secret() -> None:
    secret = "Bearer sk_live_ABCDEFGHIJKLMNOPQRST"
    with pytest.raises(StudioValidationError) as exc:
        validate_draft("shape_advisor", {"system_instruction": secret}, granted_permissions=_DRAFTER)
    assert secret not in str(exc.value)


# --- size and format limits -------------------------------------------------


def test_oversized_instruction_is_refused() -> None:
    with pytest.raises(StudioValidationError, match="exceeds"):
        validate_draft(
            "shape_advisor",
            {"system_instruction": "x" * (MAX_INSTRUCTION_CHARS + 1)},
            granted_permissions=_DRAFTER,
        )


def test_blank_instruction_is_refused() -> None:
    with pytest.raises(StudioValidationError, match="must not be blank"):
        validate_draft("shape_advisor", {"system_instruction": "   "}, granted_permissions=_DRAFTER)


def test_empty_draft_is_refused() -> None:
    with pytest.raises(StudioValidationError, match="empty draft"):
        validate_draft("shape_advisor", {}, granted_permissions=_DRAFTER)


@pytest.mark.parametrize("bad_version", ["v1", "1.0", "latest", "1.0.0-rc1"])
def test_non_semver_prompt_version_is_refused(bad_version: str) -> None:
    with pytest.raises(StudioValidationError, match="semver"):
        validate_draft(
            "shape_advisor", {"prompt_version": bad_version}, granted_permissions=_DRAFTER
        )


# --- permissions ------------------------------------------------------------


def test_drafting_requires_the_draft_permission() -> None:
    with pytest.raises(StudioPermissionError, match="prompt_studio_draft"):
        validate_draft("shape_advisor", _valid(), granted_permissions={"prompt_studio_read"})


def test_read_permission_alone_cannot_activate() -> None:
    allowed, reason = can_activate_draft(
        "shape_advisor",
        granted_permissions={"prompt_studio_read", "prompt_studio_draft"},
        eval_allows_activation=True,
    )
    assert allowed is False
    assert "prompt_studio_activate" in reason


def test_drafting_and_activating_are_separate_permissions() -> None:
    """The person who writes a prompt should not be the only gate on shipping it."""
    assert "prompt_studio_draft" != "prompt_studio_activate"
    validate_draft("shape_advisor", _valid(), granted_permissions=_DRAFTER)
    allowed, _ = can_activate_draft(
        "shape_advisor", granted_permissions=_DRAFTER, eval_allows_activation=True
    )
    assert allowed is False


def test_unknown_action_is_refused() -> None:
    with pytest.raises(StudioValidationError, match="unknown studio action"):
        require_permission(_ACTIVATOR, "delete_everything")


# --- activation still defers to the evaluation gate -------------------------


def test_studio_cannot_bypass_the_evaluation_contract() -> None:
    allowed, reason = can_activate_draft(
        "shape_advisor", granted_permissions=_ACTIVATOR, eval_allows_activation=False
    )
    assert allowed is False
    assert reason == "prompt_evaluation_contract_refused_activation"


@pytest.mark.parametrize("role_id", sorted(ROLE_CONTRACTS))
def test_no_role_can_be_activated_through_the_studio_today(role_id: str) -> None:
    """Every role is NOT_RUN_LIVE, so the eval gate refuses every activation."""
    eval_allows, _ = contract_for_role(role_id).can_activate()
    allowed, _ = can_activate_draft(
        role_id, granted_permissions=_ACTIVATOR, eval_allows_activation=eval_allows
    )
    assert allowed is False


# --- B-owned roles warn -----------------------------------------------------


@pytest.mark.parametrize("role_id", ["spl_advisory_generator", "spl_repair"])
def test_drafting_a_b_owned_role_warns_about_ownership(role_id: str) -> None:
    result = validate_draft(role_id, _valid(), granted_permissions=_DRAFTER)
    assert any("B_SPL" in w for w in result.warnings)


# --- audit history ----------------------------------------------------------


def test_activation_audit_requires_a_rollback_target() -> None:
    with pytest.raises(StudioValidationError, match="rollback target"):
        build_audit_entry(
            entry_id="a1",
            role_id="shape_advisor",
            action="activated",
            actor="operator",
            prompt_version_before="1.0.0",
            prompt_version_after="1.1.0",
            stable_prefix_hash_before="a" * 64,
            stable_prefix_hash_after="b" * 64,
            rollback_target_version="",
        )


def test_audit_entry_records_both_versions_and_both_hashes() -> None:
    entry = build_audit_entry(
        entry_id="a2",
        role_id="shape_advisor",
        action="activated",
        actor="operator",
        prompt_version_before="1.0.0",
        prompt_version_after="1.1.0",
        stable_prefix_hash_before="a" * 64,
        stable_prefix_hash_after="b" * 64,
        rollback_target_version="1.0.0",
    )
    assert entry.prompt_version_before == "1.0.0"
    assert entry.prompt_version_after == "1.1.0"
    assert entry.stable_prefix_hash_before != entry.stable_prefix_hash_after
    assert entry.rollback_target_version == "1.0.0"
    assert entry.at.endswith("+00:00")


def test_audit_entry_is_immutable() -> None:
    entry = build_audit_entry(
        entry_id="a3",
        role_id="shape_advisor",
        action="draft_validated",
        actor="operator",
        prompt_version_before="1.0.0",
        prompt_version_after="1.0.0",
        stable_prefix_hash_before="a" * 64,
        stable_prefix_hash_after="a" * 64,
        rollback_target_version="1.0.0",
    )
    with pytest.raises(Exception):
        entry.actor = "someone else"  # type: ignore[misc]
