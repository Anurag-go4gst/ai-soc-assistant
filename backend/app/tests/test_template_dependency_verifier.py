"""Pre-execution Splunk server alignment via MCP discovery tools."""

from __future__ import annotations

import pytest

from app.spl import template_dependency_verifier as tdv
from app.spl.template_dependency_verifier import (
    required_lookups_for_template,
    verify_template_dependencies,
)


class _FakeConnector:
    def __init__(self, indexes=None, lookups=None, block=None):
        self._indexes = indexes or []
        self._lookups = lookups or []
        self._block = block or set()
        self.calls: list[str] = []

    def call_tool(self, tool_name, arguments, server_name=None):
        self.calls.append(tool_name)
        if tool_name in self._block:
            return {"status": "blocked", "error": "rbac"}
        if tool_name == "splunk_get_indexes":
            return {"indexes": self._indexes}
        if tool_name == "splunk_get_knowledge_objects":
            return {"lookups": self._lookups}
        return {}


@pytest.fixture
def _discovery_on(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(tdv, "discovery_execution_allowed", lambda **_kw: True)

    def _install(connector):
        monkeypatch.setattr(tdv, "get_mcp_connector", lambda: connector)

    return _install


def test_required_lookups_parses_spl() -> None:
    spl = "search index=cisco_asa | lookup power_sector_iocs.csv indicator_ip as dest_ip | stats count"
    assert required_lookups_for_template(spl) == ["power_sector_iocs.csv"]
    assert required_lookups_for_template("search index=x | stats count") == []


def test_verified_when_index_and_lookup_present(_discovery_on) -> None:
    _discovery_on(_FakeConnector(indexes=["cisco_asa", "pgcil_soc"], lookups=["power_sector_iocs.csv"]))
    v = verify_template_dependencies(
        required_indexes=["cisco_asa"], required_lookups=["power_sector_iocs.csv"]
    )
    assert v.checked and v.verified
    assert v.tools_called == ["splunk_get_indexes", "splunk_get_knowledge_objects"]


def test_missing_index_not_verified(_discovery_on) -> None:
    _discovery_on(_FakeConnector(indexes=["pgcil_soc"], lookups=["power_sector_iocs.csv"]))
    v = verify_template_dependencies(required_indexes=["scada_perf"], required_lookups=[])
    assert v.checked and not v.verified
    assert v.missing_indexes == ["scada_perf"]


def test_missing_lookup_not_verified(_discovery_on) -> None:
    _discovery_on(_FakeConnector(indexes=["cisco_asa"], lookups=[]))
    v = verify_template_dependencies(
        required_indexes=["cisco_asa"], required_lookups=["power_sector_iocs.csv"]
    )
    assert not v.verified and v.missing_lookups == ["power_sector_iocs.csv"]


def test_discovery_unavailable_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tdv, "discovery_execution_allowed", lambda **_kw: False)
    v = verify_template_dependencies(required_indexes=["scada_perf"], required_lookups=[])
    assert not v.checked and not v.verified and v.reason == "mcp_discovery_unavailable"


def test_blocked_tool_fails_closed(_discovery_on) -> None:
    _discovery_on(_FakeConnector(indexes=["scada_perf"], block={"splunk_get_indexes"}))
    v = verify_template_dependencies(required_indexes=["scada_perf"], required_lookups=[])
    assert not v.checked and not v.verified


def test_no_dependencies_is_trivially_verified(monkeypatch: pytest.MonkeyPatch) -> None:
    v = verify_template_dependencies(required_indexes=[], required_lookups=[])
    assert v.verified and v.checked and v.reason == "no_dependencies"
