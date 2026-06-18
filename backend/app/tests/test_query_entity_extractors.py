from __future__ import annotations

from app.query_understanding.parser import understand_query


def test_entity_extractors_cve_mitre_port_purdue_zone_observation_window() -> None:
    query = (
        "Hunt CVE-2024-12345 on port 502 in zone CORE_SCADA during Purdue layer 1 "
        "observation window of 7 days; map T1059.001 activity"
    )
    result = understand_query(query)
    entities = result.entities

    assert "CVE-2024-12345" in entities.cve_ids
    assert "T1059.001" in entities.mitre_techniques
    assert "502" in entities.port_numbers
    assert "L1" in entities.purdue_layers
    assert entities.zone_labels == ["CORE_SCADA"]
    assert entities.observation_window is not None
    assert "observation window" in entities.observation_window.lower()
