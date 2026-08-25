"""P4 — governed Prompt & Policy Studio configuration model (backend contract only).

Scope
-----
The config model, its validation, redaction, permission and rollback semantics. No UI
(explicitly out of scope for P4) and no route: wiring an endpoint is a change to
`routes_settings.py` and belongs with the Studio UI decision, not here.

Design stance
-------------
A Studio that can edit anything is a Studio that can quietly grant an LLM authority.
So the editable surface is an **allowlist**, not a denylist: only the fields named in
``EDITABLE_FIELDS`` may be drafted, and everything else -- authority sets, validators,
output schema, role posture, provider bindings -- is immutable from the Studio and
must go through code review. ``validate_draft`` refuses an unknown field rather than
ignoring it, because silently dropping an edit is how an operator ends up believing a
change took effect.

Drafts are validated without persisting and never echo a secret back.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

STUDIO_CONFIG_VERSION = "prompt_studio_config_v1"

#: The only fields a Studio operator may draft. Adding to this list widens what can be
#: changed without code review, so it is a deliberate, reviewed act.
EDITABLE_FIELDS: tuple[str, ...] = (
    "system_instruction",
    "few_shot_set",
    "negative_example_set",
    "prompt_version",
)

#: Never editable from the Studio. Listed explicitly so the refusal message can say why.
IMMUTABLE_FIELDS: tuple[str, ...] = (
    "role_id",
    "runtime_posture",
    "allowed_authority",
    "extra_prohibited_authority",
    "validator",
    "fallback",
    "output_schema",
    "model_class",
    "authoritative_inputs",
    "dynamic_context",
    "owning_workstream",
)

MAX_INSTRUCTION_CHARS = 8000
MAX_DRAFT_FIELDS = len(EDITABLE_FIELDS)

Permission = Literal["prompt_studio_read", "prompt_studio_draft", "prompt_studio_activate"]

#: Drafting and activating are separate permissions on purpose: the person who writes
#: a prompt should not be the only person who can put it in front of production.
REQUIRED_PERMISSIONS: dict[str, Permission] = {
    "read": "prompt_studio_read",
    "draft": "prompt_studio_draft",
    "activate": "prompt_studio_activate",
}

_SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    ("bearer_literal", r"bearer\s+[A-Za-z0-9._\-]{16,}"),
    ("jwt_literal", r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    ("api_key_literal", r"\bsk-[A-Za-z0-9]{16,}\b"),
    ("bound_secret_field", r'"(api_key|access_token|password|secret|credential)"\s*:\s*"[^"]+"'),
)

_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


class StudioValidationError(ValueError):
    """Raised when a draft is not admissible. Never carries the offending secret."""


class StudioPermissionError(PermissionError):
    """Raised when the caller lacks the permission for the attempted action."""


@dataclass(frozen=True)
class DraftValidationResult:
    admissible: bool
    role_id: str
    changed_fields: tuple[str, ...]
    warnings: tuple[str, ...]
    #: Redacted echo of what would change. Values are summarised, never returned raw.
    redacted_preview: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class StudioAuditEntry:
    entry_id: str
    role_id: str
    action: Literal["draft_validated", "activated", "rolled_back"]
    actor: str
    at: str
    prompt_version_before: str
    prompt_version_after: str
    stable_prefix_hash_before: str
    stable_prefix_hash_after: str
    #: The version an activation can be rolled back to. Required for every activation.
    rollback_target_version: str


def require_permission(granted: set[str] | frozenset[str], action: str) -> None:
    """Guard for read/draft/activate. Raises rather than degrading to read-only."""
    try:
        needed = REQUIRED_PERMISSIONS[action]
    except KeyError as exc:
        raise StudioValidationError(f"unknown studio action: {action}") from exc
    if needed not in granted:
        raise StudioPermissionError(f"action '{action}' requires permission '{needed}'")


def redact(value: str) -> str:
    """Summarise a value for echo. Never returns the value itself."""
    text = str(value)
    return f"<{len(text)} chars>"


def _contains_secret(text: str) -> str | None:
    for label, pattern in _SECRET_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return label
    return None


def validate_draft(
    role_id: str,
    draft: dict[str, Any],
    *,
    granted_permissions: set[str] | frozenset[str],
) -> DraftValidationResult:
    """Validate a draft without persisting anything and without echoing secrets."""
    require_permission(granted_permissions, "draft")

    from app.llm.policy.registry import contract_for

    contract = contract_for(role_id)
    warnings: list[str] = []

    if not draft:
        raise StudioValidationError(f"{role_id}: empty draft")
    if len(draft) > MAX_DRAFT_FIELDS:
        raise StudioValidationError(f"{role_id}: draft has more fields than are editable")

    for key in draft:
        if key in IMMUTABLE_FIELDS:
            raise StudioValidationError(
                f"{role_id}: '{key}' is not editable from the Studio; authority, validator, "
                "schema and posture changes require code review"
            )
        if key not in EDITABLE_FIELDS:
            raise StudioValidationError(f"{role_id}: unknown draft field '{key}'")

    if contract.owning_workstream != "D_POLICY":
        warnings.append(
            f"role is owned by {contract.owning_workstream}; a Studio edit needs that owner's review"
        )

    instruction = draft.get("system_instruction")
    if instruction is not None:
        text = str(instruction)
        if not text.strip():
            raise StudioValidationError(f"{role_id}: system_instruction must not be blank")
        if len(text) > MAX_INSTRUCTION_CHARS:
            raise StudioValidationError(
                f"{role_id}: system_instruction exceeds {MAX_INSTRUCTION_CHARS} characters"
            )
        leaked = _contains_secret(text)
        if leaked is not None:
            raise StudioValidationError(
                f"{role_id}: draft appears to contain credential material ({leaked})"
            )

    version = draft.get("prompt_version")
    if version is not None and not _SEMVER.match(str(version)):
        raise StudioValidationError(f"{role_id}: prompt_version must be semver, got '{version}'")

    return DraftValidationResult(
        admissible=True,
        role_id=role_id,
        changed_fields=tuple(sorted(draft)),
        warnings=tuple(warnings),
        redacted_preview={key: redact(value) for key, value in sorted(draft.items())},
    )


def build_audit_entry(
    *,
    entry_id: str,
    role_id: str,
    action: str,
    actor: str,
    prompt_version_before: str,
    prompt_version_after: str,
    stable_prefix_hash_before: str,
    stable_prefix_hash_after: str,
    rollback_target_version: str,
) -> StudioAuditEntry:
    """Every activation records what changed and what it rolls back to."""
    if action == "activated" and not rollback_target_version.strip():
        raise StudioValidationError(
            f"{role_id}: activation requires a rollback target; an activation you "
            "cannot undo is not a governed change"
        )
    return StudioAuditEntry(
        entry_id=entry_id,
        role_id=role_id,
        action=action,  # type: ignore[arg-type]
        actor=actor,
        at=datetime.now(UTC).isoformat(),
        prompt_version_before=prompt_version_before,
        prompt_version_after=prompt_version_after,
        stable_prefix_hash_before=stable_prefix_hash_before,
        stable_prefix_hash_after=stable_prefix_hash_after,
        rollback_target_version=rollback_target_version,
    )


def can_activate_draft(
    role_id: str,
    *,
    granted_permissions: set[str] | frozenset[str],
    eval_allows_activation: bool,
) -> tuple[bool, str]:
    """Studio activation still defers to the P8 evaluation gate."""
    try:
        require_permission(granted_permissions, "activate")
    except StudioPermissionError as exc:
        return False, str(exc)
    if not eval_allows_activation:
        return False, "prompt_evaluation_contract_refused_activation"
    return True, "activation_permitted"
