# T4 unseen generalization qualification set

Prompts-only pack for the frozen production T4 semantic contract.
Reuses `maybe_enrich_t4_semantic` / `SemanticT4Proposal`. Does **not** call Cisco.

Playbook: [`docs/ai/t4_semantic_prompting_playbook.md`](../ai/t4_semantic_prompting_playbook.md).

## Frozen proposal contract

```json
{
  "normalized_goal": "string",
  "evidence_requirements": ["string"],
  "competing_hypotheses": ["string"],
  "semantic_ambiguity": "unambiguous | clarification_required",
  "clarification_required": "boolean",
  "clarification_reason": "string | null",
  "semantic_confidence": "number[0,1]"
}
```

T4 proposes semantic meaning only. Deterministic code remains authority for final
RQC, capabilities, route/owner, ResourcePlan, SPL, MCP, RBAC, HIL, and policy.

## Emit prompts (this VPS)

```bash
PYTHONPATH=backend:. python3 scripts/eval_t4_unseen_qualification.py --emit-prompts \
  --out docs/evals/t4_unseen_qualification.json --check
```

`--live` is refused here.

## Nine unseen cases

Queries are new. No DGA / PowerShell tuning wording. No case-specific few-shots.
No keyword routing.

| ID | Class | Clarification expected |
|---|---|---|
| `unresolved_referent` | genuine unresolved referent | yes |
| `explicit_host` | explicit host/IP/domain | no |
| `explicit_time_range` | explicit time range | no |
| `followup_from_context` | follow-up resolvable from supplied conversation context | no |
| `vague_actionable_hunt` | vague but actionable hunt | no |
| `knowledge_only` | knowledge-only request | no |
| `competing_explanations` | benign/malicious competing explanations | no |
| `semantic_strength_trap` | semantic-strengthening trap (`unusual` ≠ `malicious`) | no |
| `material_dual_meaning` | two materially different SOC meanings | yes |

Each record includes locked/base context, unresolved fields, the exact production
prompt, expected semantic behaviour, clarification yes/no, forbidden strengthening,
and expected authority behaviour.

## Pass gate (for a later COE live run)

- 9/9 schema valid
- 9/9 no invented observed facts
- 9/9 no authority widening
- clarification correct for both approved clarification classes
- no semantic-strengthening failure
- ≥8/9 overall semantic pass

Injected-proposal contract checks run without a model and pin merge behaviour.
Live Cisco scoring is COE-only and is not asserted by this pack.
