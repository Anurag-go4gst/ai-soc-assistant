# Wazuh MCP review → adoption plan + flagship EC scenario

Date: 2026-06-15
Branch: spl-generation-audit
Status: In Progress (§3 EC flagship **built**; §4A **shipped** incl. RBAC + `/chat` shadow + EC sidecar parity; §4B pending approval)
Source reviewed: `https://github.com/Sbharadwaj05/sb-siem-mcp` (third-party Wazuh MCP **server**, MIT, 28 tools, 9 domains)

---

## 1. Context / what the reviewed repo actually is

`sb-siem-mcp` sits on the **opposite side of the wire** from us. It is an MCP
**server** that exposes a live Wazuh deployment as 28 tools. We are the
governed AI-SOC **orchestrator/consumer** — our backend controls MCP, the LLM
never calls MCP directly (CLAUDE.md hard rule).

Key finding on the flagship prompt
("*Show me all critical alerts in the last 6 hours, cross-reference with MITRE
ATT&CK, and check if any affected hosts have unpatched CVEs*"):

- **There is no "cross-reference" tool.** The intelligence is the AI client
  running an autonomous multi-tool loop (their `ADVANCED_FEATURES.md`
  documents the sequence: `alert_summary → list_alerts(min_level=12) →
  get_alert → search_events → query_fim → query_vulnerabilities →
  incident_timeline → rules_coverage_map`).
- **Enrichment is native to Wazuh, not the MCP.** Wazuh alerts already carry
  `rule.mitre.id`, `rule.level`, `rule.pci_dss`, `rule.nist_800_53`, etc.
  CVEs come from Wazuh vulnerability-detector; CIS from Wazuh SCA. The server
  only reads and aggregates pre-stamped fields.

This matters for us: their "magic" = rich pre-mapped data + an autonomous agent
loop. We cannot copy the loop (LLM-drives-MCP is forbidden here). We adopt
**answer shapes** and **safety hardening** instead, rendered deterministically.

### 1.1 Architecture contrast (confirmed on read)

`sb-siem-mcp` **has no skills, no routing, no governance, no answer contract.**
It is 28 Wazuh API wrappers. The entire pipeline is:

```
user prompt → LLM picks tool(s) → LLM calls MCP directly → LLM synthesizes answer
```

All intelligence lives in the model's tool-calling loop. There is no
deterministic authority — severity, MITRE status, actions, and the join logic
are whatever the model decides that turn. That is the opposite of our posture:

| Dimension | sb-siem-mcp | AI-SOC (us) |
|-----------|-------------|-------------|
| Skills / routing | none — raw tool wrappers | deterministic 5-skill router + use-case catalog |
| Who calls MCP | the LLM, directly | backend only; LLM never touches MCP |
| Severity / MITRE / actions | LLM-decided per turn | deterministic policy authority; LLM advisory only |
| Cross-reference (alert→CVE) | LLM reasoning | deterministic backend join |
| Answer shape | free-form LLM prose | governed AnswerContract sections |
| Enrichment | native Wazuh fields (free) | we must stamp/derive it |

**Implication:** their answers look rich because Wazuh hands the model
pre-mapped MITRE/CVE/CIS fields and the model dumps aggregates. To match the
richness *without* surrendering governance, we must own #1 (stamp enrichment on
rows) and #2 (deterministic rollup shapes) ourselves — §3.3 below.

---

## 2. Adoption decisions (what to take, what to skip)

### Adopt — high value, governance-aligned

| Item | Source file | Why | Confidence |
|------|-------------|-----|-----------|
| **A1. Result-row output sanitizer** | `sanitizer.py` | Recursive redaction of secrets (AWS/JWT/SSH/Bearer/password fields) from data **before it reaches the LLM**. Wired at `source_evidence._safe_text` (+ envelope path via `_safe_rows`). | **Shipped** |
| **A2. `risk_score` heatmap formula** | `analysis.py` (`crit*10+high*5+med*2+low`) | Drop-in deterministic answer-section for vuln/host prioritization when a vuln source is onboarded. | 0.8 |
| **A3. `rules_coverage_map` inverted-index pattern** | `analysis.py` | framework-id → rule-ids matrix = a clean "detection gap / coverage" answer card (MITRE/NIST/PCI/GDPR/HIPAA). | 0.75 |
| **A4. `alert_summary` aggregate shape** | `alerts.py` | severity dist + top rules/MITRE/IPs/agents = strong shift-handoff card; matches our AnswerContract section model. | 0.7 |

### Note for COE — future Wazuh-extension (do **not** build now)

| Item | Why deferred |
|------|--------------|
| ~~**N1. RBAC role→tool allowlist**~~ | **Promoted to in-scope — see §4A.4.** User wants RBAC to govern the 7 enabled `splunk_*` tools (esp. `splunk_get_user_info` + `splunk_run_query`). |
| **N2. Confirmation-token gate** (`response.py`, two-step `confirm=True`+expiring token) | Tighter than our bool HIL flag. Only relevant if active-response ever lands. MCP execution stays disabled. |
| **N3. Audit-JSONL rotation + lock** (`audit.py`) | Matches global flock/atomic principle; reference for any future write path. |
| **N4. Wazuh as a 2nd MCP server type** | CLAUDE.md already says "Splunk MCP is first target, not the whole framework." Wazuh tool surface (`wazuh_alert_summary`, `wazuh_query_vulnerabilities`, `wazuh_search_mitre`, `wazuh_sca_*`, `wazuh_run_active_response`) is a clean future registry entry. COE decision. |

### Skip — do not import

- Local child-process MCP model, `WAZUH_INSECURE` TLS-off dev path — conflicts
  with our Nginx / `127.0.0.1` / air-gapped posture.
- Their `validators.py` (Wazuh-API-shaped: 3-digit agent IDs, active-response
  args) — our injection filter + SPL allowlist already cover our surface.
- Token-bucket rate limiter — execution is off; low urgency.

---

## 3. Flagship Experience Center scenario (this PR)

**Decision (user, 2026-06-15): Splunk-native translation, `future_state_preview=False`.**
No drift, no fabricated CVE data. The CVE leg is shown as an **honest degrade**
("vulnerability source not onboarded"), not faked rows.

> **Corrections applied 2026-06-15 (post review).** Original §3 had real bugs,
> verified against code: (1) `use_case_id=None` → empty `mitre_decision`
> (`mitre_kb.py:76`, `scenarios.py:168`); (2) GAP-2 section names
> (`mitre_technique_rollup` etc.) exist in NO contract/frontend; (3) no Splunk
> *notable* sourcetype in `SPL_ALLOWED_SOURCETYPES` → template would fail
> validation; (4) Wazuh `rule_level` weights ≠ Splunk urgency; (5)
> `decide_severity(None)` → P3, understates "critical"; (6) live routing for the
> query unverified; (10) RAG fixture unspecified. Fixes below.

### 3.0 Phase 0 — de-risk BEFORE coding (do first)
1. **Routing probe:** run the exact flagship query through `understand_query` /
   `adjudicate_route` (no EC early-return). "MITRE"+"CVE"+"cross-reference" may
   route `knowledge_recall` / `guided_investigation`, not `attack_discovery`.
   Lock `expected_skill` to the real route or add a deliberate catalog bridge.
   Add `test_routing_critical_alerts_mitre_cve.py`.
2. **Sourcetype/schema:** confirm a *real allowed* index+sourcetype for the
   template (allowlist today = `pgcil_soc` + `pgcil:auth,aws:cloudtrail,pgcil:edr,
   pgcil:dns`). There is **no notable sourcetype** — either target an existing
   sourcetype or deliberately add one to `SPL_ALLOWED_SOURCETYPES`. Decide before
   writing the template.
3. **MITRE authority path:** decide lab use case vs structured-context bridge (§3.1).

### 3.1 Scenario contract (corrected)

```
scenario_id:        critical_alerts_mitre_cve_review
label:              "Critical alerts + MITRE + CVE cross-ref"
category:           "Investigate"
query:              "Show me all critical alerts in the last 6 hours, cross-reference
                     with MITRE ATT&CK, and check if any affected hosts have unpatched CVEs"
expected_skill:     attack_discovery   # Phase-0 probe: catalog match → attack_discovery (not spl_generation/soc_map_alert_mitre)
selected_use_case_id: "critical_notable_mitre_review"   # NEW lab use case (NOT None)
expected_sources:   ["mcp:splunk", "rag:sop"]
sufficiency_mode:   partial_answer
mcp_execution_mode: disabled
candidate_spl:      _scoped_template_spl("<template id from Phase-0 schema>")
```

**MITRE authority (fix #1):** do NOT use `use_case_id=None` — it yields empty
`mitre_decision`. Add a lab use case `critical_notable_mitre_review` to
`catalog.json` + register its candidate techniques in `mitre_kb.py`
(`related_use_cases`) so `map_mitre_for_use_case` returns ≥2 techniques, exactly
like `dns_beaconing_candidate`. This drives `mitre_decision`, the MITRE sidecar
rationale, and the rollup. (Alternative if registry change is unwanted: a
`structured_context.mitre_candidates → _experience_center_mitre_decision` bridge —
heavier, less parity; prefer the lab use case.)

### 3.2 New governed SPL template (`app/spl/templates.json`)

`notable_critical_review_mitre` — read-only review of critical notables in the
last 6h, grouped by MITRE technique + host. Honors `SPL_ALLOWED_*` policy.
EC sources SPL from this template only (no hardcoded SPL — `_scoped_template_spl`).
Template becomes reusable on the live pipeline too.

### 3.3 The answer legs + RICHNESS levers (folded gaps 1–4)

Richness is deterministic, not LLM. Three sources: (1) enrichment stamped on
every row, (2) rollup/aggregation shapes over those rows, (3) deterministic
join. Each leg below is built to be rich, not a one-liner.

**Render via the proven `dns_beaconing` `_analyst_response` pattern — NOT phantom
AnswerContract section types (fix #2).** EC does not call `build_answer_contract`;
rich output comes from a `_analyst_response` scenario branch + fixture data, and
the card renders `mitre_mappings`, `splunk_results_table`, `recommended_actions`,
`key_fields`. Use those existing keys. Generic AnswerContract section types are a
separate frontend+contract PR, out of scope here.

**Leg 1 — Critical alerts → MITRE (works today, made RICH).**

- **GAP-1 (mandatory): every notable fixture row carries `mitre_technique`,
  `mitre_tactic`, and a Splunk-native severity field.** Row shape:
  `{alert_id, host, rule_name, urgency, severity, mitre_technique, mitre_tactic, count, first_seen, last_seen}`.
- MITRE rendered as a **`mitre_mappings` table** in `_analyst_response` (≥2
  techniques, `support="analyst_review"`) + `structured_context.mitre_candidates`,
  driven by the lab use case (§3.1) so `mitre_decision`/sidecar are populated.
- Tactic coverage shown as a column in the MITRE table, not a separate section.

**Leg 2 — Unpatched CVE on affected hosts (honest degrade, rich-ready).**

- **GAP-3: CVE degrade is BOTH (a) a `_analyst_response` `limitations` /
  `missing_evidence` line AND (b) a structured resource-plan step explicitly
  injected** into `evidence_plan["resource_plan"]` (verified: EC sidecars read
  `evidence_plan.resource_plan.steps`, `scenarios.py:370` — it is NOT auto-injected,
  so the scenario builder / `_experience_center_evidence_plan` must add it):
  `{"resource": "vulnerability_source", "status": "not_onboarded", "join_key": "host"}`.
  Mirror the `llm_unservable` CVE phrasing the planner already emits
  (`test_mcp_tool_planner.py`).
- **No CVE rows fabricated.** `trace_explanation` states the leg is planned, not executed.

**GAP-4 — `top_risky_hosts` via risk_score, using SPLUNK severity (fix #4).**

- Adopt the heatmap formula (A2) but map weights from **Splunk `urgency`/`severity`**
  (the template's real fields), NOT Wazuh `rule.level`:
  `critical→10, high→5, medium→2, low→1`. Document the mapping in the template
  `returned_fields`. Render as a second table (`top_risky_hosts`) in
  `_analyst_response`. Extends to `+ CVE weights` when Leg 2 lights up.

**Severity (fix #5):** `decide_severity(use_case_id)` for the new lab use case
must carry a small policy → **P2** for a critical-alert review (or an explicit
`_analyst_response` override with `why_not_higher`). Do not leave it at the P3
`default_no_policy`, which understates a "critical alerts" query.

**RAG leg (fix #10):** add a SOC-KB fixture (`ev-rag-critical-triage`) for
critical-alert triage / CVE-correlation SOP, so `rag_available=True` is backed by
evidence (parity with `dns`'s `ev-rag-c2-ti`).

**(Follow-up, not this PR) detection-gap card** — A3 `rules_coverage_map`
inverted index: MITRE techniques with no detection rule. High value, separate PR.

### 3.4 Files touched

| File | Change |
|------|--------|
| `backend/app/use_cases/catalog.json` | + lab use case `critical_notable_mitre_review` (fix #1) |
| `backend/app/threat/mitre_kb.py` | register ≥2 candidate techniques for that use case (`related_use_cases`) so MITRE is non-empty |
| `backend/app/risk/severity_policy.py` | small policy → P2 for the use case (fix #5) |
| `backend/app/spl/templates.json` | + template against a **real allowed index+sourcetype** (Phase-0 schema; NOT "notable" unless added to allowlist) (fix #9); validate via `scripts/llm_template_audit.py` |
| `backend/app/demo/scenarios.py` | + `CRITICAL_NOTABLE_SPL = _scoped_template_spl(...)` + scenario via the **`dns_beaconing` `_analyst_response` pattern**: fixture rows w/ `mitre_technique`/`mitre_tactic`/`urgency` (GAP-1), `mitre_mappings` table (≥2), `top_risky_hosts` table (urgency-weighted, fix #4), CVE degrade as `limitations`/`missing_evidence` + injected `evidence_plan.resource_plan` step `vulnerability_source:not_onboarded` (GAP-3/fix #3), `ev-rag-critical-triage` RAG fixture (fix #10) |
| `backend/app/tests/` | scenario runs; **routing test** for the live query (fix #6); no CVE rows fabricated; `future_state_preview` False; CVE degrade step present; `mitre_mappings` length ≥2; `top_risky_hosts` ranked |
| Frontend | none — uses existing card keys (`mitre_mappings`, `splunk_results_table`, `recommended_actions`); auto-lists via `/scenarios` |

### 3.5 Guardrails honored

- `EXPERIENCE_CENTER_PROVENANCE.future_state_preview` stays `False`
  (test `test_experience_center_governance_stage3m_ec.py:124` unaffected).
- `live_llm_called=False`, `live_mcp_called=False`, `mcp_execution_mode=disabled`.
- `execution_eligible=false` / candidate SPL non-executable.
- No new flags (flag posture: all-on SOC, MCP execution never).
- EC SPL from template registry (no hardcoded SPL) — drift-proof.

---

## 4. Verification

```bash
# scenario runs + contract
cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests -k "experience_center or scenario or demo" -q
# new lab use case + template: confirm catalogue/105-path eval counts do not regress
PYTHONPATH=../backend:.. python3 -m pytest -q
# governance regression
./scripts/run_stage3_governance_regression.sh
```

Watch for: 105-path / catalogue counts must **not** regress (new template is
review-only, not bound to a vetted use case, so eval coverage should be
unchanged — confirm).

---

## 4A. WS-MCP — air-gapped tool playbook + RBAC + advisory plan-review

> **Status 2026-06-15: §4A.2–§4A.5 + §4A.4 RBAC + `/chat` advisory shadow SHIPPED.**
> Bug fix + playbook + chronology reviewer + `mcp_tool_planner.py` (calibrated
> prompt + `response_format=json_object` → Instruct → parse → deterministic
> review → fallback). 1-LLM decision: Instruct is the planner; Qwen is a
> default-off **failover** behind `AI_SOC_LLM_PLANNER_QWEN_FAILOVER_ENABLED`
> (appended AFTER Instruct, never primary). `response_format` plumbed through
> `local_chat_client`/`failover_client`. Full suite 2182 passed.
> Calibrated-prompt A/B (2026-06-15): with json_object mode + the calibrated
> closed-set prompt, Instruct matched/beat Qwen (caught CVE+MITRE `unservable`,
> no over-claim) — the earlier "Instruct can't plan" was a prompt/config gap.
>
> **Integration status (2026-06-15):** `mcp_rbac_policy.json` + `mcp_rbac.py`
> enforce role inheritance; `select_mcp_tool` / `evaluate_mcp_execution` accept
> `rbac_role` from the FastAPI session (`demo_analyst` → `analyst`). Advisory
> `mcp_tool_plan_shadow` runs on the live `/chat` path when
> `CONTROL_PLANE_ENABLED` (or MCP/SPL interest) and surfaces under
> `control_plane_trace.mcp_tool_plan_shadow` — deterministic-only on the live
> path unless both live-synthesis flags are on (shadow never promotes). §4B
> cyclic evidence loop remains pending approval.
> EC flagship scenario (§3) **built** — `critical_alerts_mitre_cve_review` in `scenarios.py`.
>
> Shipped files: `discovery.py` (user_info→`identity_context`+`rbac_gated`, SAIA
> explicit block, `rbac_gated` descriptor field), `resource_registry_v1.json`
> (user_info tier 3→2, not blocked), `mcp_tool_playbook.json` (new),
> `mcp_tool_chronology.py` (new — `review_proposed_tool_chronology`), tests:
> `test_mcp_tool_chronology.py` (new, 9), updated `test_airgapped_splunk_tool_surface.py`
> + `test_mcp_registry.py`.

Source-of-truth correction (user, 2026-06-15): the **7 core `splunk_*` tools
are all enabled** in air-gapped and should be used; access is governed by
**RBAC**, not by hard-blocking. The 4 `saia_*` tools are **conditional**
(only present if the Splunk AI Assistant for SPL app is installed) and stay
**blocked** (generative). This supersedes the prior "user_info = tier-3 blocked"
classification.

### 4A.1 Corrected tool posture

| Tool | Capability | Gate |
|------|-----------|------|
| `splunk_run_query` | spl_search | execution-gated (HIL + exec flags + COE S5) |
| `splunk_get_info` | server readiness | read-only — **step-0 probe** |
| `splunk_get_indexes` | index_context | read-only |
| `splunk_get_index_info` | index detail | read-only |
| `splunk_get_metadata` | hosts/sources/sourcetypes | read-only |
| `splunk_get_knowledge_objects` | saved searches/macros/datamodels | read-only |
| `splunk_get_user_info` | **current-user identity (self)** | read-only, **RBAC-gated** |
| `saia_*` (4) | generative SPL assist | **conditional + blocked** |
| `splunk_get_user_list`, kvstore mutate, write/admin | — | hard-blocked |

### 4A.2 Code correction (deliberate, test-flipping)

`app/connectors/mcp/discovery.py`: reclassify `splunk_get_user_info` from
`admin_or_sensitive` (→ `blocked=True`) to `identity_context` + `rbac_gated`
(read-only, not blocked). Updates `test_airgapped_splunk_tool_surface.py:33`
(`user_info.blocked is True` → `False`, `rbac_gated is True`). Keep
`splunk_get_user_list` blocked. Add explicit SAIA block assertion
(conditional + generative).

### 4A.3 Declarative tool playbook (`mcp_tool_playbook.json`)

Single source the planner + EC + docs read. Per tool:
`when` (trigger), `why` (evidence need), `preconditions`, `produces`,
`next_tools`, `policy_tier`, `availability`, `rbac_roles`. Encodes the
chronology that today is buried in `splunk_mcp_readiness.py`:

```
step 0  splunk_get_info            readiness/health probe (once per session)
step 1  splunk_get_indexes         what indexes exist
step 2  splunk_get_metadata        sourcetypes/hosts/fields for query building
step 3  splunk_get_index_info      [if target index known] index detail
step 4  splunk_get_knowledge_objects saved searches/macros/datamodels
step 5  splunk_run_query           execute approved normalized_spl (GATED)
(any)   splunk_get_user_info       RBAC identity check when role-scoping needed
```

### 4A.4 RBAC role→tool allowlist (adopt Wazuh **N1**, now in-scope)

Promote from "COE defer" to this plan. JSON policy `mcp_rbac_policy.json`,
roles `viewer / analyst / soc_lead`, role→allowed-tool sets with inheritance.
`splunk_get_user_info` + `splunk_run_query` gated by role; saia/admin/write
never in any role. Deterministic enforcer at tool-selection, mirrors
`safe_tool` gate pattern. RBAC is preference/scoping — it never *grants*
execution past the global MCP gate.

### 4A.5 Advisory LLM plan-review sidecar

LLM proposes/critiques the discovery→search chronology for a query; the
deterministic planner validates against `mcp_tool_playbook.json` (drops
out-of-policy steps, forces blocked/conditional tools out, enforces RBAC).
**LLM advises, deterministic wins, MCP execution stays gated.** No new flags;
reuses the routing-governance advisory pattern (`apply_advisory_promotion`).

### 4A.6 Sequencing

WS-MCP is a **separate PR** from the flagship EC scenario (§3). The EC
scenario ships first (no dependency); WS-MCP playbook/RBAC/plan-review lands
after. Listed here so the corrected posture is canonical.

## 4B. Cyclic governed evidence-collection loop (CP-gated) — CORE SCAFFOLD SHIPPED

> Status 2026-06-15: **core scaffold built (default-off)**, branch
> `cp-cyclic-evidence-loop`. Gated by `CONTROL_PLANE_ENABLED` (CP). CP off =
> linear path unchanged (no loop topology, no loop state leak). No new flag.
>
> **Shipped:** `app/chat/evidence_loop.py` deterministic controller
> (`assess_loop` requirement↔deliverable + sufficiency → route); HUB
> (`graph_node_evidence_planning`) composes the chronology once, idempotent
> re-entry (bug #2); `graph_node_mcp_call` read-only planned discovery hops;
> CP-on cyclic LangGraph (`mcp_call↔HUB`, `execution→HUB`) with explicit
> `recursion_limit` (bug #4); `_hub_route` consumes the assessor verdict
> (execution-phase verdicts mapped — decision B); `control_plane_trace.evidence_loop`
> observability. Tests: controller routes + bounded termination + idempotency,
> graph topology, `_hub_route` verdict consumption, CP-on termination + trace,
> CP-off parity.
>
> **Chronology is the deterministic default** (`deterministic_default_chronology`),
> NOT yet the LLM-reviewed plan (§4B.5 `review_proposed_tool_chronology` deferred).
>
> **Not in this slice (deferred):** merge `mcp_evidence` → `source_evidence`
> (phase 6); live gated discovery-hop execution (planned-only today); the
> imperative-twin loop (bug #1 — loop runs only on the LangGraph entrypoint, which
> needs `langgraph_orchestration_enabled` AND `control_plane_enabled`; the default
> live path is the imperative twin and does NOT cycle); composed-plan dispatch
> coverage (bug #5); single counter covers discovery hops only (execution re-entry
> does not increment `mcp_hops_done`).

### 4B.1 Problem
Today `graph_node_execution → context_finalize → synthesis`, blind. A multi-tool
MCP investigation needs: plan N hops, run one, check what came back against what
was needed, then decide loop / proceed / HIL — and the **execution (`run_query`)
result itself** must sometimes return to planning (empty / partial / wrong-shape),
not march to synthesis.

### 4B.2 Topology — `graph_node_evidence_planning` is the HUB
Reuse the existing node (it is already Evidence plan + Resource Planner over the
capability registry with degrade chains and `resource_decisions`). It becomes the
single loop controller; every evidence-producing node returns to it.

```
              graph_node_evidence_planning (HUB)
              - compose / repair plan (Resource Planner)
              - requirement <-> deliverable map
              - bounded loop counter (MAX_MCP_HOPS = 6)
              - route next (deterministic)
                 |        |          |            |              |
                 v        v          v            v              v
            mcp_call   (disc     graph_node_   human_review   context_finalize
            (1 hop)     loops)   execution     (HIL)          (synthesis)
                 |                    |
                 +---- back to HUB ---+   (execution result returns to HUB too)
```

Two new conditional loopback edges: `mcp_call -> evidence_planning` and
`graph_node_execution -> evidence_planning` (vs forward to `context_finalize`).

### 4B.3 Requirement <-> deliverable (the core new logic)
When the planner decides an MCP call is needed it declares the **requirement**:
the `produces` keys it needs (from `mcp_tool_playbook.json`). After the hop the HUB
maps requirement vs **deliverable** (what actually came back):

| Outcome | HUB route |
|---------|-----------|
| all required `produces` satisfied | proceed (next planned hop, or → execution gate → `run_query`) |
| execution rows sufficient | → `context_finalize` (synthesis) |
| execution **empty** + broaden-eligible | **hand off to `broaden_orchestration`** (analyst-confirmed, cross-turn) — NOT the loop (decision B) |
| too-broad / too-narrow / wrong-shape + budget left | re-plan in loop: new tool / new index / refine → loop |
| partial, more evidence needed | next MCP hop → loop |
| gap, alt resource exists (other MCP / API in degrade chain) | call the alternative → loop |
| gap, analyst could resolve | → `human_review` (HIL) |
| gap, no tool/data produces it (e.g. CVE) | honest degrade (`unservable`) → `context_finalize` |
| `hop_count >= 6` | force HIL or proceed-with-what-we-have |

MCP responses also surface alternative-resource hints (other MCP servers, APIs)
from the Resource Planner capability registry, so the HUB has fallback candidates.

### 4B.4 State additions (`ChatPipelineState`)
```
mcp_chronology: list[str]     # the planned ordered tool list
mcp_cursor: int               # next pending hop
mcp_evidence: list[dict]      # accumulated per-hop outputs (+ feeds source_evidence)
mcp_hops_done: int            # the single loop bound (<= 6)
mcp_requirements: dict        # per-hop required `produces`
sufficiency: str              # sufficient | needs_more | exhausted | capability_gap
```

### 4B.5 Full chain (prompt → answer) — what is built vs to build
| Stage | Status |
|-------|--------|
| LLM prompt for tool call | BUILT — `build_planner_prompts` (calibrated closed-set + `response_format=json_object`); live-verified Instruct returns a valid plan + `unservable` |
| LLM response parse | BUILT — `_extract_proposed_tools` (tolerant JSON) |
| Plan + deterministic review | BUILT — `review_proposed_tool_chronology` (drops blocked/unknown/rbac, reorders, fallback) |
| Declare per-hop requirement | TO BUILD — map plan → required `produces` |
| Execute one MCP hop | TO BUILD — `mcp_call` node (read-only discovery hops); `run_query` stays in `graph_node_execution`, gated |
| Verify result vs requirement | TO BUILD — requirement↔deliverable assessor in HUB (reuse Stage-3J sufficiency) |
| Accumulate results | TO BUILD — `mcp_evidence[]` → merged into `source_evidence`/`structured_context` |
| Pass to followup nodes → answer | PARTIAL — `context_finalize`/answer_contract already read `source_evidence`; must read the accumulated multi-hop set |

### 4B.6 Bugs / shortcomings found in review (must address in build)
1. **Parity twin. DECISION (2026-06-15): UNIFY.** Live runs via the compiled
   LangGraph (`chat_workflow.py`, invoked from `routes_chat*.py`), but
   `pipeline.py:_build_live_chat_response_inner` is an imperative twin running the
   same node fns. **At least `graph_node_evidence_planning` and
   `graph_node_execution` will be unified to a single implementation** (the loop +
   HUB logic lives once, both entrypoints use it) — no dual maintenance for these
   two nodes. Other nodes can stay parity for now; these two must not diverge.
2. **Re-entry idempotency.** `evidence_planning`, routing, and progress emits were
   written single-pass. Re-entering the HUB must NOT re-route, re-compose the plan
   from scratch, or re-emit "queued/understanding". Guard with `mcp_hops_done`/
   cursor so re-entry only does the assess+route step.
3. **broaden-on-empty double-fire. DECISION (2026-06-15): B — loop DEFERS to
   broaden.** Existing `broaden_orchestration` (cross-turn, HIL-confirmed) keeps
   ownership of the execution-empty case. On `run_query` empty the HUB does NOT
   auto-retry/broaden in-loop — it stops looping and hands off to the existing
   analyst-confirmed broaden flow (preserves the HIL scope-widen confirm + reuses
   tested code). The loop owns discovery-hop gathering and partial/wrong-shape
   re-plan; empty-result widening stays with broaden. Build must detect
   "execution empty + broaden-eligible" and route to broaden, not loop.
4. **LangGraph recursion limit.** Cycles need an explicit `recursion_limit` on
   `invoke` derived from MAX_MCP_HOPS (×nodes-per-iteration) or the graph aborts.
   Set it; test the bound.
5. **Composed-plan dispatch path.** `execute_plan_dispatch` (WS0 `has_composed_plan`)
   is a third dispatch route. The loop must cover it or explicitly bypass it.
6. **Single bound, single counter.** All loopbacks (discovery hops + execution
   retries) count against ONE `mcp_hops_done <= 6`. No node retries on its own —
   guaranteed termination.

### 4B.7 Governance (non-negotiable)
- Loop controller, requirement↔deliverable map, routing, termination = deterministic.
- LLM advises the plan only (Instruct primary; Qwen failover flag, default off).
- Bounded at 6; each `run_query` still passes the MCP execution gate + HIL.
- CP-gated: `CONTROL_PLANE_ENABLED` on → loop; off → today's linear path.

### 4B.8 Build phases (on approval)
1. State fields + `MAX_MCP_HOPS=6` + recursion_limit wiring.
2. `mcp_call` node + per-hop requirement declaration.
3. HUB assessor (requirement↔deliverable + Stage-3J sufficiency) + conditional router.
4. Conditional loopback edges (`mcp_call`→HUB, `execution`→HUB) in `chat_workflow.py`
   + parity in the imperative twin (or consolidate — bug #1).
5. Reconcile broaden-on-empty (bug #3). Cover/bypass composed-plan dispatch (bug #5).
6. Accumulate `mcp_evidence[]` → `source_evidence`; verify `context_finalize`/answer
   reads the multi-hop set.
7. Tests: bounded-loop termination, re-entry idempotency, each route (proceed/loop/
   HIL/capability_gap), CP-off regression, governance regression.

## 4C. LLM prompt design (CRITICAL to answer quality)

The A/B test (2026-06-15) proved the headline lesson: **prompt calibration moved
the answer more than model choice did.** Same Instruct model went from
"rambling prose, dropped a needed tool, over-claimed run_query covers CVE" →
"valid JSON, correct dependency-ordered plan, flagged CVE+MITRE unservable" —
only the prompt + decode config changed. Prompts are first-class artifacts here,
versioned and eval'd, not incidental strings.

### 4C.1 The MCP tool-planner prompt (built, live-verified)
Canonical template lives in `build_planner_prompts` (`mcp_tool_planner.py`). Six
calibration elements, each load-bearing (removing any regressed the answer):

1. **Closed tool set** — exact tool names + per-tool `produces`/`preconditions`,
   injected from `mcp_tool_playbook.json`. Turns the task into *selection from a
   closed list*, which weak/local models do far better than open generation.
2. **Explicit BLOCKED list** — names the blocked tools so the model excludes them.
3. **Dependency-ordering rule** — "a tool may appear only after the tools that
   produce its preconditions" → correct chronology.
4. **The indexed-data-only rule** (the single biggest fix): *"splunk_run_query
   only returns events already indexed in Splunk; it cannot fetch CVE/asset/identity
   data not indexed."* This is what stopped the over-claim and produced honest
   `unservable`.
5. **Strict JSON output contract** — `{"tools","reason","excluded","unservable"}`,
   "no prose, no markdown".
6. **Two few-shot examples** — one normal, one **with an `unservable` leg** (the
   example is what taught the model to flag CVE rather than over-claim).

Plus decode config: **`response_format: {"type":"json_object"}`** — forces valid
JSON on llama.cpp; without it Instruct emitted prose and the JSON extractor got
nothing. Mandatory for the planner.

### 4C.2 Grounding inputs to inject (per call)
`query` + `index` + `spl_approved` + `rbac_role` today; extend with: extracted
query signals (entities/time window), known session state (already-discovered
indexes/sourcetypes so it doesn't re-propose discovery), and max-N tools. More
grounded state → better proposal AND easier deterministic validation.

### 4C.3 Anti-patterns (observed, must avoid)
- No `json_object` mode → model rambles prose → unparseable.
- Weak/short prompt (no closed-set, no `unservable` example) → dropped needed
  tools (`metadata`) + over-claimed `run_query` covers CVE + empty `unservable`.
- Open generation instead of closed-set selection → invented/hallucinated tools.

### 4C.4 Prompt as a governed boundary
- The planner prompt only *proposes*; `review_proposed_tool_chronology` is the
  authority (drops blocked/unknown/rbac, reorders, fallback). The prompt can never
  authorize a blocked tool or bypass the gate — a bad prompt degrades to the
  deterministic default, it does not break governance.
- **Live synthesis/narration prompt (separate, live `/chat` only):** facts
  (severity, MITRE+status, actions, SPL, `execution_eligible=false`) stay
  deterministic authority; the model only rewrites prose. The planner prompt and
  the narration prompt are different artifacts with different guards — do not merge.
- **EC path uses NO live prompt** (`coe_synthetic_fixture`); §3 answer quality is
  deterministic/fixture, not prompt-driven.

### 4C.5 Prompt evaluation (before locking the planner on any path)
Small planner eval set (~8–10 queries: catalog, novel, RAG-only, blocked-tool-bait,
multi-unservable) × the calibrated prompt + `json_object`, graded on: valid JSON,
correct tool set, dependency order, no blocked/invented tools, correct `unservable`.
Run against Instruct (and Qwen if the failover flag is on) to confirm robustness
beyond the single flagship case. Lock the template + decode config only after green.

## 5. Out of scope (explicit)

- No Wazuh connector, no 2nd MCP server type (COE — N4).
- No live CVE/vuln data source onboarding.
- No active-response / confirmation-token gate (N2).
- No LLM-drives-MCP loop (forbidden).
- Heatmap/coverage shapes (A2–A4) are **planned follow-ups**, tracked here, not built in this PR unless requested. **A1 sanitizer shipped** (`evidence_sanitizer.py` → `source_evidence._safe_text`); RAG `to_prompt_block` leg is optional belt-and-suspenders follow-up.
