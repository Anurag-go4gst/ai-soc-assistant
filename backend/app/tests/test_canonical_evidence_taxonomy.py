"""Evidence legs must come from reported events and structured semantics.

Regression pins for the defect where ``compose_multi_leg_evidence`` reconstructed
required evidence from lexical cues in the raw instruction, so that

* "correlate endpoint, DNS/proxy ..." manufactured legs, while
* reported events (archive creation, high outbound transfer, scheduled-task
  creation, second-host access) disappeared.

These cases are phrased as behaviours of the taxonomy, not as the five evaluation
questions: each asserts a *class* of report survives and a *class* of instruction
does not manufacture evidence.
"""

from __future__ import annotations

import pytest

from app.chat.canonical_evidence_taxonomy import (
    ORIGIN_HYPOTHESIS,
    ORIGIN_OBSERVATION,
    ORIGIN_REQUESTED,
    build_semantic_evidence_composition,
    categories_in_text,
    split_reported_observations,
    unsupported_semantic_requirements,
)


def _compose(query: str, *, goal=None, requirements=None, hypotheses=None):
    return build_semantic_evidence_composition(
        raw_query=query,
        normalized_goal=goal,
        semantic_evidence_requirements=requirements,
        semantic_hypotheses=hypotheses,
    )


def _domains(composition) -> set[str]:
    return {leg["domain"] for leg in (composition or {}).get("evidence_legs", [])}


def _backed(composition) -> set[str]:
    return set((composition or {}).get("observation_backed_domains") or [])


@pytest.mark.parametrize(
    "report, expected",
    [
        ("an archive file was created locally", "file_activity"),
        ("the host transferred substantially more outbound data than normal", "egress"),
        ("a newly created scheduled task appeared on the server", "scheduled_task"),
        ("the account accessed another internal server", "lateral_access"),
        ("the workstation made outbound connections to an external IP", "firewall_network"),
        ("several denied outbound connections were generated", "firewall_network"),
        ("the workstation launched cmd.exe", "endpoint_process"),
        ("the host accessed an unusual external domain", "dns"),
        ("remote access by an administrator account", "vpn_auth"),
    ],
)
def test_reported_event_classes_are_recognised(report: str, expected: str) -> None:
    assert expected in categories_in_text(report)


def test_instruction_alone_never_manufactures_evidence() -> None:
    """The negative case: a domain the analyst asks about is not a reported event."""
    for instruction in (
        "Check DNS, endpoint and authentication evidence.",
        "Please review endpoint logs, DNS records and authentication telemetry.",
        "Correlate endpoint, DNS/proxy, and network evidence.",
    ):
        assert _compose(instruction) is None


def test_reported_events_survive_without_naming_their_telemetry_domain() -> None:
    """Observations alone compose, even though no telemetry domain is named."""
    composition = _compose(
        "A finance workstation accessed an unusual external domain, then transferred "
        "substantially more outbound data than normal. Around the same time, an archive "
        "file was created locally."
    )
    assert {"dns", "egress", "file_activity"} <= _backed(composition)


def test_instruction_domains_are_additive_hints_not_chain_members() -> None:
    """A requested domain earns a leg but is never observation-backed."""
    composition = _compose(
        "A workstation generated several denied outbound connections to an external "
        "address. Correlate the connection sequence with endpoint activity on the host."
    )
    assert "firewall_network" in _backed(composition)
    legs = {leg["domain"]: leg["origin"] for leg in composition["evidence_legs"]}
    assert legs["endpoint_process"] == ORIGIN_REQUESTED
    assert "endpoint_process" not in _backed(composition)


def test_event_reported_inside_an_instruction_is_still_a_report() -> None:
    """"Investigate whether a newly created scheduled task ..." reports a task."""
    composition = _compose(
        "Investigate whether a newly created scheduled task on a server is suspicious. "
        "The task appeared shortly after remote access by an administrator account."
    )
    assert {"scheduled_task", "vpn_auth"} <= _backed(composition)


def test_competing_hypothesis_implies_evidence_but_is_not_a_reported_event() -> None:
    """A hypothesis earns an evidence question; it must not enter a chain claim."""
    composition = _compose(
        "A workstation generated several denied outbound connections to an external "
        "address and later successfully connected to the same destination. Correlate "
        "the connection sequence with endpoint activity on the host.",
        hypotheses=["the account may have performed lateral movement to another server"],
    )
    legs = {leg["domain"]: leg["origin"] for leg in composition["evidence_legs"]}
    assert legs["lateral_access"] == ORIGIN_HYPOTHESIS
    assert "lateral_access" not in _backed(composition)


def test_semantic_requirements_are_observation_backed() -> None:
    composition = _compose(
        "Something happened on the estate.",
        requirements=[
            "file and archive creation on the host",
            "outbound transfer volume for the host",
        ],
    )
    assert {"file_activity", "egress"} <= _backed(composition)


def test_unmapped_semantic_requirement_is_reported_not_invented() -> None:
    unsupported = unsupported_semantic_requirements(
        ["badge reader turnstile records", "endpoint activity logs"]
    )
    assert unsupported == ["badge reader turnstile records"]


def test_instruction_and_observation_clauses_are_separated() -> None:
    observations, instructions = split_reported_observations(
        "An archive file was created locally. Correlate endpoint and DNS evidence. "
        "Do not execute remediation."
    )
    assert any("archive" in clause for clause in observations)
    assert not any("archive" in clause for clause in instructions)
    assert len(instructions) == 2


def test_multi_domain_report_states_one_chain_over_backed_domains_only() -> None:
    composition = _compose(
        "A user account logged into a workstation it does not normally use, and shortly "
        "afterward that workstation launched cmd.exe and made outbound connections to an "
        "unfamiliar external IP.",
    )
    backed = _backed(composition)
    assert {"auth_success", "endpoint_process", "firewall_network"} <= backed
    assert backed <= _domains(composition)
