"""WS2 prototype: governed-template <stem> SPL resolves from Environment Knowledge.

Proves the de-hardcoding pattern is byte-safe: an abstracted template
(index=<auth_index> sourcetype=<auth_sourcetype>) resolves through the existing
Environment Knowledge resolver to the EXACT SPL the hardcoded template emits
today, so abstraction changes nothing at render time. Hardcoded templates (no
placeholder) are a no-op.
"""

from __future__ import annotations

import json

import pytest

from app.spl import source_profile_resolver as spr
from app.spl.source_profile_resolver import apply_template_env_bindings

# The auth_failed_login_spike template's hardcoded prefix today.
_HARDCODED = "search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now action=failure | stats count by host, src"
_ABSTRACT = "search index=<auth_index> sourcetype=<auth_sourcetype> earliest=-60m latest=now action=failure | stats count by host, src"


@pytest.fixture
def _env_map(monkeypatch: pytest.MonkeyPatch):
    spr._explicit_profile_map.cache_clear()
    monkeypatch.setattr(
        "app.spl.source_profile_resolver.settings.ai_soc_source_profile_map",
        json.dumps({"auth_index": "pgcil_soc", "auth_sourcetype": "pgcil:auth"}),
    )
    yield
    spr._explicit_profile_map.cache_clear()


def test_abstract_template_resolves_byte_identical_to_hardcoded(_env_map) -> None:
    resolved, trace = apply_template_env_bindings(_ABSTRACT)
    assert resolved == _HARDCODED, "abstracted template must resolve to today's exact SPL"
    assert trace["applied"] is True
    assert trace["resolved_from"] == "environment_knowledge"
    assert not trace["unresolved_slots"]


def test_hardcoded_template_is_noop() -> None:
    resolved, trace = apply_template_env_bindings(_HARDCODED)
    assert resolved == _HARDCODED
    assert trace["applied"] is False
    assert trace["reason"] == "no_placeholders"


def test_unmapped_stem_stays_placeholder(_env_map) -> None:
    spl = "search index=<auth_index> sourcetype=<nonexistent_sourcetype> | stats count"
    resolved, trace = apply_template_env_bindings(spl)
    assert "pgcil_soc" in resolved  # mapped stem resolved
    assert "<nonexistent_sourcetype>" in resolved  # unmapped stays placeholder (-> HIL)
    assert any("nonexistent" in s for s in trace["unresolved_slots"])


def test_env_binding_flag_active_and_templates_resolve_to_concrete() -> None:
    """Activated: templates load with <stem> resolved to deployment index/sourcetype."""
    from app.config import settings
    from app.spl.template_registry import get_spl_template

    assert settings.ai_soc_template_env_binding_enabled is True
    t = get_spl_template("auth_failed_login_spike")
    assert t is not None
    # Loader resolved the abstracted <auth_index>/<auth_sourcetype> from Env Knowledge.
    assert "index=pgcil_soc" in t.spl_text
    assert "sourcetype=pgcil:auth" in t.spl_text
    assert "<" not in t.spl_text.split("|")[0]  # no unresolved placeholder in base search
