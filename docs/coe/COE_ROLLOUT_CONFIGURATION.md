# COE rollout configuration and status (post S2–S6d)

**Audience:** COE operators, staging reviewers, and agents wiring `env/profiles/coe.env.example`.

**Engineering status:** Forward roadmap slices **S2–S6d are complete** on `master` (commits `b365f1e` … `f3484f2`). This document clarifies what is **shipped in code**, what COE **enables via configuration**, what remains **corpus curation**, and what requires **operator-only** Splunk/MCP work.

**Canonical COE profile:** [`env/profiles/coe.env.example`](../../env/profiles/coe.env.example)  
**Profile loader:** [`env/README.md`](../../env/README.md)  
**Live-testing layers (EC parity / mock MCP / real MCP):** [`COE_LIVE_TESTING_GUIDE.md`](COE_LIVE_TESTING_GUIDE.md)

---

## 1. Status classification

Do **not** treat all remaining work as “COE-only.” Use this table:

| Category | What it means | Items |
|----------|----------------|-------|
| **Engineering complete** | Implemented, tested, governance-green; flag-off byte-identical where designed | Guided hybrid dispatch (`AI_SOC_GUIDED_HYBRID_INVESTIGATION_ENABLED`); runtime enrichment loader (`AI_SOC_RUNTIME_ENRICHMENT_ENABLED`); graph `node_trace` / state v2 (`project_chat_pipeline_state_v2`); MITRE evidence preconditions expansion (`T1190`, `T1046` + pilot resolver); SPL template metadata (phishing/ransomware planned rows); P3–P7 pilot enrichment blocks; Answer Guard lab alias (`AI_SOC_ANSWER_GUARD_LAB_ENABLED`); durable session pin store (`AI_SOC_SESSION_STORE_BACKEND=file`) |
| **Corpus curation open** | Offline mapping / catalogue work — not a runtime flag | **64** `missing_authoritative_mapping` rows in BL-004 closeout (`docs/evals/bl004_coverage_closeout_report.md`); incremental `question_use_case_map.json` curation; sample anchors stay **non-routable** |
| **COE rollout config** | Enable safe feature flags in COE profile; restart backend | See §2 recommended flag table |
| **Operator-only** | Credentials, network, smoke on real Splunk | Live Splunk MCP URL/token; `MCP_MODE=registry`; per-server execution enablement; `splunk_run_query` allowlist; per-call analyst confirmation; staging smoke per [`contracts/splunk_mcp_connection_contract.md`](../../contracts/splunk_mcp_connection_contract.md); `schema_confirmed=true` sign-off |
| **Engineering / QA decision** | Optional enablement after explicit parity review | `AI_SOC_PIPELINE_SPLIT_ROUTING_NODES_ENABLED=true` (trace-only split nodes; **default off**) |
| **COE sign-off required** | Template exists but `enabled=false` until real mail/EDR schema confirmed | `email_phishing_header_review`, `endpoint_ransomware_impact_review` SPL templates in `backend/app/spl/templates.json` |

---

## 2. Recommended COE flag table

Apply via `env/profiles/coe.env.example` (or operator overrides in repo-root `.env`). **Do not** change `backend/app/config.py` defaults for production safety.

| Flag | COE recommended | Rationale |
|------|-----------------|-----------|
| `CONTROL_PLANE_ENABLED` | `true` | Required for control-plane trace, evidence plan, guided hybrid rail |
| `AI_SOC_GUIDED_HYBRID_INVESTIGATION_ENABLED` | `true` | Out-of-catalog guided hunts use `guided_hybrid_dispatch` (review-only) |
| `AI_SOC_RUNTIME_ENRICHMENT_ENABLED` | `true` | Loads curated `content_enrichment.json` on runtime paths when use case is activation-eligible |
| `AI_SOC_CURATED_ENRICHMENT_ACTIVATION_ENABLED` | `true` | Legacy alias; either flag OR the other may enable enrichment gate |
| `AI_SOC_ANSWER_GUARD_LAB_ENABLED` | `true` | Lab Answer Guard on synthesis draft (OR `AI_SOC_LLM_ANSWER_GUARD_ENABLED`) |
| `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` | `true` | Enables governed answer-composer path in COE profile; facts remain deterministic |
| `AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED` | `true` | Allows Foundation-Sec to rewrite analyst prose from the governed contract only; model output is non-authoritative and falls back on failure |
| `AI_SOC_LLM_ANSWER_GUARD_ENABLED` | `true` | Runs semantic guard when a governed synthesis draft is produced |
| `AI_SOC_SESSION_STORE_BACKEND` | `file` | Multi-worker-ready structured pins (no transcript) |
| `AI_SOC_SESSION_STORE_FILE_DIR` | `<coe-writable-path>` | e.g. `/var/lib/ai-soc/session_pins` — must be writable by backend user |
| `AI_SOC_PIPELINE_SPLIT_ROUTING_NODES_ENABLED` | **`false`** | Trace-only split nodes; enable only after engineering parity sign-off |
| `MCP_GLOBAL_EXECUTION_ENABLED` | **`false`** | No live/mock MCP execution unless operator explicitly approves |
| `MCP_SERVER_MOCK_EXECUTION_ENABLED` | **`false`** | Same |
| `MCP_SERVER_*_EXECUTION_ENABLED` | **`false`** | Per-server execution stays off until live rollout |
| `AI_SOC_GUIDED_MCP_DISCOVERY_ENABLED` | `false` | Separate COE decision; metadata discovery only when approved |

**Still intentionally off in COE profile (unless operator documents an exception):**

- Live Splunk MCP execution (`MCP_MODE=registry` + execution flags + URL/token + allowlist + per-call analyst confirmation)
- Free-form / LLM-primary SPL execution paths (`candidate_spl` remains review-only; governance gates unchanged)
- `AI_SOC_PIPELINE_SPLIT_ROUTING_NODES_ENABLED` (until QA parity review)
- Phishing/ransomware template `enabled=true` (COE sign-off on real sourcetypes)
- GitHub `SKILL.md` runtime import (provenance only in enrichment JSON)

---

## 3. COE smoke checklist

Run after selecting COE profile and restarting backend (`docker compose up -d --force-recreate backend`).

### 3.1 Control plane trace

- [ ] Send an in-catalog query with `CONTROL_PLANE_ENABLED=true`.
- [ ] Response includes `control_plane_trace` (or collapsed technical trace) with routing / evidence stages.
- [ ] `node_trace` present when visibility builder runs (additive S2 fields).

### 3.2 Guided hybrid dispatch

- [ ] Query: *How should I investigate unusual outbound traffic from an OT host overnight?*
- [ ] `selected_skill` = `guided_investigation` (or guided hybrid path).
- [ ] Trace shows `guided_hybrid_dispatch` / `dispatch_source=guided_hybrid_dispatch`.
- [ ] **No** `graph_node_execution` hop on guided hybrid path.
- [ ] `mcp_allowed` / execution remains **false** (unless live MCP rollout explicitly enabled).

### 3.3 Runtime enrichment in trace

- [ ] Enable `AI_SOC_RUNTIME_ENRICHMENT_ENABLED=true`.
- [ ] Query mapped to a **runtime-active** use case (e.g. `auth_failed_login_spike`, `dns_beaconing_candidate`).
- [ ] `control_plane_trace` or `skill_enrichment` / evidence plan shows enrichment-driven required evidence or `curated_enrichment_trace` summary.
- [ ] Proposed-only rows (e.g. `email_phishing_header_review`) show `metadata_only` / not full runtime activation — not broken routing.

### 3.4 Governed synthesis and Answer Guard lab

- [ ] `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=true` and `AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED=true` if COE wants Foundation-Sec analyst prose.
- [ ] `AI_SOC_ANSWER_GUARD_LAB_ENABLED=true` (or `AI_SOC_LLM_ANSWER_GUARD_ENABLED=true`) with synthesis enabled.
- [ ] Composer trace shows model prose is sourced from the governed AnswerContract / StructuredContext, not raw events or MCP tools.
- [ ] Response `answer_guard.enabled=true` on turns that produce a synthesis draft.
- [ ] Unsupported compromise wording blocked or surfaced as analyst review — not silently promoted.

### 3.5 Session pins (file backend)

- [ ] `AI_SOC_SESSION_STORE_BACKEND=file` and writable `AI_SOC_SESSION_STORE_FILE_DIR`.
- [ ] First turn returns `session_context_status.session_id`.
- [ ] Follow-up MITRE/SPL refine turn reports `used_previous_context=true` when within TTL.
- [ ] Expired session triggers clarification (no silent stale authority).

### 3.6 Execution safety (must pass)

- [ ] `MCP_GLOBAL_EXECUTION_ENABLED=false` → no live/mock executed rows unless operator override documented.
- [ ] `candidate_spl` / `spl_validation.execution_enabled=false` on governed paths.
- [ ] Free-form SPL execution blocked; planned templates do not emit approved executable SPL without COE template enablement.

### 3.7 Regression gate (engineering)

```bash
./scripts/run_stage3_governance_regression.sh
```

---

## 4. What COE config does **not** solve

| Gap | Owner |
|-----|--------|
| 64 BL-004 unmapped question rows | Corpus / mapping curation |
| Live Splunk event shape + MCP wire contract | Operator + staging smoke; adapter exists, but schema sign-off is deployment-specific |
| Enabling phishing/ransomware SPL templates | COE sign-off on indexes/sourcetypes |
| Split-routing trace nodes in production | Engineering/QA after parity review |

---

## 5. Related docs

| Doc | Purpose |
|-----|---------|
| [`plans/AI_SOC_MASTER_PLAN.md`](../../plans/AI_SOC_MASTER_PLAN.md) §R | Slice execution log |
| [`docs/evals/bl004_coverage_closeout_report.md`](../evals/bl004_coverage_closeout_report.md) | 41/105 mapped; 64 gaps |
| [`docs/architecture/real_splunk_mcp_safety_contract.md`](../architecture/real_splunk_mcp_safety_contract.md) | Live MCP gates |
| [`docs/architecture/chat_pipeline_state_v2_and_node_trace.md`](../architecture/chat_pipeline_state_v2_and_node_trace.md) | node_trace spec |
