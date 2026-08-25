"""P4 PP5 — stable prefix / dynamic suffix assembly, hashing and cache provenance.

The split
---------
``STABLE_PREFIX``  role identity, authority boundaries, output schema, stable
                   instructions, active few-shots, active negative examples. Identical
                   for every turn of a given role at a given prompt version.
``DYNAMIC_SUFFIX`` the current turn: RQC, semantic contract, evidence, plan delta, tool
                   result, session state, source bindings, artifact under review.

Why the split is enforced rather than documented
------------------------------------------------
The prefix is the cacheable half, and a cache is a shared object. If a session id, a
trace id, an Auth0 token or the current user's evidence reaches the prefix, that data
becomes cache-resident and can be served across turns and potentially across users.
``assemble_prompt`` therefore *scans* the prefix for forbidden material and raises
rather than returning a poisoned prefix. A test cannot be relied on to catch what a
future caller passes at runtime; the assembler can.

Caching is optimisation only. Nothing cached ever carries authority, and a cache hit
never substitutes for deterministic validation.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from app.llm.policy.contracts import RoleContract
from app.llm.policy.examples import few_shot_set, negative_set
from app.llm.policy.registry import contract_for

CACHE_POLICY_VERSION = "prompt_cache_policy_v1"
TEMPLATE_SCHEMA_VERSION = "prompt_template_v1"

#: Material that must never appear in a cacheable stable prefix.
#:
#: These match *data shapes*, not word mentions, and that distinction is the whole
#: point. A good prompt says "never reveal credentials" and "you receive no Auth0
#: grant" -- prohibitions belong in the prefix, because they are the stable policy.
#: The first version of this scanner matched the words and rejected seven perfectly
#: correct prefixes, including an SPL negative example about password-change-then-login.
#: What must never appear is an actual token, an actual session id, an actual
#: timestamp: a sensitive key *bound to a concrete value*.
FORBIDDEN_PREFIX_PATTERNS: tuple[tuple[str, str], ...] = (
    # A sensitive JSON key bound to a non-empty value. This is the main detector:
    # turn data reaches a prefix as a populated field, not as a noun in a sentence.
    (
        "bound_sensitive_field",
        r'"(session_id|trace_id|request_id|correlation_id|api_key|access_token'
        r"|auth_token|authorization|bearer_token|call_grant|execution_grant"
        r'|password|secret|credential)"\s*:\s*"[^"]+"',
    ),
    # Literal credential material, whatever key it hides behind.
    ("bearer_literal", r"bearer\s+[A-Za-z0-9._\-]{16,}"),
    ("jwt_literal", r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    ("api_key_literal", r"\bsk-[A-Za-z0-9]{16,}\b"),
    # A concrete identifier or clock reading: never stable, so never cacheable.
    ("uuid_literal", r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"),
    ("iso_timestamp_literal", r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}\b"),
    # Populated tool output. An empty list is a schema hint; rows with content are data.
    ("tool_output_rows", r'"(results_preview|rows|retrieved_entries)"\s*:\s*\[\s*[^\]\s]'),
    ("evidence_refs_populated", r'"(evidence_refs|source_evidence_refs)"\s*:\s*\[\s*[^\]\s]'),
)


class StablePrefixViolation(ValueError):
    """Raised when turn-specific or secret material reaches the cacheable prefix."""


def _canonical(payload: object) -> str:
    """Deterministic serialization. Ordering is fixed so hashes are reproducible."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AssembledPrompt:
    role_id: str
    prompt_template_id: str
    prompt_version: str
    stable_prefix: str
    dynamic_suffix: str
    stable_prefix_hash: str
    dynamic_context_hash: str
    prompt_hash: str
    cache_eligible: str

    def provenance(self) -> dict[str, object]:
        """Redacted trace record. Carries identity and hashes, never prompt text."""
        return {
            "role_id": self.role_id,
            "prompt_template_id": self.prompt_template_id,
            "prompt_version": self.prompt_version,
            "prompt_hash": self.prompt_hash,
            "stable_prefix_hash": self.stable_prefix_hash,
            "dynamic_context_hash": self.dynamic_context_hash,
            "cache_eligible": self.cache_eligible,
            "cache_policy_version": CACHE_POLICY_VERSION,
            # Provider-reported; unknown until a provider answers.
            "cache_hit": "unknown",
        }


def build_stable_prefix(contract: RoleContract) -> str:
    """Canonical, turn-independent prefix. Ordering is fixed and part of the hash."""
    few_shots = [] if contract.few_shot_set.startswith("NOT_APPLICABLE") else [
        {
            "example_id": e.example_id,
            "purpose": e.purpose,
            "input_shape": e.input_shape,
            "expected_output_shape": e.expected_output_shape,
            "authority_boundary": e.authority_boundary,
            "version": e.version,
        }
        for e in few_shot_set(contract.few_shot_set)
    ]
    negatives = [] if contract.negative_example_set.startswith("NOT_APPLICABLE") else [
        {
            "example_id": e.example_id,
            "purpose": e.purpose,
            "failure_mode": e.failure_mode,
            "corrected_behaviour": e.corrected_behaviour,
            "enforcing_rule": e.enforcing_rule,
            "version": e.version,
        }
        for e in negative_set(contract.negative_example_set)
    ]
    return _canonical(
        {
            "schema": TEMPLATE_SCHEMA_VERSION,
            "role_id": contract.role_id,
            "prompt_template_id": contract.prompt_template_id,
            "prompt_version": contract.prompt_version,
            "system_instruction": contract.system_instruction,
            "output_schema": contract.output_schema,
            "allowed_authority": list(contract.allowed_authority),
            "prohibited_authority": list(contract.prohibited_authority),
            "authoritative_input_names": list(contract.authoritative_inputs),
            "non_authoritative_context_names": list(contract.non_authoritative_context),
            "few_shot_examples": few_shots,
            "negative_examples": negatives,
        }
    )


def build_dynamic_suffix(contract: RoleContract, dynamic_values: dict[str, object]) -> str:
    """Per-turn half. Only keys the contract declared as dynamic context are accepted."""
    declared = set(contract.dynamic_context)
    undeclared = sorted(set(dynamic_values) - declared)
    if undeclared:
        raise StablePrefixViolation(
            f"{contract.role_id}: dynamic keys not declared in the contract: {undeclared}"
        )
    return _canonical({"role_id": contract.role_id, "dynamic": dynamic_values})


def assert_prefix_is_cacheable(prefix: str, *, role_id: str) -> None:
    """Fail loudly rather than return a prefix that would poison a shared cache."""
    for label, pattern in FORBIDDEN_PREFIX_PATTERNS:
        if re.search(pattern, prefix, flags=re.IGNORECASE):
            raise StablePrefixViolation(
                f"{role_id}: stable prefix contains forbidden material ({label}); "
                "turn-specific and secret data belong in the dynamic suffix"
            )


def assemble_prompt(role_id: str, dynamic_values: dict[str, object] | None = None) -> AssembledPrompt:
    """Assemble, verify and hash one role's prompt for one turn."""
    contract = contract_for(role_id)
    prefix = build_stable_prefix(contract)
    assert_prefix_is_cacheable(prefix, role_id=role_id)
    suffix = build_dynamic_suffix(contract, dict(dynamic_values or {}))

    prefix_hash = _sha256(prefix)
    suffix_hash = _sha256(suffix)
    return AssembledPrompt(
        role_id=contract.role_id,
        prompt_template_id=contract.prompt_template_id,
        prompt_version=contract.prompt_version,
        stable_prefix=prefix,
        dynamic_suffix=suffix,
        stable_prefix_hash=prefix_hash,
        dynamic_context_hash=suffix_hash,
        # The full prompt hash covers both halves, so it moves when either does.
        prompt_hash=_sha256(f"{prefix_hash}:{suffix_hash}"),
        cache_eligible=contract.cache_eligible,
    )


def stable_prefix_hash(role_id: str) -> str:
    """Cache key for a role at its current prompt version."""
    return _sha256(build_stable_prefix(contract_for(role_id)))


def cache_invalidation_inputs(role_id: str) -> tuple[str, ...]:
    """What a stable-prefix change is a function of. Any change invalidates the cache."""
    return (
        "prompt_version",
        "role_contract_fields",
        "output_schema",
        "governance_instruction",
        "few_shot_bank",
        "negative_example_bank",
        "stable_policy_rules",
    )
