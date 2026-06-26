"""OT/ICS + identity detection-imperative phrasing is investigation-shaped.

Guards the shape-detector branch that routes out-of-registry OT/grid hunts to
guided_investigation (where RAG grounding + LLM enrichment engage) instead of a
thin knowledge_recall answer. Regression cover for the Google-25 testing ground.
"""
from __future__ import annotations

import pytest

from app.query_understanding.soc_investigation_shape import detect_soc_investigation_shape

# Detection-imperative OT/ICS/identity hunts (no literal "hunt"/"anomaly" word).
SHAPED = [
    "Detect any logins to SCADA devices using known default or vendor credentials.",
    "Flag any Modbus TCP traffic communicating on non-standard ports other than 502.",
    "Identify any smart meter or AMI endpoints running outdated firmware versions.",
    "Show the frequency of RTU connection drops to the control center.",
    "Identify any unusual DNP3 function codes sent to distribution RTUs.",
    "Detect any PLCs that were switched from run mode into stop or program mode.",
    "Identify gaps or interruptions in PMU phasor data streams.",
    "Show any firewall policy or rule changes on the OT DMZ firewalls.",
    "Flag any vendor VPN account logged in concurrently from two different locations.",
    "List any new Active Directory accounts created (event code 4720) in the last 7 days.",
]

# Must NOT be shaped: non-SOC, explicit unsafe action, or exact-105 match.
NOT_SHAPED = [
    "What is our HR vacation policy?",
    "Block this IP on the OT firewall right now.",
    "Isolate the substation HMI immediately.",
]


@pytest.mark.parametrize("query", SHAPED)
def test_ot_detection_imperative_is_shaped(query: str) -> None:
    assert detect_soc_investigation_shape(query) is True


@pytest.mark.parametrize("query", NOT_SHAPED)
def test_non_soc_or_unsafe_not_shaped(query: str) -> None:
    assert detect_soc_investigation_shape(query) is False


def test_exact_105_match_suppresses_shape() -> None:
    # Even OT-context detection phrasing must defer to a registry exact match.
    query = "Detect any PLCs that were switched from run mode into stop or program mode."
    assert detect_soc_investigation_shape(query, exact_105_match=True) is False
