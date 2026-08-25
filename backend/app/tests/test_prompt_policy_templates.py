"""P4 PP5 — prompt hashing, stable-prefix isolation and cache provenance.

Covers mission checks C, D, E, F, G and O.
"""

from __future__ import annotations

import pytest

from app.llm.policy import examples as examples_module
from app.llm.policy.contracts import RoleContract
from app.llm.policy.registry import ROLE_CONTRACTS, contract_for
from app.llm.policy.templates import (
    CACHE_POLICY_VERSION,
    AssembledPrompt,
    StablePrefixViolation,
    assemble_prompt,
    assert_prefix_is_cacheable,
    build_stable_prefix,
    cache_invalidation_inputs,
    stable_prefix_hash,
)

_ALL_ROLES = sorted(ROLE_CONTRACTS)


def _dynamic_for(role_id: str) -> dict[str, object]:
    """Populate every declared dynamic key with distinguishable turn data."""
    return {key: f"turn-value-for-{key}" for key in contract_for(role_id).dynamic_context}


# --- C: identical stable content hashes identically -------------------------


@pytest.mark.parametrize("role_id", _ALL_ROLES)
def test_stable_prefix_hash_is_deterministic_across_calls(role_id: str) -> None:
    assert stable_prefix_hash(role_id) == stable_prefix_hash(role_id)


@pytest.mark.parametrize("role_id", _ALL_ROLES)
def test_prompt_hash_is_deterministic_for_identical_input(role_id: str) -> None:
    dynamic = _dynamic_for(role_id)
    first = assemble_prompt(role_id, dynamic)
    second = assemble_prompt(role_id, dict(dynamic))
    assert first.prompt_hash == second.prompt_hash
    assert first.stable_prefix_hash == second.stable_prefix_hash
    assert first.dynamic_context_hash == second.dynamic_context_hash


def test_every_role_has_a_distinct_stable_prefix() -> None:
    """Two roles sharing a prefix hash would be one prompt wearing two names."""
    seen: dict[str, str] = {}
    for role_id in _ALL_ROLES:
        digest = stable_prefix_hash(role_id)
        assert digest not in seen, f"{role_id} shares a stable prefix with {seen[digest]}"
        seen[digest] = role_id


# --- D: stable-prefix hash moves when stable content moves ------------------


def test_stable_prefix_hash_changes_when_the_instruction_changes() -> None:
    base = contract_for("intent_shadow_classifier")
    mutated = RoleContract(
        **{
            **{f.name: getattr(base, f.name) for f in base.__dataclass_fields__.values()},
            "system_instruction": base.system_instruction + " Additional stable rule.",
        }
    )
    assert build_stable_prefix(mutated) != build_stable_prefix(base)


def test_stable_prefix_hash_changes_when_prompt_version_changes() -> None:
    base = contract_for("intent_shadow_classifier")
    mutated = RoleContract(
        **{
            **{f.name: getattr(base, f.name) for f in base.__dataclass_fields__.values()},
            "prompt_version": "9.9.9",
        }
    )
    assert build_stable_prefix(mutated) != build_stable_prefix(base)


def test_stable_prefix_hash_changes_when_an_example_is_added(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adding, removing or reordering an active example must invalidate the cache."""
    before = stable_prefix_hash("intent_shadow_classifier")
    original = examples_module.few_shot_set

    extra = examples_module.FewShotExample(
        example_id="fs.intent.zz_probe",
        role_id="intent_shadow_classifier",
        purpose="probe",
        input_shape="A probe request class used only by this test.",
        expected_output_shape="probe",
        authority_boundary="probe",
        version="1.0.0",
        activation="ACTIVE",
        set_id="fewshot:intent_v1",
    )

    def _patched(set_id: str):
        base = original(set_id)
        return base + (extra,) if set_id == "fewshot:intent_v1" else base

    monkeypatch.setattr("app.llm.policy.templates.few_shot_set", _patched)
    assert stable_prefix_hash("intent_shadow_classifier") != before


def test_stable_prefix_hash_changes_when_a_negative_example_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = stable_prefix_hash("intent_shadow_classifier")
    monkeypatch.setattr("app.llm.policy.templates.negative_set", lambda set_id: ())
    assert stable_prefix_hash("intent_shadow_classifier") != before


# --- E: dynamic turn data must NOT move the stable-prefix hash --------------


@pytest.mark.parametrize("role_id", _ALL_ROLES)
def test_dynamic_data_does_not_change_the_stable_prefix_hash(role_id: str) -> None:
    """The cacheable half must be identical whatever the turn contains."""
    baseline = stable_prefix_hash(role_id)
    keys = contract_for(role_id).dynamic_context
    first = assemble_prompt(role_id, {k: "alice / 10.0.0.8 / last 24h" for k in keys})
    second = assemble_prompt(role_id, {k: "bob / 10.9.9.9 / last 7d" for k in keys})
    assert first.stable_prefix_hash == baseline
    assert second.stable_prefix_hash == baseline
    assert first.stable_prefix == second.stable_prefix


# --- F: full prompt hash DOES reflect dynamic input -------------------------


@pytest.mark.parametrize("role_id", _ALL_ROLES)
def test_prompt_hash_reflects_dynamic_input(role_id: str) -> None:
    keys = contract_for(role_id).dynamic_context
    first = assemble_prompt(role_id, {k: "value-a" for k in keys})
    second = assemble_prompt(role_id, {k: "value-b" for k in keys})
    assert first.prompt_hash != second.prompt_hash
    assert first.dynamic_context_hash != second.dynamic_context_hash


def test_prompt_hash_covers_both_halves() -> None:
    role_id = "intent_shadow_classifier"
    a = assemble_prompt(role_id, _dynamic_for(role_id))
    b = assemble_prompt(role_id, {k: "different" for k in contract_for(role_id).dynamic_context})
    assert a.stable_prefix_hash == b.stable_prefix_hash
    assert a.prompt_hash != b.prompt_hash


# --- G: secrets and turn ids cannot enter the cacheable prefix --------------


@pytest.mark.parametrize("role_id", _ALL_ROLES)
def test_every_registered_role_assembles_a_cacheable_prefix(role_id: str) -> None:
    assemble_prompt(role_id, _dynamic_for(role_id))


@pytest.mark.parametrize(
    "label,payload",
    [
        ("bound session id", '{"session_id":"s-7741"}'),
        ("bound trace id", '{"trace_id":"t-0001"}'),
        ("bound request id", '{"request_id":"r-42"}'),
        ("bound api key", '{"api_key":"abcdef123456"}'),
        ("bound access token", '{"access_token":"zzz"}'),
        ("bearer literal", "Authorization: Bearer sk_live_ABCDEFGHIJKLMNOPQRSTUV"),
        ("jwt literal", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0"),
        ("uuid literal", '{"x":"3f2504e0-4f89-11d3-9a0c-0305e82c3301"}'),
        ("iso timestamp", '{"generated_at":"2026-08-25T18:06"}'),
        ("populated rows", '{"rows":[{"user":"alice"}]}'),
        ("populated evidence refs", '{"evidence_refs":["ev:1"]}'),
    ],
)
def test_forbidden_material_is_rejected_from_the_prefix(label: str, payload: str) -> None:
    with pytest.raises(StablePrefixViolation):
        assert_prefix_is_cacheable(payload, role_id="probe")


@pytest.mark.parametrize(
    "payload",
    [
        "You receive no Auth0 grant, no execution tool and no MCP access.",
        "Never reveal a credential, password or API key.",
        "Demonstrate a password change followed by a login within five minutes.",
        '{"results_preview":[]}',
        '{"evidence_refs":[]}',
    ],
)
def test_prohibition_prose_and_empty_schema_hints_stay_cacheable(payload: str) -> None:
    """A prompt must be able to forbid secrets without becoming uncacheable itself."""
    assert_prefix_is_cacheable(payload, role_id="probe")


def test_undeclared_dynamic_key_is_rejected() -> None:
    """Turn data may only enter through keys the contract declared."""
    with pytest.raises(StablePrefixViolation, match="not declared in the contract"):
        assemble_prompt("intent_shadow_classifier", {"session_id": "s-1"})


# --- O: provenance is deterministic and redacted ----------------------------


@pytest.mark.parametrize("role_id", _ALL_ROLES)
def test_provenance_is_complete_and_carries_no_prompt_text(role_id: str) -> None:
    assembled = assemble_prompt(role_id, _dynamic_for(role_id))
    record = assembled.provenance()
    for key in (
        "role_id",
        "prompt_template_id",
        "prompt_version",
        "prompt_hash",
        "stable_prefix_hash",
        "dynamic_context_hash",
        "cache_eligible",
        "cache_policy_version",
        "cache_hit",
    ):
        assert key in record, f"{role_id} provenance missing {key}"
    serialized = str(record)
    assert assembled.stable_prefix not in serialized
    assert assembled.dynamic_suffix not in serialized


def test_provenance_cache_hit_starts_unknown() -> None:
    """Cache hit is provider-reported; we never assert it ourselves."""
    record = assemble_prompt("shape_advisor", _dynamic_for("shape_advisor")).provenance()
    assert record["cache_hit"] == "unknown"


def test_cache_policy_version_is_declared() -> None:
    assert CACHE_POLICY_VERSION == "prompt_cache_policy_v1"


def test_cache_invalidation_inputs_cover_the_stable_prefix_sources() -> None:
    inputs = set(cache_invalidation_inputs("intent_shadow_classifier"))
    for required in (
        "prompt_version",
        "output_schema",
        "few_shot_bank",
        "negative_example_bank",
        "governance_instruction",
    ):
        assert required in inputs


@pytest.mark.parametrize("role_id", _ALL_ROLES)
def test_cache_eligibility_is_declared_for_every_role(role_id: str) -> None:
    assembled = assemble_prompt(role_id, _dynamic_for(role_id))
    assert assembled.cache_eligible in {
        "ELIGIBLE",
        "INELIGIBLE_DYNAMIC_ONLY",
        "INELIGIBLE_NO_STABLE_PREFIX",
    }


def test_assembled_prompt_is_immutable() -> None:
    assembled = assemble_prompt("shape_advisor", _dynamic_for("shape_advisor"))
    with pytest.raises(Exception):
        assembled.prompt_hash = "tampered"  # type: ignore[misc]
    assert isinstance(assembled, AssembledPrompt)
