# Plan 6 D2 — residual routing L1–L4 (script reused, `--no-pipeline`)

Same measurement as Plan 5 D0 residual probe, written here so Plan 6 D2 does not treat frozen `--arm both` as the T4 observer. L5 skipped in-process (single llama slot). L5 for the eight residue paraphrases is D0 VPS `/chat` in `t4_paraphrase_accuracy.md`.

Measurement only. No routing rule added, no skill contract widened, no frozen baseline refreshed.

Rows: **25** (d2 3 · ownership 10 · paraphrase 12).

| Layer | resolved | unchanged | regressed |
|---|---|---|---|
| L1 `select_route_from_understanding` | 0 | 25 | 0 |
| L4 `adjudicate_route` | 10 | 15 | 0 |
| L5 full `/chat` | 0 | 0 | 0 |

## Rows

| row | class | L1 | L2 | L4 | L5 | contract family / goal / caps | verdict (L4) |
|---|---|---|---|---|---|---|---|
| `rt.d1.003` | ownership_deferred | knowledge_recall | knowledge_recall | spl_generation | n/a | spl_generation_only / spl_artifact / spl | resolved_by_architecture |
| `rt.d1.005` | ownership_deferred | knowledge_recall | knowledge_recall | spl_generation | n/a | spl_generation_only / spl_artifact / spl | resolved_by_architecture |
| `rt.d1.006` | ownership_deferred | knowledge_recall | knowledge_recall | spl_generation | n/a | spl_generation_only / spl_artifact / spl | resolved_by_architecture |
| `rt.d1.011` | ownership_deferred | knowledge_recall | knowledge_recall | spl_generation | n/a | spl_generation_only / spl_artifact / spl | resolved_by_architecture |
| `rt.d1.012` | ownership_deferred | knowledge_recall | knowledge_recall | spl_generation | n/a | spl_generation_only / spl_artifact / spl | resolved_by_architecture |
| `rt.d1.013` | ownership_deferred | knowledge_recall | knowledge_recall | spl_generation | n/a | spl_generation_only / spl_artifact / spl | resolved_by_architecture |
| `rt.d1.014` | ownership_deferred | knowledge_recall | knowledge_recall | spl_generation | n/a | spl_generation_only / spl_artifact / spl | resolved_by_architecture |
| `rt.d2.003` | d2_defect | knowledge_recall | knowledge_recall | spl_generation | n/a | spl_generation_only / spl_artifact / spl | resolved_by_architecture |
| `rt.d2.010` | d2_defect | knowledge_recall | knowledge_recall | knowledge_recall | n/a | clarification_required / clarification / - | unchanged |
| `rt.d2.017` | d2_defect | knowledge_recall | knowledge_recall | knowledge_recall | n/a | clarification_required / clarification / - | unchanged |
| `rt.para.001` | paraphrase | knowledge_recall | knowledge_recall | spl_generation | n/a | spl_generation_only / spl_artifact / spl | resolved_by_architecture |
| `rt.para.002` | paraphrase | spl_generation | spl_generation | spl_generation | n/a | spl_generation_only / spl_artifact / spl | unchanged |
| `rt.para.003` | paraphrase | knowledge_recall | knowledge_recall | knowledge_recall | n/a | clarification_required / clarification / - | unchanged |
| `rt.para.004` | paraphrase | knowledge_recall | knowledge_recall | knowledge_recall | n/a | clarification_required / clarification / - | unchanged |
| `rt.para.005` | paraphrase | knowledge_recall | knowledge_recall | knowledge_recall | n/a | clarification_required / clarification / - | unchanged |
| `rt.para.006` | paraphrase | knowledge_recall | knowledge_recall | knowledge_recall | n/a | clarification_required / clarification / - | unchanged |
| `rt.para.007` | paraphrase | knowledge_recall | knowledge_recall | knowledge_recall | n/a | clarification_required / clarification / - | unchanged |
| `rt.para.008` | paraphrase | knowledge_recall | knowledge_recall | knowledge_recall | n/a | clarification_required / clarification / - | unchanged |
| `rt.para.009` | ownership_deferred | knowledge_recall | knowledge_recall | knowledge_recall | n/a | clarification_required / clarification / - | unchanged |
| `rt.para.010` | paraphrase | knowledge_recall | knowledge_recall | spl_generation | n/a | spl_generation_only / spl_artifact / spl | resolved_by_architecture |
| `rt.para.011` | paraphrase | attack_discovery | attack_discovery | attack_discovery | n/a | live_investigation / procedural_steps / mcp,spl | unchanged |
| `rt.para.012` | paraphrase | knowledge_recall | knowledge_recall | knowledge_recall | n/a | clarification_required / clarification / - | unchanged |
| `rt.para.013` | ownership_deferred | knowledge_recall | knowledge_recall | knowledge_recall | n/a | clarification_required / clarification / - | unchanged |
| `rt.para.014` | ownership_deferred | knowledge_recall | knowledge_recall | knowledge_recall | n/a | clarification_required / clarification / - | unchanged |
| `rt.para.015` | paraphrase | knowledge_recall | knowledge_recall | knowledge_recall | n/a | clarification_required / clarification / - | unchanged |
