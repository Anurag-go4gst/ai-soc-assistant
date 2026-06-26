from __future__ import annotations

from app.use_cases.registry import match_use_cases


def test_generic_threat_advisory_does_not_match_cert_in_hash_use_case() -> None:
    query = (
        "A new advisory says an actor targets electric utilities. "
        "Based on what we log today, are we exposed?"
    )
    assert "cert_in_hash_match" not in {item.use_case_id for item in match_use_cases(query)}


def test_cert_in_hash_language_still_matches_use_case() -> None:
    query = "Check these CERT-In advisory IOC hashes against our telemetry"
    assert "cert_in_hash_match" in {item.use_case_id for item in match_use_cases(query)}
