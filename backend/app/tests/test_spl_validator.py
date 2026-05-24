from app.safeguards.spl_validator import validate_spl


def test_safe_spl() -> None:
    result = validate_spl("search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | stats count by user | head 100")
    assert result["approved"] is True
    assert result["normalized_spl"] is not None
    assert result["reject_reasons"] == []
    assert result["enforced_limits"]["max_result_limit"] == 100


def test_unsafe_spl_blocks_command() -> None:
    result = validate_spl("search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | delete")
    assert result["approved"] is False
    assert "delete" in result["blocked_commands"]


def test_spl_requires_time_range_and_aggregation() -> None:
    result = validate_spl("search index=pgcil_soc sourcetype=pgcil:auth user=admin")
    assert result["approved"] is False
    assert "missing_time_bounds" in result["reject_reasons"]


def test_disallowed_index_is_rejected() -> None:
    result = validate_spl("search index=* sourcetype=pgcil:auth earliest=-15m latest=now | stats count")
    assert result["approved"] is False
    assert "disallowed_index" in result["reject_reasons"]
    assert "wildcard_index_not_allowed" in result["reject_reasons"]


def test_risky_commands_are_rejected() -> None:
    for command in ("outputlookup", "collect", "delete", "sendemail", "rest", "map"):
        result = validate_spl(f"search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | {command} | head 100")
        assert result["approved"] is False
        assert any(reason.startswith("blocked_command") for reason in result["reject_reasons"])


def test_macros_subsearches_external_calls_and_secret_patterns_are_rejected() -> None:
    macro = validate_spl("search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now `danger` | stats count | head 100")
    subsearch = validate_spl("search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now [ search index=pgcil_soc ] | stats count | head 100")
    external = validate_spl("search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now http://example.com | stats count | head 100")
    secret = validate_spl("search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now password=foo | stats count | head 100")

    assert "macros_not_allowed" in macro["reject_reasons"]
    assert "subsearches_not_allowed" in subsearch["reject_reasons"]
    assert "external_calls_not_allowed" in external["reject_reasons"]
    assert "credential_or_secret_pattern" in secret["reject_reasons"]


def test_missing_result_limit_is_rejected() -> None:
    result = validate_spl("search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | stats count")
    assert result["approved"] is False
    assert result["normalized_spl"] is None
    assert "missing_result_limit" in result["reject_reasons"]


def test_result_limit_above_policy_is_rejected() -> None:
    result = validate_spl("search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | stats count | head 1000")
    assert result["approved"] is False
    assert result["normalized_spl"] is None
    assert "result_limit_exceeds_policy" in result["reject_reasons"]


def test_bounded_spl_is_the_only_executable_normalized_form() -> None:
    unbounded = validate_spl("search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | stats count")
    bounded = validate_spl("search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | stats count | head 100")

    assert unbounded["approved"] is False
    assert unbounded["normalized_spl"] is None
    assert bounded["approved"] is True
    assert bounded["normalized_spl"] == "search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | stats count | head 100"
