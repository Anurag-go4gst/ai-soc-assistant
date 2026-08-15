"""Plan 6 E0 — provenance for pipeline_inline MITRE/CVE phases.

These phases execute inside ``graph_node_context_finalize``, not the hook loop.
This helper only names what actually ran. It does not dispatch, schedule, or
authorize anything.
"""

from __future__ import annotations

INLINE_MITRE = "mitre_finalize"
INLINE_CVE = "cve_adapter"


def inline_executed_names(*, mitre_ran: bool, cve_ran: bool) -> list[str]:
    """Stable, ordered names for inline phases that actually ran this turn."""
    names: list[str] = []
    if mitre_ran:
        names.append(INLINE_MITRE)
    if cve_ran:
        names.append(INLINE_CVE)
    return names


def mitre_inline_ran(*, branch_ran: bool, suppressed_not_applicable: bool) -> bool:
    """True when ``run_mitre_evidence_branch`` completed or ``_mitre_outputs_for_finalize`` ran.

    The planner ``not_applicable`` suppress path does not run MITRE mapping.
    """
    if branch_ran:
        return True
    return not suppressed_not_applicable
