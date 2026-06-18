from __future__ import annotations

from app.safeguards.spl_validator import validate_spl
from app.spl.policy import SplValidationPolicy


def _policy(**overrides: object) -> SplValidationPolicy:
    base = dict(
        enabled=True,
        allowed_indexes=("pgcil_soc",),
        allowed_sourcetypes=("pgcil:network",),
        default_earliest="-24h",
        default_latest="now",
        max_result_limit=100,
        allowed_commands=(
            "search",
            "stats",
            "where",
            "table",
            "fields",
            "sort",
            "dedup",
            "rename",
            "eval",
            "timechart",
            "bin",
            "head",
            "streamstats",
            "iplocation",
            "mvexpand",
        ),
        blocked_commands=("delete", "collect", "outputlookup", "sendemail", "script", "map", "rest", "loadjob", "inputlookup"),
    )
    base.update(overrides)
    return SplValidationPolicy(**base)


def test_tier1_iplocation_passes_global_policy() -> None:
    query = """
search index=pgcil_soc sourcetype=pgcil:network earliest=-24h latest=now src_ip=*
| iplocation src_ip
| stats count by Country
| head 50
"""
    result = validate_spl(query, policy=_policy())
    assert result["approved"] is True


def test_lookup_fails_without_template_profile() -> None:
    query = """
search index=pgcil_soc sourcetype=pgcil:network earliest=-24h latest=now
| lookup ot_asset_inventory.csv ip as dest_ip OUTPUT asset_name
| stats count by asset_name
| head 50
"""
    result = validate_spl(query, policy=_policy())
    assert result["approved"] is False
    assert "disallowed_command:lookup" in result["reject_reasons"]


def test_governed_lookup_requires_allowlisted_csv_name() -> None:
    query = """
search index=pgcil_soc sourcetype=pgcil:network earliest=-24h latest=now
| lookup ot_asset_inventory.csv ip as dest_ip OUTPUT asset_name
| stats count by asset_name
| head 50
"""
    result = validate_spl(query, policy=_policy(), template_profile={"allowed_lookups": ["ot_asset_inventory.csv"]})
    assert result["approved"] is True

    rejected = validate_spl(query, policy=_policy(), template_profile={"allowed_lookups": ["other.csv"]})
    assert rejected["approved"] is False
    assert "lookup_not_allowlisted:ot_asset_inventory.csv" in rejected["reject_reasons"]


def test_join_and_transaction_need_template_capability_and_bounds() -> None:
    join_query = """
search index=pgcil_soc sourcetype=pgcil:network earliest=-24h latest=now
| stats count by src_ip
| join max=1 type=left src_ip [ search index=pgcil_soc sourcetype=pgcil:network earliest=-24h latest=now | stats count by src_ip | head 50 ]
| head 50
"""
    denied = validate_spl(join_query, policy=_policy())
    assert "join_not_allowed" in denied["reject_reasons"]

    allowed = validate_spl(join_query, policy=_policy(), template_profile={"allow_join": True, "allow_subsearches": True})
    assert allowed["approved"] is True

    missing_final_head_query = """
search index=pgcil_soc sourcetype=pgcil:network earliest=-24h latest=now
| stats count by src_ip
| join max=1 type=left src_ip [ search index=pgcil_soc sourcetype=pgcil:network earliest=-24h latest=now | stats count by src_ip | head 50 ]
"""
    missing_final_head = validate_spl(
        missing_final_head_query,
        policy=_policy(),
        template_profile={"allow_join": True, "allow_subsearches": True},
    )
    assert missing_final_head["approved"] is False
    assert "join_requires_result_head" in missing_final_head["reject_reasons"]

    transaction_query = """
search index=pgcil_soc sourcetype=pgcil:network earliest=-24h latest=now
| transaction user maxspan=5m
| stats count by user
| head 50
"""
    tx = validate_spl(transaction_query, policy=_policy(), template_profile={"allow_transaction": True})
    assert tx["approved"] is True


def test_bucket_alias_is_treated_like_bin() -> None:
    query = """
search index=pgcil_soc sourcetype=pgcil:network earliest=-24h latest=now
| bucket _time span=1h
| stats count by _time
| head 50
"""
    result = validate_spl(query, policy=_policy())
    assert result["approved"] is True


def test_mvexpand_without_downstream_head_warns() -> None:
    query = """
search index=pgcil_soc sourcetype=pgcil:network earliest=-24h latest=now
| mvexpand values
| stats count by values
| head 50
"""
    result = validate_spl(query, policy=_policy())
    assert result["approved"] is True
    assert "mvexpand_without_downstream_head" not in result["warnings"]

    no_downstream_head = """
search index=pgcil_soc sourcetype=pgcil:network earliest=-24h latest=now
| head 50
| mvexpand values
| stats count by values
"""
    warned = validate_spl(no_downstream_head, policy=_policy())
    assert warned["approved"] is True
    assert "mvexpand_without_downstream_head" in warned["warnings"]
