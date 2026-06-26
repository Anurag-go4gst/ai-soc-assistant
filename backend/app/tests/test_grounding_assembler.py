from __future__ import annotations

from app.chat.grounding_assembler import (
    GroundingBlock,
    NullTechniqueResolver,
    assemble_grounding,
    atlas_reference_for_question,
    detect_ai_threat_signal,
)


def test_ai_threat_signal_detection() -> None:
    assert detect_ai_threat_signal("Is my LLM endpoint being prompt injection attacked?") is True
    assert detect_ai_threat_signal("signs of model theft on the inference api") is True
    assert detect_ai_threat_signal("Which hosts had the most failed logins?") is False


def test_atlas_reference_only_for_ai_questions() -> None:
    # AI-shaped question → ATLAS references attached (depository reachable).
    refs = atlas_reference_for_question("possible prompt injection against our ai model")
    assert refs
    assert all(r["technique_id"].startswith("AML") for r in refs)
    # Non-AI question → no ATLAS noise.
    assert atlas_reference_for_question("top SMB talkers today") == []


def test_assemble_grounding_scaffold_shape() -> None:
    block = assemble_grounding(
        "detect model extraction on the llm endpoint",
        detection_families=["network_exfil_volume"],
        enterprise_mitre_refs=["T1041"],
    )
    assert isinstance(block, GroundingBlock)
    assert block.ai_threat_signal is True
    assert block.enterprise_mitre_refs == ["T1041"]
    assert block.atlas_references  # AI question carries ATLAS refs
    # Null resolver → no names yet → explicit limitation recorded.
    assert block.technique_details == {}
    assert any("ATLAS YAML" in lim or "names/descriptions" in lim for lim in block.limitations)
    text = block.to_prompt_block()
    assert "advisory only" in text
    assert "ATLAS" in text


def test_resolver_slot_fills_names() -> None:
    class StubResolver(NullTechniqueResolver):
        def detail(self, technique_id: str):
            return {"name": f"Name for {technique_id}", "description": "x", "deprecated": False}

    block = assemble_grounding(
        "prompt injection hunt",
        resolver=StubResolver(),
        enterprise_mitre_refs=["T1059"],
    )
    assert block.technique_details["T1059"]["name"] == "Name for T1059"
    # With details available, the names-missing limitation is not added.
    assert not any("names/descriptions" in lim for lim in block.limitations)
