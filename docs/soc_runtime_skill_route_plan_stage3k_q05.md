# Stage 3K-Q0.5: Compact Runtime Skill Route Plan

Status: design/contract only
Inputs: `docs/soc_question_taxonomy_stage3k_q0.md`, `docs/soc_team_vetting_note_stage3k_q0_20260527-134736.md`
Scope: compact runtime skill routing and route-plan design. No runtime code, `SKILL_ENUM`, runtime registry, SPL templates, SPL validator, LLM synthesis, Answer Guard, MCP/SPL gates, or Experience Center behavior changes are included.

## Executive Summary

Stage 3K-Q0 grouped 105 SOC questions into 20 taxonomy patterns for planning, coverage analysis, and SOC/Splunk team vetting. Those taxonomy groups are not runtime skills. They describe the shape of analyst needs and source dependencies; they should not become 20 independently routed execution capabilities.

Runtime skills should be compact operational contracts. A small catalog should carry variation through route-plan parameters: `pattern_id`, `operation_type`, `source_class`, `domain`, `entities`, `metric`, `time_window`, filters, thresholds, required lookups, and required detection bindings.

The recommended runtime design is a compact 10-skill catalog:

- `aggregate_and_rank`
- `threshold_anomaly`
- `sequence_detection`
- `lookup_correlation`
- `behavioral_detection_binding`
- `metadata_discovery`
- `entity_context_lookup`
- `notable_risk_lookup`
- `multi_signal_correlation`
- `entity_timeline`

An LLM can assist with broad semantic routing into this fixed catalog, especially where analyst language is varied. Deterministic layers must still validate the route plan, enforce hard preconditions, reject invalid compositions, decide execution order, and preserve existing governance boundaries. Model confidence is not authority.

## Runtime Skill Catalog

### `aggregate_and_rank`

Purpose: Rank entities by a deterministic aggregate over a bounded time window.

Examples from the SOC list:

- Which source IPs generated the most outbound connections?
- Which hosts generated the most DNS queries?
- Which destination IPs were contacted by many hosts?
- Which source IPs generated the most authentication failures today?
- Which devices are generating the most endpoint alerts?

Allowed operation types: `top_n`, `bottom_n`, `rank_by_count`, `rank_by_distinct_count`, `rank_by_sum`, `enumerate_latest`.

Required slots: `source_class`, `domain`, `time_window`, `group_by.field`, `metric.type`, `metric.field`, `sort.field`, `sort.direction`, `limit`.

Optional slots: `filters`, `secondary_group_by`, `entity_normalization`, `direction`, `internal_external_scope`.

Source dependencies: CIM or raw source binding for network, DNS, authentication, intrusion detection, endpoint alert, or notable/risk data. CIM/tstats use remains blocked until Stage 3K-Q1 validator/template-schema safety work.

Allowed post-enrichments: `entity_context_lookup` for ranked users, hosts, IPs, or assets.

Clarification triggers: missing time window when no deterministic default exists; ambiguous entity field; ambiguous metric; missing direction for directional network questions if no default source binding defines it.

Hard preconditions: configured source binding for the requested source class; allowed aggregate metric; bounded time window; bounded limit.

Governance constraints: read-only aggregation; no compromise conclusion from counts alone; global aggregate values must remain value-or-gap in model-consumed packages.

Must NOT: infer maliciousness, call external threat intelligence, generate behavioral detection logic, execute candidate SPL, or treat `group_by` as the metric.

### `threshold_anomaly`

Purpose: Find entities whose counts, distinct counts, bytes, rates, or changes exceed an explicit threshold, baseline, or SOC-approved default.

Examples from the SOC list:

- Which users have excessive failed logins?
- Which hosts communicated with many unique external IPs?
- Which hosts show a spike in failed logins?
- Which domains were queried by multiple hosts in a short period?
- Who is sending large amounts of data outbound?

Allowed operation types: `threshold_count`, `threshold_distinct_count`, `threshold_sum`, `spike`, `baseline_deviation`, `repeated_activity`.

Required slots: `source_class`, `domain`, `time_window`, `entity_field`, `metric`, `threshold` or `baseline_ref`, `comparison`.

Optional slots: `filters`, `peer_group`, `lookback_window`, `minimum_event_count`, `direction`, `unit`.

Source dependencies: source binding with fields needed for the metric, plus baseline store or SOC-approved default when the question uses words such as "excessive", "many", "large", "spike", or "unusual".

Allowed post-enrichments: `entity_context_lookup`; `lookup_correlation` only when the threshold result is being checked against a local IOC or approved lookup.

Clarification triggers: missing threshold and no approved default; missing baseline; missing unit for byte/volume questions; missing source needed for user attribution.

Hard preconditions: threshold/baseline must be explicit or configured; source must expose required metric fields; bounded time window.

Governance constraints: output is an anomaly candidate, not proof of compromise or exfiltration; thresholds must be visible in lineage.

Must NOT: invent thresholds, silently pick baselines, create external enrichments, or claim exfiltration/attack without supporting detection or context.

### `sequence_detection`

Purpose: Detect ordered event sequences within a bounded window.

Examples from the SOC list:

- Which accounts had a successful login after repeated failures?
- Which users authenticated to VPN after repeated MFA failures?
- Which internal hosts generated outbound traffic after DNS lookups?
- Which users had access to sensitive systems and then large outbound transfers?

Allowed operation types: `success_after_failure`, `event_a_then_event_b`, `ordered_sequence`, `temporal_join`.

Required slots: `source_class`, `domain`, `entity_field`, `sequence_steps`, `time_window`, `max_step_gap`.

Optional slots: `threshold`, `filters`, `anchor_event`, `join_fields`, `direction`, `post_sequence_window`.

Source dependencies: source bindings for each sequence step, normalized entity fields, event result/action semantics, and time fields.

Allowed post-enrichments: `entity_context_lookup`; `lookup_correlation` when a sequence output is checked against local IOC or approved lookup data.

Clarification triggers: missing entity; missing repeated-failure threshold; missing max gap; missing anchor event for "before/after" questions.

Hard preconditions: ordered step definitions must be known; each step source must be configured; sequence window must be bounded.

Governance constraints: evidence must show step order and timing; output is suspicious sequence evidence, not final attribution.

Must NOT: convert vague multi-signal questions into arbitrary chains, infer missing sequence steps, or execute unvetted generated SPL.

### `lookup_correlation`

Purpose: Correlate observed events with a local, configured lookup such as malicious IPs, domains, URLs, hashes, high-risk ports, approved applications, or internal inventory.

Examples from the SOC list:

- Which hosts contacted known malicious IPs today?
- Which hosts reached known malicious domains from lookup data?
- Did any endpoint run this suspicious hash?
- Which hosts contacted IPs in an IOC lookup?
- Which internal hosts contacted known command-and-control domains?

Allowed operation types: `ioc_match`, `lookup_match`, `hash_match`, `domain_match`, `ip_match`, `url_match`, `approved_list_match`, `denylist_match`.

Required slots: `source_class`, `domain`, `time_window`, `lookup_ref`, `lookup_key`, `event_field`, `entity_field`.

Optional slots: `lookup_value_filters`, `ioc_type`, `match_direction`, `confidence_source_field`, `first_seen`, `last_seen`.

Source dependencies: local lookup configured and approved for the use case; event source with normalized field to match; no external threat-intel call by default.

Allowed post-enrichments: `entity_context_lookup`.

Clarification triggers: "known malicious", "IOC", "suspicious", or "C2" without a configured local lookup; ambiguous IOC type; suspicious hash value omitted.

Hard preconditions: local lookup must be configured and vetted; lookup key schema must match source field; source must be available.

Governance constraints: cite lookup name/version/freshness where available; distinguish lookup match from compromise.

Must NOT: call external threat-intel services, let the LLM invent lookup contents, or treat broad "suspicious" language as proof without a local source.

### `behavioral_detection_binding`

Purpose: Bind a question to vetted detection content or fixture-backed detection results for behavioral patterns that should not be generated ad hoc.

Examples from the SOC list:

- Which DNS queries look like DGA activity?
- Which hosts showed possible command-and-control beaconing?
- Which hosts executed encoded PowerShell commands?
- Which endpoints created new scheduled tasks?
- Which systems show signs of webshell activity?
- Which hosts show signs of lateral movement?

Allowed operation types: `vetted_detection_lookup`, `correlation_search_result`, `detection_result_filter`, `detection_family_lookup`.

Required slots: `detection_ref`, `domain`, `time_window`, `entity_field`, `source_class`.

Optional slots: `severity_filter`, `technique_filter`, `detection_family`, `filters`, `threshold`, `asset_scope`.

Source dependencies: SOC-approved detection/correlation search, ESCU-like content, detection inventory, or fixture-backed detection result. Required families include DGA, beaconing, C2, encoded PowerShell, lateral movement, scheduled tasks, persistence, and webshell.

Allowed post-enrichments: `entity_context_lookup`; `notable_risk_lookup` when detection results link to notable/risk records.

Clarification triggers: requested behavior has no configured vetted detection; ambiguous detection family; source binding is known unavailable.

Hard preconditions: detection reference must exist, be enabled for routing, and expose safe result metadata; no LLM-authored detection SPL.

Governance constraints: detection logic provenance must remain visible; permitted MITRE/action sets remain deterministic.

Must NOT: author new SPL for DGA/beaconing/C2/PowerShell/lateral movement/persistence/webshell, imply detection availability from wording, or bypass gated execution.

### `metadata_discovery`

Purpose: Perform safe metadata/source-health discovery before any event query planning.

Examples from the SOC list:

- Which logs are missing from key security sources?
- Which sources stopped sending events recently?

Allowed operation types: `source_health`, `missing_source_check`, `stale_source_check`, `field_availability_check`, `safe_index_discovery`.

Required slots: `operation_type`, `source_inventory_ref` or `source_class`, `time_window`.

Optional slots: `expected_sources`, `freshness_threshold`, `field_names`, `sourcetype`, `index`.

Source dependencies: source inventory, metadata/freshness records, or safe metadata-only Splunk source.

Allowed post-enrichments: none.

Clarification triggers: "key sources" without configured expected source inventory; freshness threshold missing and no default exists.

Hard preconditions: metadata operation must be allowlisted; no event-content search; bounded source scope.

Governance constraints: metadata-only; result should identify source availability gaps, not route into behavioral detection by itself.

Must NOT: trigger SPL execution against event data, chain into behavioral detection, or infer coverage beyond source health.

### `entity_context_lookup`

Purpose: Enrich a known user, host, IP, asset, account, or domain with asset/identity/CMDB/IAM context.

Examples from the SOC list:

- For any flagged host or user, what is its asset criticality, business owner, and identity/privilege status?
- What unusual processes ran on critical servers?
- Which users performed privileged actions from non-admin workstations?
- Which users accessed privileged applications unusually?

Allowed operation types: `asset_lookup`, `identity_lookup`, `cmdb_lookup`, `privilege_lookup`, `owner_lookup`, `criticality_lookup`.

Required slots: `entity`, `entity_type`, `lookup_ref`, `requested_attributes`.

Optional slots: `time_window`, `source_event_ref`, `asset_scope`, `identity_scope`.

Source dependencies: Asset & Identity, CMDB, IAM, privileged-app inventory, critical asset inventory, or equivalent local lookup.

Allowed post-enrichments: none. This skill is itself an enrichment.

Clarification triggers: missing entity; "critical asset", "business owner", "admin", or "privileged" without configured authoritative source.

Hard preconditions: entity value must be known or come from a parent result; lookup must be configured and read-only.

Governance constraints: enrichment must be source-cited; missing evidence remains explicit.

Must NOT: execute SPL as a primary route, generate detections, or infer criticality/privilege from names alone.

### `notable_risk_lookup`

Purpose: Read and rank alert, notable, risk, and case-state records from an authoritative source.

Examples from the SOC list:

- What incident or alert network events are high or critical right now?
- Which users or hosts have the highest risk scores?
- What happened for this specific notable event?
- Which alerts are still open and unresolved?
- Has this entity, IP, domain, or notable been seen or investigated before?

Allowed operation types: `severity_filter`, `risk_rank`, `notable_lookup`, `case_state_lookup`, `prior_disposition_lookup`, `open_alert_lookup`.

Required slots: `source_class`, `domain`, `time_window` or `notable_id`, `filters`.

Optional slots: `entity`, `entity_type`, `severity`, `status`, `risk_threshold`, `disposition_fields`, `limit`.

Source dependencies: ES notable/risk, alert/case system, risk index, or equivalent read-only fixture/source.

Allowed post-enrichments: `entity_context_lookup`; `entity_timeline` when there is a specific entity or notable anchor.

Clarification triggers: "this notable" without `notable_id` or prior context; "right now" with no deterministic time-window default; prior disposition source missing.

Hard preconditions: notable/risk source configured; authoritative severity/status fields; notable-specific questions require `notable_id` or prior context.

Governance constraints: read-only; no case updates; severity/status/disposition must come from source fields, not model judgment.

Must NOT: change notable state, create actions, infer priority outside deterministic permitted sets, or execute candidate SPL.

### `multi_signal_correlation`

Purpose: Coordinate a flat, bounded set of approved sub-invocations for questions that explicitly require multiple signals.

Examples from the SOC list:

- Which hosts showed both process execution and suspicious DNS within 24 hours?
- Which users were involved in both failed logins and privilege changes?
- Which hosts contacted both malicious IPs and domains?
- Which users had access to sensitive systems and then large outbound transfers?
- Which detections involved the same user and host repeatedly?

Allowed operation types: `both_signals`, `all_signals`, `any_signal_set`, `temporal_multi_signal`, `same_entity_multi_detection`.

Required slots: `correlation_entity`, `time_window`, `sub_invocations`, `join_policy`.

Optional slots: `max_gap`, `post_enrichment`, `minimum_signal_count`, `signal_labels`, `evidence_policy`.

Source dependencies: each sub-invocation must satisfy its own source, lookup, threshold, or detection preconditions.

Allowed post-enrichments: `entity_context_lookup` after sub-results. Flat `sub_invocations` may use only approved primary skills and may not themselves contain `sub_invocations`.

Clarification triggers: vague "anomalies" without named signal families; missing correlation entity; too many requested signals; required sub-skill blocked by missing lookup, detection, or source.

Hard preconditions: explicit multi-signal language such as "both", "and then", "involved in both", "multiple different detections", or a clear temporal correlation request; max route-plan depth is 2.

Governance constraints: branch evidence must remain separate; unsupported claims cannot be flattened into a single conclusion.

Must NOT: create arbitrary LLM-authored chains, nest multi-signal plans, silently skip blocked branches, or combine unrelated results without deterministic join policy.

### `entity_timeline`

Purpose: Build a bounded activity timeline for a known entity around a time window or detection anchor.

Examples from the SOC list:

- What is the full activity timeline for a given entity in the N hours before and after a detection?
- Has this entity, IP, domain, or notable been seen or investigated before?
- What happened for this specific notable event?

Allowed operation types: `entity_activity_timeline`, `before_after_detection`, `prior_sightings`, `bounded_history`.

Required slots: `entity` or `notable_id`, `entity_type`, `time_window` or `anchor_event`, `source_classes`.

Optional slots: `event_categories`, `before_window`, `after_window`, `limit_per_source`, `case_history_ref`.

Source dependencies: configured event sources and/or notable/case history source; entity normalization.

Allowed post-enrichments: `entity_context_lookup` only when entity context was not already supplied.

Clarification triggers: missing entity; "this host/entity/notable" without prior context; missing `N` for before/after windows and no default exists.

Hard preconditions: known entity or notable anchor; bounded time range; source classes selected by deterministic validator.

Governance constraints: timeline is evidence organization, not final synthesis; missing branches stay explicit.

Must NOT: run as a broad search without entity/time bounds, infer prior disposition without case-history source, or create nested investigations.

## Taxonomy-to-Runtime Mapping

Taxonomy patterns are planning metadata. The runtime skill and operation type below are the proposed compact route representation, not a one-to-one skill expansion.

| Taxonomy pattern | Runtime skill | operation_type | source_class | Required parameters | Clarification triggers | Dependency type | Notes |
|---|---|---|---|---|---|---|---|
| `top_n_aggregation` | `aggregate_and_rank` | `top_n` or `rank_by_*` | CIM/raw event or notable/risk | `group_by`, `metric`, `sort`, `limit`, `time_window` | ambiguous metric/entity, missing time default | source binding | Covers network, DNS, auth, endpoint alerts, notable rankings. |
| `threshold_anomaly` | `threshold_anomaly` | `threshold_*`, `spike`, `baseline_deviation` | CIM/raw event | entity, metric, threshold/baseline, comparison, time_window | no threshold/default, no baseline | threshold/baseline plus source | "Excessive", "many", "large", "spike", "unusual" need approved values. |
| `time_trend` | `aggregate_and_rank` | `enumerate_latest` or future `time_bucket_trend` | CIM/raw event | bucket span, metric, time_window | bucket span missing | source binding | No actual Q0 question; do not add a runtime skill now. |
| `new_or_unusual_source` | `threshold_anomaly` | `baseline_deviation` or `lookup_match` | CIM/raw plus baseline/lookup | entity, comparison field, baseline_ref or lookup_ref, time_window | no baseline/allowlist/policy | baseline/policy | Geo, rare port, after-hours, new country need deterministic policy. |
| `success_after_failure` | `sequence_detection` | `success_after_failure` | `cim.authentication` or VPN/MFA | entity, failure step, success step, threshold, max_gap, time_window | failure threshold missing, source mapping missing | source plus threshold | Covers AD/auth and VPN/MFA variants. |
| `ioc_correlation` | `lookup_correlation` | `ioc_match` | network/DNS/web/endpoint | lookup_ref, lookup_key, event_field, entity_field, time_window | no local lookup, IOC type missing | local lookup | No external threat-intel call. |
| `threat_intel_enrichment` | `lookup_correlation` | `lookup_match` | DNS/web/network | lookup_ref, event_field, entity_field, time_window | "suspicious" source missing | local lookup | Treat as local lookup correlation, not external enrichment. |
| `notable_risk_lookup` | `notable_risk_lookup` | `severity_filter`, `risk_rank` | ES notable/risk or equivalent | severity/status/risk filters, time_window, entity if needed | "right now" undefined, source missing | notable/risk source | Read-only only. |
| `case_state_lookup` | `notable_risk_lookup` or `entity_timeline` | `case_state_lookup`, `prior_disposition_lookup` | case/notable history | notable_id/entity, disposition fields, time_window | "this notable" without context | case history source | Specific notable routes to `notable_risk_lookup`; broader prior sightings may use `entity_timeline`. |
| `asset_identity_context` | `entity_context_lookup` | `asset_lookup`, `identity_lookup`, `privilege_lookup` | Asset/Identity, CMDB, IAM | entity, entity_type, lookup_ref, attributes | missing entity, missing authoritative lookup | enrichment lookup | Post-enrichment or direct context lookup only. |
| `dns_beaconing_dga_behavior` | `behavioral_detection_binding` | `vetted_detection_lookup` | vetted DNS/network detection | detection_ref, entity_field, time_window | no vetted DGA/beaconing/C2 detection | detection binding | Do not generate detection SPL. |
| `lateral_movement` | `behavioral_detection_binding` | `vetted_detection_lookup` | vetted endpoint/network detection | detection_ref, entity_field, time_window | no lateral movement/SMB detection or threshold | detection binding | SMB fan-out may be threshold only if SOC-approved threshold exists. |
| `suspicious_process_powershell` | `behavioral_detection_binding` | `vetted_detection_lookup` | vetted endpoint detection | detection_ref, process/entity fields, time_window | no endpoint source/detection | detection binding | Includes encoded PowerShell, process chains, webshell, script interpreters. |
| `persistence_scheduled_task_service` | `behavioral_detection_binding` | `vetted_detection_lookup` | vetted endpoint/Windows detection | detection_ref, entity_field, time_window | no scheduled task/service detection | detection binding | Persistence claims require approved detection logic. |
| `data_source_health` | `metadata_discovery` | `source_health`, `stale_source_check` | metadata/source inventory | expected_sources, freshness threshold, time_window | "key sources" undefined | metadata inventory | No post-enrichment. |
| `cloud_activity` | `behavioral_detection_binding` or `threshold_anomaly` | blocked until source design | cloud/control-plane | source binding, operation-specific fields | cloud source missing | source/detection | Count is zero in Q0; keep as planning metadata. |
| `dlp_exfiltration` | `threshold_anomaly` or `behavioral_detection_binding` | `threshold_sum` or `vetted_detection_lookup` | network/proxy/DLP/endpoint | bytes/volume threshold, entity, time_window, source | no DLP/proxy/source, no threshold | source plus threshold/detection | Volume alone must not claim exfiltration. |
| `multi_signal_correlation` | `multi_signal_correlation` | `both_signals`, `temporal_multi_signal` | multi-source | correlation_entity, sub_invocations, join_policy, time_window | vague signals, blocked sub-skill | composed dependencies | Flat sub-invocations only. |
| `safe_metadata_discovery` | `metadata_discovery` | `safe_index_discovery`, `field_availability_check` | metadata only | source scope, requested metadata | scope missing | metadata inventory | No actual Q0 question; keep safe and narrow. |
| `other_or_unclear` | no direct route | blocked or clarification | unknown | SOC definition required | unclear pattern/source | policy/detection definition | Example: peer-to-peer style communication needs SOC definition. |

## Deterministic Preflight Boundary

Preflight is a narrow deterministic step before LLM-assisted routing. It catches hard blockers that should not be left to model judgment.

Preflight should catch:

- `this`, `that`, `current`, or similar references without prior context.
- Missing entity for entity-specific queries.
- Missing `notable_id` for notable-specific queries.
- Missing required local IOC lookup where the query explicitly asks for known malicious, suspicious IOC, C2 lookup, or IOC correlation.
- Missing configured vetted detection for DGA, beaconing, C2, encoded PowerShell, lateral movement, scheduled tasks, persistence, or webshell.
- Missing required source binding where the system already knows the source is unavailable.
- Missing SOC-approved threshold or baseline where a threshold is required and no default exists.

Preflight must not become a full deterministic intent router. It should not classify every query by keyword, choose every skill, or replace LLM-assisted semantic routing. Its job is to stop routes that are impossible or unsafe before model routing can decorate them.

## Route Plan Schema

The route plan is a deterministic contract returned by the LLM-assisted router and accepted, corrected, or rejected by deterministic validation.

Required fields:

```json
{
  "route_plan_id": "string",
  "primary_skill": "aggregate_and_rank",
  "pattern_id": "top_n_outbound_connection_sources",
  "operation_type": "top_n",
  "domain": "network",
  "source_class": "cim.network_traffic",
  "entities": [],
  "time_window": {
    "preset": "last_24h",
    "start": null,
    "end": null
  },
  "parameters": {},
  "missing_slots": [],
  "hard_preconditions": [],
  "route_status": "route_ready",
  "model_advisory_metadata": {},
  "deterministic_validation": {
    "validated": false,
    "validator_version": null,
    "errors": [],
    "warnings": []
  }
}
```

Optional fields:

- `post_enrichment`: flat list of allowed enrichment requests.
- `sub_invocations`: flat list of child route plans, allowed only under `multi_signal_correlation`.

Rules:

- Exactly one `primary_skill`.
- Max route-plan depth is 2.
- `sub_invocations` are allowed only when `primary_skill=multi_signal_correlation`.
- Child `sub_invocations` must not contain their own `sub_invocations`.
- `post_enrichment` must be flat.
- Arbitrary LLM-created chains are not allowed.
- Deterministic validator decides execution order.
- `route_status` values are:
  - `route_ready`
  - `clarification_required`
  - `cannot_route_missing_lookup`
  - `cannot_route_missing_detection`
  - `cannot_route_missing_source`
  - `blocked_invalid_composition`
  - `blocked_invalid_parameters`

## Composition Matrix

Allowed compositions:

| Primary skill | Allowed post-enrichment | Allowed sub-invocations |
|---|---|---|
| `aggregate_and_rank` | `entity_context_lookup` | none |
| `threshold_anomaly` | `entity_context_lookup`, `lookup_correlation` | none |
| `sequence_detection` | `entity_context_lookup`, `lookup_correlation` | none |
| `lookup_correlation` | `entity_context_lookup` | none |
| `behavioral_detection_binding` | `entity_context_lookup`, `notable_risk_lookup` | none |
| `notable_risk_lookup` | `entity_context_lookup`, `entity_timeline` | none |
| `entity_timeline` | `entity_context_lookup` | none |
| `metadata_discovery` | none | none |
| `entity_context_lookup` | none | none |
| `multi_signal_correlation` | `entity_context_lookup` after sub-results | flat child invocations only |

Forbidden compositions:

- `metadata_discovery -> behavioral_detection_binding`
- `entity_context_lookup -> SPL execution`
- `lookup_correlation -> external threat-intel call`
- `behavioral_detection_binding -> LLM-authored detection SPL`
- Nested `multi_signal_correlation`
- Child route plan containing `sub_invocations`
- Any composition not explicitly allowed above

## Aggregation Parameter Schema

`aggregate_and_rank` must separate `group_by` from `metric`. The grouped entity is not the measured value.

Parameter schema:

```json
{
  "group_by": {
    "field": "src_ip",
    "source_class": "cim.network_traffic"
  },
  "metric": {
    "type": "count",
    "field": "events"
  },
  "sort": {
    "field": "metric_value",
    "direction": "desc"
  },
  "limit": 10,
  "filters": [],
  "time_window": {
    "preset": "last_24h"
  }
}
```

Allowed metric types: `count`, `sum`, `distinct_count`, `enumerate`, `latest`, `earliest`.

Question: Which source IPs generated the most outbound connections?

Correct shape:

```json
{
  "primary_skill": "aggregate_and_rank",
  "pattern_id": "top_n_outbound_connection_sources",
  "operation_type": "top_n",
  "source_class": "cim.network_traffic",
  "parameters": {
    "group_by": {
      "field": "src_ip"
    },
    "metric": {
      "type": "count",
      "field": "events"
    },
    "sort": {
      "field": "metric_value",
      "direction": "desc"
    }
  }
}
```

Question: Which destination IPs were contacted by many hosts?

Correct shape:

```json
{
  "primary_skill": "aggregate_and_rank",
  "pattern_id": "top_destinations_by_distinct_hosts",
  "operation_type": "top_n",
  "source_class": "cim.network_traffic",
  "parameters": {
    "group_by": {
      "field": "dest_ip"
    },
    "metric": {
      "type": "distinct_count",
      "field": "src_host"
    }
  }
}
```

## Clarification Design

Clarification is driven by missing slots and hard preconditions, not skill uncertainty.

Examples:

- "right now" needs a deterministic time window if no default is configured.
- "known malicious" needs a local IOC lookup.
- "DGA" needs a vetted detection source.
- "critical asset" needs Asset/Identity or CMDB source.
- "this notable" needs `notable_id` or prior context.
- "excessive" needs an explicit threshold or SOC-approved default.

The router should produce `missing_slots` and the appropriate `route_status`. It should not ask vague "which skill did you mean" questions when a concrete missing slot is known.

## Confidence Handling

Model confidence must not be used for routing, tie-breaking, execution, or final decisioning.

If retained at all, confidence must be named `model_self_reported_confidence` and stored only under `model_advisory_metadata`. Deterministic validation must reject or ignore any output where confidence is the only reason to choose a skill, bypass a hard precondition, allow a composition, or mark a route ready.

## Lineage and Synthesis Package Impact

Route plans introduce branching. Investigation lineage must eventually show:

- primary skill
- allowed post-enrichment
- sub-invocations for `multi_signal_correlation`
- route status and validation result per branch
- source, lookup, threshold, or detection dependency per branch

The synthesis package must carry evidence per branch. It must not flatten unsupported claims into one blended answer. Existing Stage 3K.1A safety rules remain:

- no per-source distinct counts in the model-consumed package
- global aggregates are value-or-gap only
- missing evidence stays explicit
- permitted MITRE/action sets remain deterministic
- blocked actions keep `execution_path=none`

## Implementation Recommendation

A. Run the v2 model probe before coding runtime changes.

B. If the v2 probe is acceptable, implement the route-plan schema and deterministic validator as dormant/non-executing first.

C. Add the compact skill catalog only after the schema is stable.

D. Do not modify the SPL validator, CIM support, or tstats/template behavior in this stage.

E. Stage 3K-Q1 remains the SPL validator/template-schema safety work for CIM/tstats.
