from app.safeguards.spl_validator import validate_spl


def test_safe_spl() -> None:
    result = validate_spl('index=auth earliest=-15m latest=now | stats count by user')
    assert result["valid"] is True
    assert result["errors"] == []


def test_unsafe_spl_blocks_command() -> None:
    result = validate_spl('index=auth earliest=-15m latest=now | delete')
    assert result["valid"] is False
    assert "delete" in result["blocked_commands"]


def test_spl_requires_time_range_and_aggregation() -> None:
    result = validate_spl("index=auth user=admin")
    assert result["valid"] is False
    assert len(result["errors"]) == 2
