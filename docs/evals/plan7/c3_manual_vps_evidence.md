# Plan 7 C3 — manual same-VPS diagnostic evidence (user-run)

Recorded **separately** from the automated Plan 7 results. These observations come from
**user-run same-VPS LLM-Lab tests**, not from the Plan 7 harness, and are not merged into any
automated eval baseline.

> Earlier C2 correctly measured zero accepted semantic value under the then-current production
> prompt and 2-second serving posture. Subsequent same-VPS diagnostic testing demonstrated that
> Cisco 8B can produce useful T4 semantic completion when given a compact field-constrained
> few-shot prompt.

Earlier C2 evidence is **not** rewritten. Both measurements stand: C2 measured the production
prompt at a 2 s bound; this records the same model behaving usefully under a different prompt and
a longer bound.

## Observed behaviours

**1. Lateral-movement query**
- produced a meaningful investigation objective
- identified the threat relationship
- produced useful evidence requirements
- **no tool/SPL execution leakage**

**2. DNS / C2 query**
- **preserved competing hypotheses** — C2 versus legitimate software
- generated relevant evidence requirements
- **no premature malicious classification**

**3. Contextually incomplete follow-up**
- correctly set `clarification_required=true`
- asked for the missing event/comparison context
- confidence remained appropriately low

## Resulting classification

```
T4 semantic role                 VIABLE
Cisco 8B semantic capability     VIABLE / PROVISIONALLY PROVEN
current production T4 prompt     NEEDS HARDENING
few-shot prompting               MATERIALLY BENEFICIAL
structured output                USE CONSTRAINED JSON
current 2-second VPS timeout     NON-VIABLE
VPS model runtime stability      NEEDS EXISTING RELIABILITY HANDLING
```

## Status of this evidence

Diagnostic and provisional. It justified the C3 decision
(`REMEDIATE_EXISTING_T4_IN_PLACE`) and the move to a bounded
`VPS_T4_REMEDIATION_TIMEOUT = 120 s`. It is **not** a Plan 7 acceptance result — the automated
re-run after the minimum prompt correction is what must carry that weight, and T4 remains a
**hard GO requirement** at E2.
