# T4 semantic prompting playbook

Read this **before** any T4 prompt, schema, few-shot, or merge-rule change.

Validated on Cisco Foundation-Sec 8B (Plans 6–8 C3/U3). `architecture.md` is frozen and read-only. T4 proposes semantic meaning only; deterministic code remains authority for the final ResolvedQueryContract (RQC), capability derivation, route/owner, ResourcePlan, SPL, MCP, RBAC, HIL, and policy/actions.

Production seam: `backend/app/chat/semantic_t4_understanding.py` + `backend/app/chat/contracts/semantic_t4_proposal.py`. Do not parallel-implement T4. Do not call Cisco on the shared VPS to “try a prompt.”

---

## Authority stays tightly bounded

T4 may complete unresolved **semantic meaning**: analysis goal, evidence categories, competing hypotheses, and whether the analyst’s *wording* is ambiguous.

T4 may not:

- select a skill or route
- grant or drop capabilities
- generate or execute SPL
- call MCP
- set RBAC, HIL, or policy
- override locked T1–T3 facts
- invent observed entities, time scopes, or findings

A valid JSON object is not authority. Merge rejects locked-field changes, capability widening, fabricated observations, and clarification that is not semantic.

---

## Field meanings (must stay explicit)

The frozen T4 **proposal** contract is:

| Field | Meaning |
|---|---|
| `normalized_goal` | Restate what the analyst is asking, at the **same semantic strength** as the query. |
| `evidence_requirements` | Proposed **evidence categories** that would answer the ask. Not findings. Not proof. |
| `competing_hypotheses` | **Possibilities** still on the table. Not conclusions. Benign and malicious both stay if the query did not settle them. |
| `semantic_ambiguity` | Ambiguity in **analyst meaning** only. Values: `unambiguous` \| `clarification_required`. |
| `clarification_required` | `true` only under the clarification rule below. |
| `clarification_reason` | What meaning is unresolved. Null when not clarifying. Never “missing logs” or “need a threshold.” |
| `semantic_confidence` | Confidence that we **understood the analyst’s meaning**. Not confidence that an attack occurred. |

Do not treat RQC `ambiguity_state` / `confidence` as synonyms without mapping: those fields mix deterministic investigation/policy states with understanding. T4’s two fields are meaning-only.

---

## Clarification is allowed ONLY for

1. An **unresolved required referent** — the query points at an unnamed event, host, alert, indicator, or prior turn that was not supplied.
2. **Two materially different semantic meanings** — the analyst’s wording itself has two distinct interpretations of *what is being asked*, and choosing one would change the investigation.

**Required referential resolution precedes ordinary semantic completion.** Before completing the hunt/goal, determine whether any required referent depends on supplied conversation/context. If the specific referenced object cannot be resolved from that context, `semantic_ambiguity=clarification_required` and `clarification_required=true`. Naming the missing object generically does not resolve it. Unresolved referents must not be emitted as concrete entities.

Locked upstream `ambiguity_state` does **not** determine T4 `semantic_ambiguity`. Do not copy it.

Everything else is **not** clarification:

- missing logs, evidence, examples, thresholds, or detection criteria
- a broad but actionable hunt (“find credential stuffing against SSO”)
- insufficient evidence to confirm a hypothesis
- “unusual” without a baseline
- follow-ups whose referent is already in supplied conversation context

A hunt is not missing context. Resolve it and list what evidence would answer it.

---

## Three uncertainties that must not be mixed

| Kind | What it is | What T4 does |
|---|---|---|
| **Semantic** | We do not know what the analyst *means*. | May ask. |
| **Evidence** | We know the ask; we do not yet have the logs/rows. | Continue. List evidence categories. Do not ask. |
| **Investigation** | We know the ask; benign and malicious (or other) explanations remain open. | Preserve hypotheses. Do not conclude. Do not ask. |

Semantic uncertainty ≠ evidence uncertainty ≠ investigation uncertainty.

Production merge accepts a T4 clarification proposal only when the frozen
triple is complete (`clarification_required=true`, `semantic_ambiguity=clarification_required`,
non-empty `clarification_reason`) **and** either:

1. `_has_unresolved_referent` is true, or
2. semantic ambiguity is still eligible for T4 and no locked deterministic fact
   contradicts asking (`policy_blocked`, locked meaning, explicit do-not-clarify).

Arbitrary clarification widening (asking while `semantic_ambiguity` stays
`unambiguous`, empty reason, locked meaning) is still rejected. Do not inspect
`clarification_reason` with keywords. Do not weaken this to “ask if context is missing.”

---

## Preserve exact semantic strength

Do not strengthen, moralize, or specialize the analyst’s words.

| Analyst said | Must not become |
|---|---|
| `new domain` | `newly registered domain` |
| `unusual` | `malicious` |
| `looks off` / `odd` | `confirmed C2` / `malware` |
| `talking to` | `exfiltrating to` |
| `failed then succeeded` | `account takeover` (as fact) |

`evidence_requirements` stay categories (“parent process and command line”), not findings (“malicious parent process”). `competing_hypotheses` stay possibilities (“routine patch vs persistence”), not verdicts.

Never invent observed facts (IPs, hosts, users, CVEs, time windows) that the query or locked context did not supply.

---

## Prompt construction rules

- Keep the **schema simple and fixed**. Do not grow it per query class.
- Describe fields with **schema/type semantics**. Do not instruct using copyable sentinel values such as empty strings or `0.0`.
- Use **at most one** small contrastive example for a **known failure class**. Few-shots are prompt assets, not retrieval and not an agent.
- Avoid broad rules such as “ask if context is missing.”
- **No query-specific prompt patches.** If one case fails, do not add that query as a few-shot.
- Production ships one compact contrastive example: clear SOC hunt with missing evidence → do not clarify, versus unresolved semantic meaning → clarify. Do not add query-specific few-shots. Do not add campaign/incident diagnostic wording.

---

## Changing the prompt (required evidence)

A prompt, schema, or few-shot change requires:

1. A **reproducible general failure class** (not one query), and
2. **Unseen validation** on cases that were not used to tune the prompt.

Validate on an **unseen** generalization set (cases that were not used to tune the prompt). Do not reuse DGA / PowerShell tuning wording in new cases. Do not add case-specific few-shots or keyword routing to make a pack pass.

This VPS must not run live Cisco for T4 prompt iteration. Emit production prompts only here; live inference is COE later.

---

## Pointers

- Production hop: `maybe_enrich_t4_semantic` in `semantic_t4_understanding.py`
- Proposal model: `SemanticT4Proposal` (frozen fields in `FROZEN_SEMANTIC_T4_PROPOSAL_FIELDS`)
- Merge / clarification guard: `_merge_proposal`, `_may_merge_t4_clarification`
- Unseen generalization pack (prompts only on this VPS): `scripts/eval_t4_unseen_qualification.py`
- COE serving pack (separate): `docs/evals/t4_coe_qualification.md`
- Architecture (read-only): `architecture.md` §§9–12
