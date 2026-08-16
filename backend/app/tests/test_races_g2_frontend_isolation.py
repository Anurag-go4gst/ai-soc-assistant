"""G2 — frontend isolation. Chat/Cockpit/ChatPanel do not import EC runtime."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FRONTEND = REPO / "frontend" / "src"


def test_g2_production_surfaces_do_not_import_ec_runtime() -> None:
    for rel in (
        "pages/ChatPage.tsx",
        "pages/SocCockpit.tsx",
        "components/ChatPanel.tsx",
    ):
        text = (FRONTEND / rel).read_text(encoding="utf-8")
        assert "@/components/ec" not in text
        assert "components/ec/" not in text
        assert "EcInvestigationWorkspace" not in text


def test_g2_ec_does_not_use_proposed_actions_panel() -> None:
    for path in (FRONTEND / "components" / "ec").rglob("*"):
        if path.suffix not in {".ts", ".tsx"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert "ProposedActionsPanel" not in text


def test_g2_ec_client_uses_demo_routes() -> None:
    text = (FRONTEND / "api" / "ecClient.ts").read_text(encoding="utf-8")
    assert "/demo/" in text
    assert "/api/actions" not in text
