"""CVE/vulnerability evidence-requirement vocabulary (leaf module).

Lives in the CVE domain (not the chat pipeline) so both `app.chat.evidence_loop`
and `app.cve.evidence_adapter` can share it without an import cycle
(evidence_adapter is imported by the evidence/context layer, which the chat
package imports — pulling the predicate from `app.chat` created a partial-init
circular import). No imports of its own.
"""
from __future__ import annotations

# CVE/vulnerability-class requirements an onboarded CVE snapshot read model can
# inform (never SERVE from Splunk). Subset of evidence_loop.UNSERVABLE_REQUIREMENTS.
CVE_VULNERABILITY_REQUIREMENTS = frozenset(
    {"cve", "cve_correlation", "unpatched_cve_correlation", "vulnerability_source"}
)


def cve_requirements_present(required: list[str] | set[str] | None) -> bool:
    """True when any CVE/vulnerability-class requirement is in the plan."""
    return bool(set(required or ()) & CVE_VULNERABILITY_REQUIREMENTS)
