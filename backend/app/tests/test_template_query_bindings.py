from __future__ import annotations

from app.spl.template_query_bindings import customize_template_spl

_BASE = (
    "search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now "
    "(action=failure OR action=success) | stats count by user | head 100"
)


_AUTH_SPIKE_BASE = (
    "search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now action=failure "
    "| stats count as failed_logins by user | head 100"
)


def test_auth_failed_login_spike_honors_last_24_hours_from_query() -> None:
    query = "Show failed login spike by user in the last 24 hours"
    spl = customize_template_spl("auth_failed_login_spike", _AUTH_SPIKE_BASE, query)
    assert "earliest=-24h latest=now" in spl
    assert "earliest=-60m" not in spl


def test_auth_success_after_failure_injects_alert_id_without_host() -> None:
    query = (
        "For alert ALT-2024-0891 (failed logins followed by a successful login from the same user "
        "in the last hour), what's the severity, MITRE mapping with status, and a governed SPL "
        "I can review—but not execute"
    )
    spl = customize_template_spl("auth_success_after_failure", _BASE, query)
    assert 'alert_id="ALT-2024-0891"' in spl
    assert "host=APP-01" not in spl


def test_auth_success_after_failure_adds_explicit_host_only_when_present() -> None:
    query = "Generate SPL for successful login after failures on host=APP-01"
    spl = customize_template_spl("auth_success_after_failure", _BASE, query)
    assert 'host="APP-01"' in spl
    assert "alert_id=" not in spl
