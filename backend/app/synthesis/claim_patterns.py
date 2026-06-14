"""Shared forbidden-claim patterns (leaf module — no app imports).

Single source of truth for claim detection, used by the governed answer
composer (composition-time enforcement) and the Tier-D answer-quality checks
(eval-time enforcement). Lives in a leaf module because the composer's import
chain reaches app.chat.pipeline, which would cycle for any consumer that
imports before app.chat is initialized.
"""

from __future__ import annotations

import re

GITHUB_MARKERS: tuple[str, ...] = ("skill.md", "github.com", "/skills/", "github_ref:")

EXECUTED_SPL = re.compile(r"\b(spl (was )?executed|executed spl|executed in splunk)\b", re.IGNORECASE)

APPROVED_EXEC = re.compile(
    r"\b(spl (is )?approved for execution|approved for execution|ready to execute|execute (the )?spl)\b",
    re.IGNORECASE,
)

COMPROMISE = re.compile(
    r"\b(account compromis\w*|confirmed compromis\w*|compromise confirmed)\b",
    re.IGNORECASE,
)

NEGATION = re.compile(
    r"\b(not confirmed|no evidence of|not evidence of|candidate only|is not confirmed|review required|do not claim)\b",
    re.IGNORECASE,
)

EVIDENCE_SUPPORTED = re.compile(r"\b(evidence[- ]supported|evidence supported)\b", re.IGNORECASE)

SEVERITY_TOKEN = re.compile(r"\bP[1-4]\b", re.IGNORECASE)
WHY_NOT_HIGHER_CONTEXT = re.compile(
    r"\b(requires|required|threshold|why not|not met|unless|before|would need|missing|not assigned)\b",
    re.IGNORECASE,
)
SEVERITY_ASSIGNMENT = re.compile(
    r"\b(this is|assigned|severity|rated|classified|escalate to|treat as|incident is|priority)\b",
    re.IGNORECASE,
)


def severity_token_is_upgrade_claim(text: str, token: str) -> bool:
    """True when a non-authority severity token reads as an upgrade, not why-not-higher context."""
    pattern = re.compile(rf"\b{re.escape(token)}\b", re.IGNORECASE)
    for match in pattern.finditer(text):
        start = max(0, match.start() - 80)
        end = min(len(text), match.end() + 40)
        window = text[start:end]
        lowered = window.lower()
        if WHY_NOT_HIGHER_CONTEXT.search(lowered):
            continue
        if re.search(rf"\bnot\s+{re.escape(token)}\b", lowered, re.IGNORECASE):
            continue
        if SEVERITY_ASSIGNMENT.search(lowered):
            return True
        token_num = int(token[1])
        before = text[max(0, match.start() - 12) : match.start()].lower()
        if token_num <= 2 and re.search(rf"\b(a|an)\s*$", before):
            return True
    return False
