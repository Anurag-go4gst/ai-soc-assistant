from app.safeguards.spl_validator import validate_spl
from app.spl.generator import generate_candidate_spl


AUTH_CASE_QUERIES = [
    ("attack_discovery", "In the last hour, which users have abnormally high failed login counts?"),
    ("attack_discovery", "Top source IPs by failed login count in the last hour."),
    ("attack_discovery", "Find successful logins that followed multiple failed login attempts from the same source in the last hour."),
    ("knowledge_recall", "Which users had the most authentication events in the last hour?"),
    ("alert_summary", "Show account lockouts over time in the last hour."),
    ("attack_discovery", "Show successful logins from new or unusual source IPs in the last hour."),
]


def test_existing_auth_cases_have_stub_candidate_behavior() -> None:
    for index, (skill, query) in enumerate(AUTH_CASE_QUERIES, start=1):
        candidate = generate_candidate_spl(f"trace-{index}", skill, query)
        assert candidate.trace_id == f"trace-{index}"
        assert candidate.skill == skill
        assert candidate.generation_mode == "stub"
        if skill in {"attack_discovery", "spl_generation"}:
            assert "index=pgcil_soc" in candidate.candidate_spl
            assert validate_spl(candidate.candidate_spl)["approved"] is True
        else:
            assert candidate.candidate_spl == ""
            assert "spl_not_required" in candidate.warnings


def test_spl_generation_skill_uses_stub_candidate() -> None:
    candidate = generate_candidate_spl("trace-spl", "spl_generation", "Create SPL for failed logins.")
    validation = validate_spl(candidate.candidate_spl)

    assert candidate.candidate_spl
    assert candidate.confidence > 0
    assert validation["approved"] is True
