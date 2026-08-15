# Plan 6 D2 — T4 paraphrase accuracy and false-widening

D1 produced **no accepted T4 contracts** on any in-environment serving option. This item therefore cannot score semantic accuracy of a merged T4 proposal. It records that fact, scores the eight residual paraphrases at L3–L5 **without** an accepted hop (deterministic floor), and checks false-widening.

No routing keywords. Production T4 timeout still 2.0s. T4 flag still **false** (Arm A). **Not D3.**

## Serving options that produced accepted contracts

None.

| Option | Accepted contracts | Accuracy on 8 paraphrases |
|---|---|---|
| A local primary 2.0s | 0/9 D0 hops; 0/8 D1 off-path 90s | **n/a — no proposal to score** |
| B Foundation-Sec failover URL | unavailable | n/a |
| C Qwen | unavailable | n/a |
| D N=2 | 0/2 | n/a |

D1 off-path 90s + clean 180s also returned empty timeouts. Tiny classification works; T4 JSON does not complete on this host inside those budgets.

## Eight residual paraphrases

Expected (truth set): `spl_generation_only` / hunt / acceptable `{attack_discovery, spl_generation}` / required `{spl}`.

Observer: `scripts/eval_residual_routing_after_architecture.py --no-pipeline` → `docs/evals/plan6/t4_residual_routing_l3l4.json` (L1–L4). L5 = D0 VPS `/chat` with T4 ON (hop timed out, so committed route is the deterministic floor). Frozen `--arm both` was **not** used as the T4 observer.

| row | L1 | L4 | L5 `/chat` (D0, T4 ON) | L3 family | T4 hop | proposal parsed | accepted | family vs expected | `/chat` ms |
|---|---|---|---|---|---|---|---|---|---|
| rt.para.003 | knowledge_recall | knowledge_recall | knowledge_recall / clarification | clarification_required | invoked, timed_out | no | no | miss | 39294 |
| rt.para.004 | knowledge_recall | knowledge_recall | knowledge_recall / clarification | clarification_required | invoked, timed_out | no | no | miss | 41923 |
| rt.para.005 | knowledge_recall | knowledge_recall | knowledge_recall / clarification | clarification_required | invoked, timed_out | no | no | miss | 40538 |
| rt.para.006 | knowledge_recall | knowledge_recall | knowledge_recall / clarification | clarification_required | invoked, timed_out | no | no | miss | 38273 |
| rt.para.007 | knowledge_recall | knowledge_recall | knowledge_recall / clarification | clarification_required | invoked, timed_out | no | no | miss | 37804 |
| rt.para.008 | knowledge_recall | knowledge_recall | knowledge_recall / clarification | clarification_required | invoked, timed_out | no | no | miss | 42320 |
| rt.para.012 | knowledge_recall | knowledge_recall | knowledge_recall / clarification | clarification_required | invoked, timed_out | no | no | miss | 32949 |
| rt.para.015 | knowledge_recall | knowledge_recall | knowledge_recall / clarification | clarification_required | invoked, timed_out | no | no | miss | 37992 |

L4 tally for these eight: **8/8 unchanged** (`knowledge_recall` / `clarification_required`). L5 matches L4. `/chat` p50 **38784 ms**, p95 **42320 ms**.

T4 semantic accuracy on the eight: **0/8 accepted**, **0/8 parsed**. Route correctness vs truth-set acceptable skills remains **0/8** at L4/L5 because the hop never merged. That is the serving limit D0/D1 measured, not a new routing-table defect.

## False-widening (ambiguous T4)

D1 off-path complete-gen on three T4 cases (`p6.clarify`, `rt.para.009`, `rt.para.013`): all timed out, **0 parsed**, **0 merged**.

| Check | Result |
|---|---|
| Capability widening events | **0** |
| Clarification dropped | **0** |
| Skill key in output | **0** |
| SPL prohibition dropped | **0** |

Fail-closed on timeout is not the same as “the model stays inside the contract.” There was no completed proposal to violate it. L3/L4 for `rt.para.009` / `013` stay `clarification_required` with prohibited `{mcp,spl}`.

## Residual probe (full 25-row set, L1–L4)

`tally_l1_select_route`: unchanged 25. `tally_l4_adjudicated`: resolved_by_architecture **10**, unchanged **15**, regressed **0**.

The 10 L4 resolutions are Plan 5 architecture (live-posture / some paraphrases), **not** T4 semantic serving. The eight D1 residue rows are inside the 15 unchanged.

L5 in-process pipeline was **not** re-run for all 25 (would occupy the single llama slot after D1). L5 for the eight residue rows is the D0 VPS `/chat` arm above.

## Restore / gates

Arm A unchanged. Zero capability-widening events. D3 not decided.
