"""EC SOAR / firewall MCP adapter — fake in pytest, never production /api/actions."""

from __future__ import annotations

from app.demo import ec_soar


def setup_function() -> None:
    ec_soar.clear_all_for_tests()


def test_fake_soar_submit_records_simulated_block() -> None:
    fake = ec_soar.FakeSoarTransport()
    ec_soar.set_transport_for_tests(fake)
    receipt = ec_soar.submit_block(
        {
            "indicator": "198.51.100.42",
            "soar": {"playbook": "ip_block", "action": "block", "reason": "SOC review"},
        },
    )
    assert receipt.status == "SUCCESS"
    assert receipt.production_side_effect is False
    assert receipt.external_side_effect is False
    assert len(fake.submitted) == 1
    assert fake.submitted[0]["indicator"] == "198.51.100.42"


def test_unconfigured_soar_returns_configuration_required(monkeypatch) -> None:
    monkeypatch.setenv("AI_SOC_EC_SOAR_TRANSPORT", "http")
    monkeypatch.delenv("AI_SOC_EC_SOAR_BASE_URL", raising=False)
    ec_soar.set_transport_for_tests(None)
    receipt = ec_soar.submit_block({"indicator": "198.51.100.42", "soar": {"playbook": "ip_block"}})
    assert receipt.status == ec_soar.CONFIGURATION_REQUIRED
    assert receipt.production_side_effect is False
    assert receipt.summary
