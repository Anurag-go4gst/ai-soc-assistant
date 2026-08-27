"""OPTIONAL_PHASE_S H1 — Layer 3 prompt/few-shot contract.

The six-case live evaluation found the 8B model over-claiming OPTIMIZED: it swapped
`NOT x=y` for `x!="y"` and stripped wildcards off search terms. These tests pin the
*prevention* contract — the few-shot classes and the hard NEVER rules. Authority to
accept a rewrite lives in `assert_rewrite_preserves`, never here, so nothing in this
file may be consulted by decision logic at runtime.
"""

from __future__ import annotations

import json

from app.spl.spl_optimization_llm import (
    _FEW_SHOTS,
    SPL_OPTIMIZATION_JSON_SCHEMA,
    _system_prompt,
    _user_prompt,
)


def _shot(shot_id: str) -> dict[str, str]:
    for shot in _FEW_SHOTS:
        if shot["id"] == shot_id:
            return shot
    raise AssertionError(f"missing required few-shot class: {shot_id}")


def test_few_shot_set_is_small_and_abstain_weighted() -> None:
    # 5-8 high-signal examples; prefer examples over prose for this model size.
    assert 5 <= len(_FEW_SHOTS) <= 8
    abstain = [s for s in _FEW_SHOTS if s["status"] == "NO_SAFE_OPTIMIZATION"]
    positive = [s for s in _FEW_SHOTS if s["status"] == "OPTIMIZED"]
    assert len(abstain) > len(positive), "few-shot set must be weighted toward abstention"
    assert positive, "abstain-only training would delete Layer 3's useful capability"


def test_negative_filter_class_abstains() -> None:
    shot = _shot("A_negative_filter_abstain")
    assert shot["status"] == "NO_SAFE_OPTIMIZATION"
    assert "!=" in shot["tempted"]
    assert shot["candidate"] == shot["spl"], "abstain must return the input unchanged"


def test_wildcard_removal_class_abstains() -> None:
    shot = _shot("B_wildcard_abstain")
    assert shot["status"] == "NO_SAFE_OPTIMIZATION"
    assert "*" in shot["spl"] and "*" not in shot["tempted"]
    assert shot["candidate"] == shot["spl"]


def test_already_good_class_abstains() -> None:
    shot = _shot("C_already_good_abstain")
    assert shot["status"] == "NO_SAFE_OPTIMIZATION"
    assert shot["candidate"] == shot["spl"]


def test_identical_output_class_abstains() -> None:
    shot = _shot("D_identical_abstain")
    assert shot["status"] == "NO_SAFE_OPTIMIZATION"
    assert shot["candidate"] == shot["spl"]


def test_positive_or_to_in_invents_no_values() -> None:
    shot = _shot("E_or_to_in_positive")
    assert shot["status"] == "OPTIMIZED"
    assert "IN (" in shot["candidate"]
    for value in ("alice", "bob", "carol"):
        assert value in shot["spl"] and value in shot["candidate"]
    # No value may appear in the rewrite that was absent from the input.
    invented = [
        token
        for token in shot["candidate"].replace("(", " ").replace(")", " ").replace(",", " ").split()
        if token not in shot["spl"] and token not in {"IN"}
    ]
    assert not invented, f"few-shot E invents values: {invented}"


def test_governed_time_class_abstains() -> None:
    shot = _shot("F_governed_time_abstain")
    assert shot["status"] == "NO_SAFE_OPTIMIZATION"
    assert "relative_time" in shot["tempted"]
    assert "earliest=" in shot["candidate"] and "latest=" in shot["candidate"]


def test_term_class_does_not_replace_wildcard_matching() -> None:
    shot = _shot("G_term_wildcard_abstain")
    assert shot["status"] == "NO_SAFE_OPTIMIZATION"
    assert "TERM(" in shot["tempted"]
    assert shot["candidate"] == shot["spl"]


def test_system_prompt_states_the_hard_never_rules() -> None:
    prompt = _system_prompt()
    for rule in (
        "Optimization is OPTIONAL",
        "NO_SAFE_OPTIMIZATION",
        "identical to the input",
        "stylistic equivalence",
        "remove, add, or move a wildcard",
        "relative_time",
        "boolean grouping",
        "result limit",
        "Never optimize by guessing",
        "Maximum one pass",
    ):
        assert rule in prompt, f"system prompt lost the {rule!r} rule"


def test_system_prompt_embeds_every_few_shot() -> None:
    prompt = _system_prompt()
    for shot in _FEW_SHOTS:
        payload = json.dumps(
            {"status": shot["status"], "candidate_spl": shot["candidate"]},
            separators=(",", ":"),
        )
        assert payload in prompt, f"few-shot {shot['id']} not rendered into the prompt"


def test_schema_puts_the_decision_before_the_description() -> None:
    # Guided decoding on this vLLM build degrades when the decision field comes last,
    # and abstention must not require emitting SPL.
    props = list(SPL_OPTIMIZATION_JSON_SCHEMA["properties"])
    assert props[0] == "status"
    assert props.index("status") < props.index("candidate_spl")
    assert SPL_OPTIMIZATION_JSON_SCHEMA["required"] == ["status"]
    assert "anyOf" not in json.dumps(SPL_OPTIMIZATION_JSON_SCHEMA)


def test_user_prompt_orders_decision_first_and_defaults_to_abstain() -> None:
    prompt = _user_prompt(
        candidate_spl="search index=auth NOT status=success | stats count by user",
        advisory_rules=["SOC-STD-SPL-001-Q03"],
        user_query="failed auth excluding successes",
    )
    assert "Decide status first" in prompt
    assert "MUST equal the input v1 unchanged" in prompt
    assert "cannot prove the rewrite preserves meaning" in prompt
    assert prompt.index('"status"') < prompt.index("Decide status first")
