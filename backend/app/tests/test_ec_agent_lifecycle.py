"""EC agent lifecycle isolation — must not touch production /chat."""

from __future__ import annotations

import inspect


def test_ec_agent_lifecycle_not_imported_by_production_chat() -> None:
    from app.chat import pipeline

    source = inspect.getsource(pipeline)
    assert "ec_agent_lifecycle" not in source
    assert "ec_agent_workflow" not in source


def test_ec_agent_lifecycle_module_is_demo_scoped() -> None:
    from app.demo import ec_agent_lifecycle

    source = inspect.getsource(ec_agent_lifecycle)
    assert "app.chat" not in source
    assert "pipeline.py" not in source
