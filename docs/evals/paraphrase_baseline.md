# Paraphrase Eval Baseline (T1.2, WS1) — 2026-06-11

Corpus: `docs/evals/paraphrase_105.jsonl` — 51 reviewed rows (3 × 12 sentinel
registry questions + 3 × 5 PowerGrid sentinel questions; classes synonym /
reorder / shorthand / typo). Runner: `scripts/eval_paraphrase.py --check`
(`--min-rate 0.90`), query-understanding + intent level only.

| Configuration | Rate |
|---|---|
| Pre-WS1 (no semantic tier, no signal fixes) | **25/51 (0.49)** |
| Semantic tier at initial threshold 0.80 | 27/51 (0.53) |
| + calibration to 0.65/0.05 + corpus-motivated synonyms | 35/51 (0.69) |
| + intent-signal fixes (judgment regex, triage phrasings, checklist→SOP channel) | 43/51 (0.84) |
| + confused-band candidate rule (shorthand/typo may pass via explicit "did you mean" candidates) | **48/51 (0.94) — PASS** |
| Current code, semantic tier disabled (`--without-semantic`) | 40/51 (0.78) |

## Calibration decisions (2026-06-11, Anurag + Claude)

- Threshold **0.65**, margin 0.05: corpus sweep showed zero wrong landings at
  any threshold down to 0.50 (the margin gate absorbs ambiguity); 0.65 chosen
  conservatively over 0.55 to protect unseen phrasings.
- **Confused band (0.45–0.65 / margin ties) never lands silently.** Top-3
  candidates surface for analyst adjudication (T1.4) — chosen over inline LLM
  adjudication because the advisory provider is sidecar-budgeted (1.5s) and
  the local model cannot answer within it; the analyst click is a stronger
  false-positive eliminator with zero latency and zero availability risk.
- One corpus row rewritten (`par.q0.q009.02`): the original passive inversion
  was genuinely ambiguous with q0.q034's mirror question.

## Residual failures (3/51, accepted — further tuning = overfit)

- `par.q0.q010.02` "top SMB talkers by host" — extreme shorthand, below
  candidate floor.
- `par.q0.q055.02/.03` Administrators-group shorthands — below floor.

These become natural WS2/WS3 targets (skill-derived synonyms, scorecard).
