# Live Efficacy 100 — System Review and Corrective-Action Backlog

Date: 2026-06-20  
Route tested: authenticated live `POST /chat` on `127.0.0.1:8010`  
Corpus: 100 independently authored questions; no existing bank was consulted  
Execution posture: MCP execution remained default-off

## Executive verdict

The system is **not ready for end-to-end acceptance testing or MCP go-live**.
Its governance defaults remained safe, but live reliability, answer usefulness,
latency, routing, knowledge use, and persisted observability are below an
acceptable operational floor.

The most important result is not the heuristic score; it is the combination of:

- 28/100 live requests returned HTTP 500;
- median successful-turn latency was 103.4 seconds (p95 130.6 seconds, max 157.9 seconds);
- 46/72 successful turns ended in clarification mode;
- 82/100 answers were thin or status-only;
- zero persisted trace timelines/bundles could be retrieved;
- no MITRE mappings were surfaced and the CVE row lacked CVE-source provenance;
- every boundary/safety question received a generic planning stub instead of a clear boundary/refusal answer.

## Results

| Measure | Result |
|---|---:|
| Questions | 100 |
| HTTP 200 | 72 |
| HTTP 500 | 28 |
| Heuristic quality mean / median | 62.5 / 46.0 |
| Rows below 70 | 50 |
| Median / p95 / max latency | 103.4s / 130.6s / 157.9s |
| Full debug telemetry retrieved | 0/100 |
| LLM health restarts | 5 |
| Retried affected questions | 5 |

HTTP 500s by domain: SOC detection 11, Splunk 10, power/OT 4,
cloud/identity 2, knowledge/governance 1.

Category mean quality: power/OT 61.6, SOC detection 41.7, Splunk 28.9,
cloud/identity 47.8, knowledge/governance 51.4, boundary 64.0. Boundary
scores are inflated by safe non-execution; all five still failed to answer the
boundary directly.

## P0 findings

### 1. LLM SPL producer crashes the live route

Representative failed questions were rerun after both backend and LLM recovery;
all failed again. The backend exception is deterministic:

```text
TypeError: FailoverChatClient.generate() got an unexpected keyword argument 'seed'
```

Path: `pipeline._candidate_from_llm_fallback` →
`llm_plan_compiler.generate_llm_spl_via_plan` → `get_detection_plan` →
`FailoverChatClient.generate(seed=...)`.

This explains the concentration of 500s on explicit SPL/detection requests. The
plan compiler was unit-tested with a compatible client, but the actual configured
failover client does not implement the same call contract. Required correction:
make `seed` part of the shared client interface or capability-negotiate it, and
fail closed to the deterministic package instead of raising through `/chat`.

### 2. Persisted debug telemetry is unreadable

Authenticated debug access initially returned 403 as expected. A temporary,
authenticated-read-only test setting was loaded to collect the requested bundles;
the endpoints then returned HTTP 500. Direct reproduction found:

```text
ValueError: dictionary update sequence element #0 has length 1; 2 is required
```

Path: `telemetry.read_store._fetch_events_for_table` calls `dict(row["event"])`
when the database driver returns serialized JSON text rather than a mapping.

Required correction: normalize JSONB/text/dict event values at the read boundary,
add mixed-row fixtures, and make one corrupt event non-fatal to the remaining
timeline. The temporary access setting was removed and the backend recreated.

### 3. Live latency is operationally unacceptable

The raw model usually generated at 6–8 tok/s, yet chat turns took 100–158 seconds.
For sampled turns:

- intent sidecar: ~28–35s;
- MITRE reasoner: commonly 15s;
- narration: ~27–42s;
- 59/72 successful turns exhausted the configured 75s turn budget;
- composer outcomes: 47 blocked, 10 passed, 10 skipped, 5 pending;
- only 10/72 successful turns actually used composed narration.

The LLM health guard itself had a blind spot: it judged only generated tok/s and
called a 52-second probe healthy. The reusable guard now also enforces wall-clock
latency and a bounded probe timeout. During the run it detected queue/time stalls,
restarted `llama-server.service` five times, and recovered the probe each time.

Required correction: enforce the turn deadline before starting optional roles,
reserve a model slot per turn, cancel abandoned requests, cache/skip intent advice
when deterministic confidence is sufficient, and move MITRE/narration off the
blocking path. A healthy 48-token canary does not imply healthy multi-role latency.

## Answer-quality and routing findings

- `knowledge_recall` was selected 62 times, including most investigation and
  Splunk questions. `guided_investigation` appeared 7 times, `attack_discovery`
  twice, and `alert_summary` once; 28 failures had no selected skill.
- 66/72 successful rows were out-of-registry, yet 46 became clarification answers.
- Resource-plan objects existed on successful responses, but 41/72 had no plan
  steps. Only 31 successful turns had actionable composed steps.
- 74/100 rows lacked structured next steps. Common visible output was a status
  message such as “Investigation planning is complete” or “SPL drafting is in
  review-only mode,” even when structured arrays existed elsewhere.
- Answer Guard correctly blocked many unsafe/unsupported compositions, but the
  fallback was too thin. Guard success must preserve a complete deterministic
  analyst package, not merely prevent a bad sentence.
- Five boundary questions were safely non-executing, but none gave a direct
  out-of-scope/refusal response. The prompt-injection/admin-tool request also
  fell to the generic planning stub.

Required correction: repair the full route cascade for novel SOC asks, add a
deterministic out-of-scope/unsafe boundary before LLM work, and enforce a visible
answer completeness floor after guard/fallback processing.

## MCP readiness

MCP execution remained off and no query executed, which is correct. Among 72
successful turns, 70 reported execution skipped and 2 required human review.
Resource/MCP planning metadata was visible on 69 responses, but only one response
contained a fully normalized SPL and only two carried candidate SPL.

Therefore this run validates **fail-closed posture**, not end-to-end MCP readiness.
The system cannot yet prove that enabling MCP would correctly execute the intended
search because the upstream SPL producer crashes, most novel questions misroute,
source binding rarely reaches normalized SPL, and persisted execution telemetry is
unreadable.

Go-live remains blocked until: zero live-route 500s; validated normalized SPL for
representative search families; explicit per-call confirmation; mock and staging
submit/poll/fetch evidence; honest empty-result handling; and readable trace
bundles.

## Skills, MITRE, and CVE

### Skills

Skill selection currently acts more like a label than an answer-shaping contract.
The overwhelming `knowledge_recall` fallback and empty resource plans show that
skills are not reliably contributing domain checklists, evidence legs, or source
requirements. Improve by adding observable skill contribution fields and a gate:
an investigation skill must contribute at least one visible checklist/evidence
section or record a deterministic skip reason.

### MITRE

No analyst-visible MITRE mappings were returned across the corpus. Three explicit
MITRE asks lacked a usable MITRE status. One evidence-shaped MITRE question was
converted into a generic request for alert context despite already supplying a
behavior sequence. Improve evidence extraction before the MITRE gate, distinguish
conceptual mapping from incident confirmation, and expose candidate/requires-
validation/not-claimed buckets in the final card.

### CVE

The CVE test appropriately avoided claiming exploitability, but the response did
not expose snapshot/vendor/scanner provenance in the trace/card. Improve by wiring
CVE source status, freshness, affected-version comparison, asset join keys, and
vendor advisory conflicts into `SourceEvidence` and the visible limitations.

## Role of the LLM

The LLM is currently expensive and often non-value-adding:

- intent advice consumed ~30s on many turns that ultimately clarified or fell back;
- narration was used on only 10 successful turns;
- 47 compositions were blocked by guards;
- generated prose was often generic (“severity not determined,” “review required”)
  and did not replace the deterministic status stub with analyst substance;
- model restarts recovered canary health but did not solve orchestration latency.

Recommended posture: deterministic routing/package first; invoke one targeted LLM
role only when it has a measurable gap to fill; pass a compact schema; enforce a
strict remaining-budget check; and score incremental value (new grounded section,
not merely fluent prose). Keep deterministic authority and MCP separation intact.

## End-to-end readiness decision

**Not ready.** The next test stage should be a corrective P0 cycle, not MCP or
production execution. Suggested order:

1. Fix `FailoverChatClient.generate(seed=...)` and add a live-config regression.
2. Fix telemetry event decoding and verify trace/bundle reads for every turn.
3. Enforce real LLM deadlines/cancellation and reduce blocking roles.
4. Correct novel-SOC routing and visible deterministic fallback completeness.
5. Add skill/MITRE/CVE contribution gates and targeted regressions.
6. Re-run this exact harness; require 100/100 HTTP success, zero critical safety
   failures, p95 under an agreed SLO, and full trace retrieval before mock MCP E2E.
7. Only then run confirmed mock MCP, staging read-only MCP, and limited production
   read-only tests.

## Reusable artifacts

- Corpus: `docs/evals/live_efficacy_100_bank.json`
- Full redacted responses and health history: `docs/evals/live_efficacy_100/results.json`
- Compact generated report: `docs/evals/live_efficacy_100/report.md`
- This review: `docs/evals/live_efficacy_100/findings.md`
- Resumable runner: `scripts/run_live_efficacy_100.py`
- Health/restart guard: `scripts/llm_health_guard.py`

The runner supports checkpoints/resume, per-attempt preservation after recovery,
periodic and slow-turn health checks, restart-and-retry, redaction, full response
capture, debug timeline/bundle capture, deterministic re-analysis, and alternate
bank/output paths for future exercises.
