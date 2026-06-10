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
