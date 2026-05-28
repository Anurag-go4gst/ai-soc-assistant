# Stage 3K-Q4: Governed SOC Pattern Coverage Pack

**Pack version:** `stage3k_q4_v1`  
**Machine-readable manifest:** `backend/app/coverage/pattern_coverage_v1.json`  
**Baseline:** Q1G `d2d2f0a`, Q2 `1dac76d`, Q3 `1dde303`

## What Q4 proves

Q4 documents how **10 representative** SOC questions from the Stage 3K-Q0 taxonomy (105-question set) map through the **governed bridge**:

1. **Route plan** (runtime skill, parameters, evidence needs)  
2. **Template match** (Q1C) where a vetted `template_ref` exists  
3. **Render / validate metadata** (Q1D; `execution_eligible=false`)  
4. **Evidence contract + lineage** (Q1E) via declared `evidence_contract_ref`  
5. **IOC binding** (Q2) or **detection binding** (Q3) when the question requires it  

Each entry carries honest **readiness** labels, expected **route status**, and **governance** flags (`execution_authorized=false`, no SPL/MCP/final synthesis/Answer Guard).

## What Q4 does not prove

- **Not** all 105 SOC questions are live-ready.  
- **Not** production Splunk execution, MCP execution, or analyst answer changes.  
- **Not** live LLM synthesis, Answer Guard execution, or shadow narration as authoritative answers.  
- **Not** promotion of `sample_only` CIM templates to production.  
- **Not** external threat-intel API calls (IOC remains local registry only).  

**Execution remains disabled** for this experience-center stage. Coverage is readiness and governance metadata only.

## Coverage groups

### Template-only (sample CIM / raw-search metadata)

| coverage_id | question_ref | template_ref | readiness |
|---|---|---|---|
| `cov.q002.top_outbound_source_ips` | q0.q002 | `sample_network_top_outbound_src_tstats` | coe_synthetic_fixture |
| `cov.q017.top_dns_query_hosts` | q0.q017 | `sample_dns_top_query_hosts_from_datamodel` | coe_synthetic_fixture |
| `cov.q046.excessive_failed_logins_sample` | q0.q046 | `sample_auth_failed_login_top_users_tstats` | coe_synthetic_fixture |
| `cov.q062.auth_failed_login_spike_raw` | q0.q062 | `auth_failed_login_spike` | source_ready |

Clarification: threshold/baseline slots (e.g. “excessive” failed logins) are **SOC-defined**; the pack records required slots, not implicit thresholds.

### IOC-dependent (Q2 local registry)

| coverage_id | question_ref | lookup_ref | Default preflight (registry off) |
|---|---|---|---|
| `cov.q004.known_malicious_ips` | q0.q004 | `known_bad_ip` | `cannot_route_missing_lookup` |
| `cov.q036.known_malicious_domains` | q0.q036 | `known_bad_domain` | `cannot_route_missing_lookup` |

With `IOC_REGISTRY_ENABLED=true` and a **fresh** registry, local lookup can satisfy preflight for seeded IOCs. If the registry is **stale**, Q2 returns **`cannot_route_lookup_stale`** and **`lookup_stale`** (not a generic missing-lookup reason).

### Detection-dependent (Q3 vetted binder)

| coverage_id | question_ref | detection_family | detection_ref (when bound) |
|---|---|---|---|
| `cov.q007.dga_detection_binding` | q0.q007 | `dga` | `soc.dga.v1` |
| `cov.q008.beaconing_detection_binding` | q0.q008 | `beaconing` | `soc.beaconing.v1` |

LLM must not author `detection_ref`. Binding is **registry-only**; no detection SPL is rendered or executed in this stage.

### Multi-signal

| coverage_id | question_ref | readiness | Notes |
|---|---|---|---|
| `cov.q032.dns_and_network_multi_signal` | q0.q032 | dependency_missing | Valid `multi_signal_correlation` shape; per-signal detections/baselines not fully seeded |

### Negative / cannot-route

| coverage_id | question_ref | expected_route_status | blockers |
|---|---|---|---|
| `cov.q045.notable_missing_context` | q0.q045 | `clarification_required` | `missing_contextual_reference`, `notable_id` |

Proves the system **refuses** to route without required analyst context.

## Honest readiness labels

| Label | Meaning |
|---|---|
| `coe_synthetic_fixture` | Sample/disabled template or COE seed data only |
| `source_ready` | Active template metadata exists; still non-executable in this stage |
| `ioc_dependent` | Requires Q2 local IOC registry enabled and fresh |
| `detection_dependent` | Requires Q3 detection registry enabled and approved binding |
| `dependency_missing` | Declared bridge gap (e.g. multi-signal baselines not seeded) |
| `blocked_missing_context` | Analyst must supply contextual slots before routing |

## Clarification and blocking behavior

- **Clarification:** entries list `clarification_required` slots (e.g. `time_window`, `notable_id`, `threshold_ref`).  
- **Blocking:** `expected_route_status` and `expected_blockers` describe deterministic preflight under **default** env (`IOC_REGISTRY_ENABLED=false`, `DETECTION_REGISTRY_ENABLED=false`) unless noted otherwise.  
- **Governance:** every entry sets `execution_authorized=false`, `spl_execution_enabled=false`, `mcp_execution_enabled=false`, `llm_final_synthesis_enabled=false`, `answer_guard_enabled=false`.

## Engineering API

```python
from app.coverage.coverage_loader import (
    list_coverage,
    coverage_for_question,
    coverage_for_skill,
    coverage_for_id,
)
```

## Future: Q4A author-time drafter (not in Q4)

An optional **CLI** coverage drafter (`tools/coverage_authoring/`) may assist humans drafting manifest entries using closed enums. It is **not** part of Q4 runtime and is **not** invoked from `/chat`. See `plans/2026-05-28_0523_stage-3k-q4-pattern-coverage-pack.md` (Q4A note).
