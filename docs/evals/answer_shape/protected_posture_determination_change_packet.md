# Protected change packet — `posture_determination` routing signal

**STATUS: PREPARED, NOT APPLIED.** No file in this packet was modified in this
loop. Applying it is an operator decision.

## PROBLEM

An investigation-class question that states its own objective dead-ends in a
hollow clarification. Trace `fe4e3657-7ce5-4b3e-94db-5fb6a976ce52`, EC scenario
S4:

> A critical zero-day affects our internet-facing VPN gateways. We have no
> detection rule or SOAR playbook yet for VPN detection. **Determine** whether we
> are exposed and what immediate controls we should apply.

Answer: *"Investigation planning is complete. Provide source profile details…"*
with `llm_call_count: 0`, `analyst_summary: null`,
`investigation_planning_trace: null`, `investigation_outcome: null`,
`proposed_actions: null`. No plan, no findings, no remediation proposal, and no
model call. **This is not caused by MCP being unavailable** — no MCP call was
ever planned.

## CURRENT ROUTING TRACE

1. `extract_query_signals` returns exactly one true signal:
   `security_log_investigation`. `soc_actionable_hunt` is **false**.
2. `soc_actionable_hunt` (`query_signals.py:1183`) requires
   `_has_detection_verb(...)` AND `_has_security_telemetry_subject(...)`. The
   subject fires (`vpn`, `detection`); the verb does not. `_DETECTION_VERB_RE`
   (`query_signals.py:1456`) lists *retrieval* verbs — show, list, identify,
   detect, review, correlate, check, "are there" — and no posture verb.
3. `classify_intent` therefore skips the guided branch
   (`intent_classifier.py:1103`) and falls to the terminal default
   (`intent_classifier.py:1120`): `intent_family="clarification_required"`,
   reason *"Insufficient deterministic intent signals"*.
4. `evidence_planner.py:176` matches
   `if intent.requires_clarification or family == "clarification_required"` and
   returns an EvidencePlan with `needs_rag=False, needs_spl=False,
   needs_mcp=False, needs_mitre=False`.

One missing verb switches off every stage.

## ROOT CAUSE

The precedence in `classify_intent` is:

```
1088   if soc_detection_intent                          -> spl_generation_only   (SPL floor)
1103   if soc_actionable_hunt and not live_data_request -> guided_investigation  (guided floor)
1120   terminal                                          -> clarification_required
```

and `soc_actionable_hunt` **feeds both**: it is a disjunct of
`soc_detection_intent` (`query_signals.py:1298`) and of `live_data_request`
(`query_signals.py:1288`). Because the SPL floor is tested first, anything that
widens `soc_actionable_hunt` reaches SPL generation before it can reach guided
investigation.

## REJECTED FIX — measured, then reverted

Adding determine/assess/evaluate/investigate to `_DETECTION_VERB_RE`:

| | before | after |
|---|---|---|
| answer-shape pass rate | 1/10 | **0/10** |
| `AS.P1` | PASS, shape 1.00, `guided_investigation` | FAIL, shape 0.33, `spl_generation` |
| rows on `spl_generation` | 3 | 5 |

It moved posture questions **away** from guided investigation and into SPL
generation, exactly as the shared-signal analysis predicts. Reverted. Do not
retry.

## PROPOSED SIGNAL

A separate deterministic signal that feeds **only** the guided decision.

```python
#: An investigation OBJECTIVE: the analyst states a question about security
#: posture and expects an investigation, not a retrieval. Deliberately NOT a
#: disjunct of soc_detection_intent or live_data_request -- that shared-signal
#: coupling is what made the naive verb widening regress.
_POSTURE_OBJECTIVE_RE = re.compile(
    r"\b(?:determine|assess|evaluate|ascertain)\s+(?:whether|if|our|the)"
    r"|\b(?:determine|assess|evaluate|ascertain)\b(?=[^.?]*\b(?:whether|if|exposed|"
    r"affected|impacted|compromise|posture|risk|incident)\b)"
    r"|\bare\s+we\s+(?:exposed|affected|impacted|vulnerable|at\s+risk)\b"
    r"|\bdo\s+we\s+have\s+(?:any\s+)?(?:exposure|vulnerable|affected|impacted)\b"
    r"|\bis\s+this\s+a\s+(?:real|genuine|true)\s+(?:incident|compromise|attack)\b",
    re.IGNORECASE,
)

#: Posture questions name a security CONDITION, not a telemetry source, so the
#: existing telemetry-subject gate is the wrong subject test for them.
_POSTURE_SUBJECT_RE = re.compile(
    r"\b(?:exposed|exposure|affected|impacted|vulnerable|vulnerability|compromise|"
    r"compromised|breach|breached|incident|campaign|intrusion|threat|attack|"
    r"zero-?day|cve-\d|posture|risk)\b",
    re.IGNORECASE,
)
```

```python
posture_determination = bool(
    _POSTURE_OBJECTIVE_RE.search(normalized)
    and (_has_security_telemetry_subject(normalized) or _POSTURE_SUBJECT_RE.search(normalized))
    and not explicit_run_spl
    and not run_spl
    and not spl_generation
    and not explicit_search_intent
    and not block_or_contain
    and not knowledge_definition
    and not playbook_procedure
    and not sop_show_request
    and not guidance_request
)
```

Offline validation of this exact predicate against the §9.5 cases (computed
without modifying production code): **10/11**. See "EXPECTED CASES" below.

## ROUTING PRECEDENCE

Unchanged except for one new branch inserted **above** the SPL floor and
guarded so it cannot capture explicit generation or retrieval:

```
A. explicit SPL authoring / runtime profile     -> spl_generation      (unchanged, above)
B. posture_determination                        -> guided_investigation  (NEW)
C. soc_detection_intent                         -> spl_generation_only (unchanged)
D. soc_actionable_hunt and not live_data_request-> guided_investigation (unchanged)
E. terminal                                      -> clarification_required (unchanged)
```

B sits above C because a stated investigation objective is a stronger signal
than the generic analytics floor; B's own guards (`explicit_search_intent`,
`spl_generation`, `explicit_run_spl`) yield to A and to explicit retrieval.

## EXACT PROTECTED FILES

| File | On the literal protected list? | Why operator-gated anyway |
|---|---|---|
| `backend/app/chat/query_signals.py` | No | Adds a deterministic routing signal |
| `backend/app/chat/intent_classifier.py` | No | Changes deterministic routing precedence for a query family |

Neither file appears on the stated protected-path list. They are gated here
because this loop's mission scopes Phase D to design only, and because the
change alters deterministic routing authority — the class of change that must
be an explicit decision rather than a side effect.

## EXACT DIFF

```diff
--- a/backend/app/chat/query_signals.py
+++ b/backend/app/chat/query_signals.py
@@ -1190,6 +1190,20 @@
         and not block_or_contain
         and not explicit_run_spl
     )
 
+    # Investigation OBJECTIVE, distinct from soc_actionable_hunt on purpose.
+    # It is NOT a disjunct of soc_detection_intent or live_data_request: that
+    # shared-signal coupling is what made widening _DETECTION_VERB_RE regress
+    # the answer-shape eval from 1/10 to 0/10.
+    posture_determination = bool(
+        _POSTURE_OBJECTIVE_RE.search(normalized)
+        and (_has_security_telemetry_subject(normalized) or _POSTURE_SUBJECT_RE.search(normalized))
+        and not explicit_run_spl
+        and not run_spl
+        and not spl_generation
+        and not explicit_search_intent
+        and not block_or_contain
+        and not knowledge_definition
+        and not playbook_procedure
+        and not sop_show_request
+        and not guidance_request
+    )
+
@@ -1402,6 +1416,7 @@
         "soc_actionable_hunt": soc_actionable_hunt,
+        "posture_determination": posture_determination,
@@ -1456,6 +1471,24 @@
 _DETECTION_VERB_RE = re.compile(
     ...unchanged...
 )
+_POSTURE_OBJECTIVE_RE = re.compile(
+    r"\b(?:determine|assess|evaluate|ascertain)\s+(?:whether|if|our|the)"
+    r"|\b(?:determine|assess|evaluate|ascertain)\b(?=[^.?]*\b(?:whether|if|exposed|"
+    r"affected|impacted|compromise|posture|risk|incident)\b)"
+    r"|\bare\s+we\s+(?:exposed|affected|impacted|vulnerable|at\s+risk)\b"
+    r"|\bdo\s+we\s+have\s+(?:any\s+)?(?:exposure|vulnerable|affected|impacted)\b"
+    r"|\bis\s+this\s+a\s+(?:real|genuine|true)\s+(?:incident|compromise|attack)\b",
+    re.IGNORECASE,
+)
+_POSTURE_SUBJECT_RE = re.compile(
+    r"\b(?:exposed|exposure|affected|impacted|vulnerable|vulnerability|compromise|"
+    r"compromised|breach|breached|incident|campaign|intrusion|threat|attack|"
+    r"zero-?day|cve-\d|posture|risk)\b",
+    re.IGNORECASE,
+)
```

```diff
--- a/backend/app/chat/intent_classifier.py
+++ b/backend/app/chat/intent_classifier.py
@@ -1087,6 +1087,24 @@
+    # An investigation objective outranks the generic analytics floor: the
+    # analyst asked what is true, not for a query. The Resource Planner still
+    # decides which evidence sources that needs; this grants no SPL and no MCP.
+    if signals.get("posture_determination"):
+        return _build_classification(
+            intent_family="guided_investigation",
+            primary_intent="investigation_guidance",
+            query_type="investigation_with_guidance",
+            answer_goal=["procedural_steps", "analyst_action_guidance"],
+            confidence=0.55,
+            requires_clarification=False,
+            requires_hil=True,
+            action_mode="recommend_only",
+            reason=(
+                "Stated investigation objective with no registry match; governed, "
+                "review-only guided investigation instead of a clarification dump."
+            ),
+            requested_output_type="INVESTIGATION",
+        )
+
     if signals.get("soc_detection_intent"):
```

## WHY NO SECOND ROUTER IS CREATED

The new branch is one additional `if` inside the existing `classify_intent`,
returning through the same `_build_classification` as every other branch. No new
dispatcher, no new precedence engine, no parallel classification path. Route
selection stays deterministic and single-authority; `adjudicate_route` and the
Resource Planner hub are untouched.

## WHY THE SPL FLOOR IS NOT BROADENED

`posture_determination` is deliberately **not** added to `soc_detection_intent`
or `live_data_request`. Those two remain byte-identical. The new signal is read
in exactly one place. This is the precise defect in the rejected fix and the
reason the new signal exists at all rather than reusing `soc_actionable_hunt`.

## WHY MCP IS NOT IMPLICITLY INVOKED

The branch sets `intent_family="guided_investigation"`,
`action_mode="recommend_only"`, `requires_hil=True`. It sets no capability, no
tool and no execution flag. Downstream, `evidence_planner` decides
`needs_rag/needs_spl/needs_mcp` for the guided family exactly as it does today,
and the MCP execution gate, RBAC and HIL are untouched. Intent classification
never authorises an MCP call, before or after this change.

## INVARIANT IMPACT

| Invariant | Impact |
|---|---|
| Deterministic routing authority | Preserved — a deterministic signal, deterministic branch |
| Deterministic clarification authority | Preserved — clarification stays the terminal default |
| Final RQC (single) | Unchanged |
| SPL validation / normalized_spl | Unchanged; candidate SPL still never executable |
| Exact-call authorization / MCP | Unchanged; no capability granted |
| RBAC / HIL | Unchanged; branch sets `requires_hil=True` |
| EvidenceState truthfulness | Unchanged; no evidence is asserted |
| T1→T2→T3 before T4 | Unchanged |
| No second planner/router/capability DB | Upheld |

## EXPECTED POSITIVE CASES

Measured offline with the exact predicate above:

| # | Query | posture | Expected route |
|---|---|---|---|
| 1 | Determine whether we are exposed to this campaign. | True | guided_investigation |
| 2 | Assess whether these hosts are affected. | True | guided_investigation |
| 3 | Evaluate whether this activity represents compromise. | True | guided_investigation |
| S4 | *(the trace above)* | True | guided_investigation |

## EXPECTED NEGATIVE CASES

| # | Query | posture | Behaviour preserved |
|---|---|---|---|
| 5 | Show failed SSH logins. | False | retrieval (`soc_actionable_hunt` true) |
| 6 | Search Splunk for denied firewall traffic. | False | search (`explicit_search_intent`) |
| 7 | Generate SPL for failed logins. | False | SPL generation |
| 8 | List the top source IPs generating denied traffic. | False | hunt/ranking |
| 9 | What is credential stuffing? | False | knowledge recall |
| 10 | Explain our brute-force SOP. | False | knowledge/SOP |

Plus the explicit negatives §9.4 requires: determine/assess/evaluate alone imply
neither SPL generation nor MCP invocation — `posture_determination` is read only
by the guided branch and grants no capability.

**Known deviation — case 4.** *"Determine whether the current activity is the
same campaign escalated last month."* computes `posture_determination=False`
because it already trips the pre-existing `explicit_search_intent`, so it keeps
its current route (`spl_generation_only`, via `soc_detection_intent`). §9.5
requires only that it not be generic knowledge recall, which holds. Routing it
to guided or to governed clarification instead would mean loosening
`explicit_search_intent`, which is out of scope here and is flagged for the
operator.

## TEST PLAN

New `backend/app/tests/test_posture_determination_routing.py`:

1. The four positive cases classify `intent_family == "guided_investigation"`.
2. The six negative cases keep their current `intent_family` (asserted against
   values captured before the change, so the test proves preservation).
3. `posture_determination` is not a disjunct of `soc_detection_intent` or
   `live_data_request`: for each positive case, both remain false.
4. `posture_determination` alone never yields `spl_generation*` and never sets
   any MCP/tool/capability field.
5. The rejected fix stays rejected: `_DETECTION_VERB_RE` still does not match
   "determine"/"assess"/"evaluate".
6. Answer-shape eval re-run: `scripts/eval_investigation_answer_shape.py`.

## EXPECTED ANSWER-SHAPE EFFECT

Not claimed as a measurement — the patch was not applied, so no post-fix numbers
exist. Current committed baseline stands at **1/10 pass, mean shape 0.4833,
plan stage 1/10**.

The reasoned expectation is that rows whose only defect is the missing objective
verb (`AS.S4`, `AS.P2`, and plausibly `AS.S3`/`AS.S7`/`AS.P3`) reach the same
route `AS.P1` already reaches today — `AS.P1` scores **1.00 with all three
stages** on exactly this path, which is the evidence that the machinery works.
This must be measured after applying, not asserted.

## ROLLBACK

Revert the two hunks. `posture_determination` is read in exactly one place, so
removing the `intent_classifier.py` branch alone fully disables the behaviour
even if the signal remains defined. No data migration, no state, no config.
