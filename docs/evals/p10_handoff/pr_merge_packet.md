# P10 PR / merge handoff packet

**STATUS:** READY_FOR_OPERATOR_NETWORK_ACTIONS  
**Prepared:** 2026-08-26  
**Prepared on branch:** `ws/p10-execution`  
**STOP:** Do **not** push, open PR, merge, or deploy until the operator explicitly authorizes network actions.

---

## 0. Baselines (do not confuse)

| Label | SHA |
|---|---|
| **P10_PRODUCT_BASELINE_SHA** (product promotion) | `c109402d69956df455a780fd49a191fa173ab7ac` |
| **P10_LINEAGE_START_SHA** / handoff tip (includes P9 evidence) | `09f02e46308b7918c81b525dfcbb629da607d9e7` |
| **PRODUCT_CODE_CHANGED_IN_P9** | NO |
| **PRODUCT_CODE_DELTA** `c109402d..09f02e46` | **NONE** (docs/plans only) |

Paths changed `c109402d..09f02e46` (evidence only):

```
docs/evals/p9_promotion/branch_packet.md
docs/evals/p9_promotion/gate_matrix_v1.json
docs/evals/p9_promotion/go_nogo_v1.json
docs/evals/p9_promotion/linux_backend_attest.txt
docs/evals/p9_promotion/residual_failure_ledger_v1.json
plans/2026-08-25_1806_ai-soc-master-parallel-closure.md
plans/LOOP_RUNNER_ai-soc-master-parallel-closure.md
```

---

## 1. Recommended merge target and source

| Item | Value |
|---|---|
| Integration branch (product tip) | `feat/complete-or-abstain-t4-ux` @ `c109402d…` |
| Handoff / evidence tip | `ws/p10-execution` @ `09f02e46…` (or fast-forward primary to tip after review) |
| Suggested PR base | `origin/master` (measured `49e545d9…` at packet time; **re-fetch before push**) |
| Local `master` | `49c5a494…` (behind origin; do not use without fetch) |
| Commits `origin/master..c109402d` | **101** |
| Commits `origin/master..09f02e46` | **103** (101 product + 2 P9 docs) |

**Merge intent:** Promote the reconciled parallel-closure history into `master` with P9 evidence retained. Prefer merging **`09f02e46`** (lineage tip) so promotion docs are not dropped; product behavior remains `c109402d`.

---

## 2. Verified merge order (plan § Reconciliation)

All landmarks are ancestors of tip `09f02e46`:

| Order | Stream | Landmark SHA | Subject (abbrev) |
|---|---|---|---|
| 0 | P0.1 RACES | `ae03a250…` | advance freeze baseline |
| 1 | A TRACE (P1) | `fd77d58e…` | freeze stable oracle contract |
| 2 | B SPL (P2) | `7fbdf83f…` | P2 RACES baseline |
| 3 | D POLICY (P4) | `cdb146df…` | governed studio configuration |
| 4 | C EVAL bank (P3→P5) | `caeab0d7…` / `f1b741f8…` | activate L2 contracts / remediation journeys |
| 5 | C rationalization (P6) | `f87fd7e1…` | KEEP ledger + l2_slow |
| 6 | F L3 / P8 product | `c109402d…` | posture/remediation/chat journeys + retirement |
| 7 | E UI (P7+) | `7ce96d69…` / `27970ea4…` / `f28ff3f7…` | Approve/Edit/Cancel; remove demo controls |
| 8 | F promotion (P9) | `5854ad11…` → `09f02e46…` | Mac + Linux promotion evidence |

---

## 3. Worktree cleanliness (P10)

```
P10_WORKTREE=/Users/aagarwal/Downloads/ai-soc-p10-execution
P10_BRANCH=ws/p10-execution
git status: clean (no staged/unstaged product dirt at packet start)
```

Primary `feat/complete-or-abstain-t4-ux` retains **local-only** dirt (do not stage/merge):

- `.claude/settings.local.json`
- `docs/evals/p8_d/final_browser/` (untracked on primary)
- `docs/evals/p8_l3/p8_primary_ff_*.json` (untracked on primary)
- `ws/`
- unrelated draft plans on primary

---

## 4. PR summary (draft for operator)

### Title

`Promote complete-or-abstain parallel closure (P0–P9) — product c109402d + promotion evidence`

### Body

```markdown
## Summary
- Reconciled parallel-closure streams (TRACE, SPL, policy, L2 bank, rationalization, UI, L3/P8 product) onto integration tip `c109402d`.
- P9 promotion: Mac+Linux backend **7109/0** at exact product SHA; three inherited residuals operator-accepted.
- P9 evidence tip `09f02e46` is docs/plans only (`PRODUCT_CODE_CHANGED_IN_P9=NO`).
- Live MCP remains OFF. Production GO deferred (P11 separate).

## Test plan
- [ ] Confirm `git rev-parse` of merge tip equals `09f02e46` (or document product-only merge of `c109402d`)
- [ ] Mac: `cd backend && python3 -m pytest -q -p no:cacheprovider` → expect 7109 passed / 0 failed
- [ ] Linux exact-SHA: compose backend clean-env pytest → expect 7109/0 (see `docs/evals/p9_promotion/linux_backend_attest.txt`)
- [ ] RACES 8; protected baseline `--check` 15/15; harness 6/6
- [ ] Frozen bank canonical hash `5f78ccbe…` for `docs/evals/p8_l3/bank_v1.json`
- [ ] Confirm accepted residuals remain named (not “PASS”): rt.para.011, golden Tier0×2
- [ ] Spot-check S4 posture → guided_investigation; J6/J7 remediation CTA rules; production `/chat` isolation; EC `/scenarios`
- [ ] Do **not** enable live MCP in this PR

## Residuals (accepted inherited — not blockers)
- `rt.para.011`
- `tier0.top_failed_login_spl_missing_binding_clarification`
- `tier0.aws_security_group_modifications_spl_only`

## Rollback
- Revert merge commit on `master`, or reset deploy pointer to pre-merge `origin/master`.
- Product rollback SHA: previous `origin/master` tip recorded at merge time.
- Do not “fix forward” by editing frozen bank or weakening validators.
```

---

## 5. Tests / gates already proven (P9) — citation only

| Gate | Result | SHA |
|---|---|---|
| Mac backend | 7109 / 0 / 45 skip / 6 xfail | `c109402d` |
| Linux exact-SHA | 7109 / 0 / 45 skip / 6 xfail | `c109402d` |
| Frontend | 119 + build PASS | `c109402d` |
| RACES | 8 PASS | `c109402d` |
| Protected baseline | 15/15 | `c109402d` |
| Bank (canonical) | `5f78ccbe1940149a67dcd1052140c44c854ec42a409d7644b47e5357010dbf51` | unchanged |
| P9 decision | `P9_COMPLETE` / `GO_FULL_PROMOTION` | evidence `09f02e46` |

P10 is **documentation/handoff only** — no product re-implementation; full Mac/Linux matrix not re-run in P10.

---

## 6. Protected approvals

| REQUEST_ID | File | Packet status | Product tip observation |
|---|---|---|---|
| P8-J7-KNOWLEDGE-REMEDIATION-OFFER | `pipeline.py` / remediation path | Packet authored; text says “not applied” | Product includes `remediation_offer_cta_eligible` + `ed1445ae` evidence gate; J7 tests present |
| P8-D-CHATPANEL-SCENARIO-PICKER | `ChatPanel.tsx` | Packet authored | `DemoScenarioPicker` not imported in production ChatPanel; `27970ea4` removed demo controls |

**Operator action:** Confirm protected queue entries are **superseded by applied product commits** (or explicitly approve residual packet diffs if any remain). Do not re-apply blindly.

Historical applied protected wiring (example): `P2-FINAL-RQC-PIPELINE-WIRING` @ `5921f1d0` — APPLIED_VERIFIED.

---

## 7. Operator network commands (DO NOT RUN until approved)

```bash
# 0) Fetch and record pre-merge master tip
cd /Users/aagarwal/Downloads/ai-soc-p10-execution   # or primary after integrating tip
git fetch origin
PRE_MERGE_MASTER=$(git rev-parse origin/master)
echo "PRE_MERGE_MASTER=$PRE_MERGE_MASTER"

# 1) Ensure handoff tip
git rev-parse HEAD   # expect 09f02e46… (or later docs-only P10 packet commit)

# 2) Push handoff branch (operator-authorized)
git push -u origin ws/p10-execution

# 3) Open PR against master (operator-authorized)
gh pr create --base master --head ws/p10-execution \
  --title "Promote complete-or-abstain parallel closure (P0–P9)" \
  --body-file docs/evals/p10_handoff/pr_merge_packet.md

# Alternative: push feat/complete-or-abstain-t4-ux after fast-forwarding it to 09f02e46 on a clean tree
# (preserve primary local-only dirt; do not commit it)

# 4) Merge only after review (operator)
# gh pr merge <N> --merge   # prefer merge commit to preserve history; avoid squash of evidence

# 5) Post-merge exact-SHA validation
git fetch origin && git checkout master && git pull --ff-only
git rev-parse HEAD   # record POST_MERGE_SHA
# Product behavior check: tree for backend/frontend should match c109402d
git diff --stat c109402d69956df455a780fd49a191fa173ab7ac HEAD -- backend frontend
cd backend && python3 -m pytest -q -p no:cacheprovider
```

---

## 8. Rollback

1. Record `PRE_MERGE_MASTER` before merge.  
2. If merge is bad: `git revert -m 1 <merge_sha>` on `master`, or restore deploy to `PRE_MERGE_MASTER`.  
3. Re-open promotion (P9) if product behavior changes after merge.  
4. Never “heal” by editing `docs/evals/p8_l3/bank_v1.json` or weakening SPL/MCP gates.

---

## 9. Explicit non-goals (this packet)

- No push / PR / merge / deploy by the agent  
- No P11 live Splunk MCP  
- No product code changes in P10  
- No fix of accepted inherited residuals  
- No email/communication downstream orchestration (`FUTURE_POST_MASTER_PLAN_GAP`)

---

## 10. STOP

**Awaiting operator** to authorize network actions and merge.  
Next phase (P11) only after approved merge **and** separate COE live-MCP authorization.
