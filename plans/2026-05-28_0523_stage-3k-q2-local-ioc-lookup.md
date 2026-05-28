# Stage 3K-Q2: Local IOC / Threat-Intel Lookup Framework

## Objective

Build the governed local IOC lookup framework so route plans that need "known malicious IP / domain / URL / hash" have a deterministic, air-gappable authority — without external API calls. Lookups are dry-run only this stage.

## Scope

- Local IOC registry schema and on-disk format (JSON or JSON-lines), loaded at process start.
- IOC types: `ip`, `domain`, `url`, `hash_md5`, `hash_sha1`, `hash_sha256`.
- Per-IOC metadata: `value` (normalized), `ioc_type`, `provenance`, `source`, `confidence` (`low|medium|high`), `tlp`, `first_seen`, `last_seen`, `expiry`, `last_refreshed`.
- Per-source metadata: `source_id`, `source_kind` (`internal_curated`, `vendor_offline_feed`, `analyst_added`), `air_gapped` (bool), `max_staleness_hours`, `update_process_notes`.
- Lookup API `lookup_ioc(value, ioc_type) -> IocLookupResult`. Returns `match`, `confidence`, `staleness_status` (`fresh|stale|expired`), `redacted_provenance`, `tlp`.
- Route plan integration: when route plan declares a lookup dependency (`evidence_needs.lookup_required`), preflight calls `lookup_ioc` and records result. If registry is `stale` past `max_staleness_hours`, preflight returns `cannot_route_missing_lookup` with reason `lookup_stale`.

## Non-Goals

- No external threat-intel API calls (VirusTotal, OTX, Recorded Future, etc.).
- No SPL execution. No MCP call. No execution gate change.
- No live LLM synthesis. No Answer Guard.
- No remediation / write actions.
- No silent "good enough" fallback when lookup is stale.
- No exposure of raw source URLs or analyst-attribution fields to the LLM or to MCP. Only `redacted_provenance` and confidence labels.

## Schema (sketch)

```
{
  "sources": [
    {
      "source_id": "internal_curated_v1",
      "source_kind": "internal_curated",
      "air_gapped": true,
      "max_staleness_hours": 168,
      "update_process_notes": "Updated by SOC weekly from offline feed bundle.",
      "last_refreshed": "2026-05-25T12:00:00Z"
    }
  ],
  "iocs": [
    {"value": "203.0.113.42", "ioc_type": "ip", "source_id": "internal_curated_v1", "confidence": "medium", "tlp": "AMBER", "first_seen": "...", "last_seen": "...", "expiry": "..."}
  ]
}
```

## Implementation Plan

1. Define `app/intel/ioc_models.py` with Pydantic models for source + IOC record.
2. Add `app/intel/ioc_registry.py` with cached loader + normalized value indexing (lowercase host, canonical IP, hash hex-lower).
3. Add `app/intel/ioc_lookup.py` with `lookup_ioc(...)` returning `IocLookupResult` and `staleness_status` driven by source `max_staleness_hours` vs `last_refreshed`.
4. Wire route-plan preflight: if normalized route plan declares lookup dependency and lookup missing/stale → return `RouteStatus.CANNOT_ROUTE_MISSING_LOOKUP` with explicit `missing_slots` / `blocking_findings` reason.
5. Add fixture IOC dataset at `backend/app/intel/fixtures/ioc_registry.sample.json` flagged `coe_synthetic_fixture`.
6. No MCP call. No external HTTP. No live LLM. Lookup is pure-function over loaded registry.

## Tests

`backend/app/tests/test_ioc_lookup_stage3k_q2.py`

- Loader rejects malformed IOC records.
- Lookup by IP / domain / hash returns the expected record + confidence + tlp.
- Normalization handles uppercase domains and IPv6 canonical form.
- Source older than `max_staleness_hours` → `staleness_status=stale`.
- Source past `expiry` → `staleness_status=expired`.
- Route plan with lookup dependency + stale registry → preflight returns `cannot_route_lookup_stale` (canonical reason) and `cannot_route_missing_lookup` aliased reason set, never silent fallback.
- Lookup result never includes raw analyst attribution; only `redacted_provenance`.
- No external HTTP libraries imported / called.

## Verification

```bash
cd backend && python3 -m pytest
python3 -m test_harness.harness.runner --json
TELEMETRY_MODE=none python3 -m test_harness.harness.runner --json
git diff --check
```

## IOC Governance Rules (frozen)

Every IOC lookup record must carry, at minimum:

- `lookup_name`
- `ioc_type`
- `source_owner`
- `last_refreshed`
- `max_staleness`
- `provenance`
- `update_mode` (e.g. `air_gapped_bundle`, `analyst_added`)
- `airgap_approved` (bool)

Staleness rule (mandatory):

- If `now() - last_refreshed > max_staleness`, route must block with `cannot_route_lookup_stale`.
- No silent fallback to "good enough". No partial answer from stale lookups.

This rule is essential for air-gapped SOC credibility.

## LLM Role and Boundary

> LLM assistance is candidate-only. Deterministic core owns validation, normalization, binding, rendering, execution eligibility, and all blocking decisions. If LLM output disagrees with deterministic validation, deterministic wins and the disagreement is recorded.

- Q2 ships **deterministic core only**. No `_llm_assist` sidecar in this stage.
- Rationale: the deterministic IOC registry must exist before any LLM advisory can be safely bound. LLM-assist for IOC questions is deferred until after Q2 lands; it will be re-evaluated as a future stage.
- LLM must never: invent `lookup_name` values, propose new IOC sources, relabel a stale lookup as fresh, override `staleness_status`, or override `cannot_route_lookup_stale`.
- When Q1F is active and a user query implies an IOC lookup, the LLM candidate route plan may set `evidence_needs.lookup_required=true` but never name a specific `lookup_name`. Naming stays in the deterministic registry.

## Fixture Honesty

Q2 ships a synthetic IOC registry fixture labelled `coe_synthetic_fixture=true`, `captured_live_run=false`, `production_execution=false`. It is never relabelled as a captured feed in any later stage.

## Exit Criteria

- Local IOC registry contract exists and loads cleanly.
- Route plan can return `cannot_route_missing_lookup` with stale / missing reasons.
- Lookup correlation can be represented safely without external API.
- No external threat-intel call path introduced.
- Backend tests pass. Harness 6/6.
