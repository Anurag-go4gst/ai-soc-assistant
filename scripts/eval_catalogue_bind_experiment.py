"""Catalogue bind experiment (plan 2026-08-19_1130, item 2) — READ-ONLY.

Compares three ways of binding a query to one of the 65 use cases:

  A  current production: substring containment, confidence = 0.62 + 0.05*matches
  B  coverage x IDF specificity, with a floor and a runner-up margin
  C  the repo's own trigram+token cosine (semantic_question_index) ported from
     the 105-question tier to the use-case catalogue, with threshold + margin

Scored on the 96-row routing truth set (labels, not observed routes):
  false_knowledge_bind - label requires SPL, matcher bound a knowledge use case
  missed_procedure     - label forbids SPL, matcher failed to bind knowledge
plus bind agreement against the 105 catalogue questions as a regression check.

Run:  cd backend && PYTHONPATH=../backend:.. python3 ../scripts/eval_catalogue_bind_experiment.py
"""

import json, math
from collections import Counter
from app.use_cases.registry import load_use_case_catalog, _expanded_match_terms
from app.coverage.semantic_question_index import _canonicalize, _vectorize, _cosine, _norm

CAT = load_use_case_catalog()
KNOWLEDGE_SKILLS = {"knowledge_recall"}

rows = json.load(open(__import__("pathlib").Path(__file__).resolve().parents[1] / "docs/evals/routing_truth_set_v1.json"))["rows"]

def surface(u):
    return " ".join([u.display_name or "", *(u.intent_patterns or []), *(u.example_queries or [])])

# ---------- A: current production ----------
def bind_current(q):
    n = " ".join(q.lower().split())
    best = None
    for u in CAT:
        m = [p for p in _expanded_match_terms(u) if p.lower() in n]
        if not m: continue
        c = min(0.95, 0.62 + 0.05*len(m))
        if best is None or c > best[1]: best = (u, c, m)
    return best

# ---------- B: coverage x IDF, with margin ----------
DF = Counter()
for u in CAT:
    for t in {w for p in _expanded_match_terms(u) for w in p.lower().split()}:
        DF[t] += 1
def idf(t): return math.log(1 + len(CAT)/(1+DF.get(t,0)))
def bind_coverage(q, floor=0.18, margin=0.06):
    n = " ".join(q.lower().split()); qlen = max(len(n.split()),1)
    scored=[]
    for u in CAT:
        m=[p for p in _expanded_match_terms(u) if p.lower() in n]
        if not m: continue
        matched_words = sum(len(p.split()) for p in m)
        spec = sum(idf(w) for p in m for w in p.lower().split())/max(matched_words,1)
        score = (matched_words/qlen) * spec        # coverage x specificity
        scored.append((u,score,m))
    if not scored: return None
    scored.sort(key=lambda x:-x[1])
    if scored[0][1] < floor: return None                       # too thin -> escalate
    if len(scored)>1 and scored[0][1]-scored[1][1] < margin: return None  # contested -> escalate
    return scored[0]

# ---------- C: repo's own cosine + threshold + margin (ported to use cases) ----------
IDX=[]
for u in CAT:
    v=_vectorize(_canonicalize(surface(u)))
    IDX.append((u,v,_norm(v)))
def bind_cosine(q, threshold=0.30, margin=0.05):
    qv=_vectorize(_canonicalize(q)); qn=_norm(qv)
    scored=sorted(((u,_cosine(qv,qn,v,nv)) for u,v,nv in IDX), key=lambda x:-x[1])
    if not scored or scored[0][1] < threshold: return None
    if len(scored)>1 and scored[0][1]-scored[1][1] < margin: return None
    return (scored[0][0], scored[0][1], [])

def evaluate(fn, name):
    false_knowledge=missed_proc=ok_proc=ok_abstain=0
    detail=[]
    for r in rows:
        req_spl = "spl" in (r.get("required_capabilities") or [])
        forb_spl = "spl" in (r.get("forbidden_capabilities") or [])
        b = fn(r["query"])
        skill = b[0].primary_skill if b else None
        if req_spl:
            if skill in KNOWLEDGE_SKILLS:
                false_knowledge += 1; detail.append((r["row_id"], b[0].use_case_id))
            else: ok_abstain += 1
        elif forb_spl:
            if skill in KNOWLEDGE_SKILLS: ok_proc += 1
            else: missed_proc += 1; detail.append((r["row_id"], "NO-BIND" if not b else b[0].use_case_id))
    print(f"{name:34} false_knowledge_bind={false_knowledge:3}  missed_procedure={missed_proc:2}  proc_ok={ok_proc:2}  spl_rows_clean={ok_abstain:3}")
    return detail

print(f"rows={len(rows)}  spl_required={sum(1 for r in rows if 'spl' in (r.get('required_capabilities') or []))}"
      f"  spl_forbidden={sum(1 for r in rows if 'spl' in (r.get('forbidden_capabilities') or []))}\n")
dA=evaluate(bind_current,"A. current (substring+additive)")
dB=evaluate(bind_coverage,"B. coverage x IDF + margin")
dC=evaluate(bind_cosine,"C. repo cosine + threshold + margin")
print("\nA false knowledge binds (first 12):", dA[:12])
print("\nB residual:", dB[:8])
print("\nC residual:", dC[:8])

print("\n--- C threshold sweep ---")
for th in (0.10,0.15,0.20,0.25,0.30):
    fk=mp=okp=0
    for r in rows:
        req="spl" in (r.get("required_capabilities") or []); forb="spl" in (r.get("forbidden_capabilities") or [])
        b=bind_cosine(r["query"], threshold=th)
        sk=b[0].primary_skill if b else None
        if req and sk in KNOWLEDGE_SKILLS: fk+=1
        if forb:
            if sk in KNOWLEDGE_SKILLS: okp+=1
            else: mp+=1
    print(f"  threshold={th:.2f}  false_knowledge={fk:2}  missed_procedure={mp}  proc_ok={okp}")

print("\n--- B vs A agreement on the 105 catalogue questions (regression risk) ---")
from app.coverage.question_runtime_map import list_question_runtime_entries
q105=[e.get("question") or e.get("query") for e in list_question_runtime_entries()]
q105=[q for q in q105 if q]
same=diff_bind=a_only=b_only=neither=0
examples=[]
for q in q105:
    a=bind_current(q); b=bind_coverage(q)
    ai=a[0].use_case_id if a else None; bi=b[0].use_case_id if b else None
    if ai==bi: same+=1
    elif ai and bi: diff_bind+=1; examples.append((q[:60],ai,bi))
    elif ai and not bi: a_only+=1; examples.append((q[:60],ai,"NO-BIND"))
    elif bi and not ai: b_only+=1
print(f"  questions={len(q105)} same={same} different_use_case={diff_bind} A-bound-B-escalates={a_only} B-only={b_only}")
for e in examples[:8]: print("   ", e)

print("\n--- B sensitivity sweep (floor x margin): false_knowledge / missed_proc / 105-binds-changed ---")
for floor in (0.10,0.14,0.18,0.22,0.26,0.30):
    line=[]
    for margin in (0.0,0.06,0.12):
        fk=mp=0
        for r in rows:
            req="spl" in (r.get("required_capabilities") or []); forb="spl" in (r.get("forbidden_capabilities") or [])
            b=bind_coverage(r["query"], floor=floor, margin=margin)
            sk=b[0].primary_skill if b else None
            if req and sk in KNOWLEDGE_SKILLS: fk+=1
            if forb and sk not in KNOWLEDGE_SKILLS: mp+=1
        changed=0
        for q in q105:
            a=bind_current(q); b=bind_coverage(q, floor=floor, margin=margin)
            ai=a[0].use_case_id if a else None; bi=b[0].use_case_id if b else None
            if ai!=bi: changed+=1
        line.append(f"m={margin:.2f}: {fk}/{mp}/{changed}")
    print(f"  floor={floor:.2f}  " + "   ".join(line))



# ---------- B' (REJECTED): artifact-aware tie-break ----------
# Hypothesis: when two candidates share a skill and score closely, prefer the
# one that can render an SPL template, so a "more precise" bind never costs the
# artifact. MEASURED AND REJECTED on the only case it was meant to fix:
#
#   auth_mfa_failure_spike   1.33   ['mfa failure','mfa failures']   template=None
#   auth_failed_login_spike  0.63   ['failure','failures']           template=auth_failed_login_spike
#
# A 0.70 gap. B is correctly preferring a specific two-word phrase over a
# generic one — the question IS about MFA failures. Making the tie-break fire
# would need a ~0.7 band, which would swamp genuine distinctions catalogue-wide.
# The defect is not in the matcher: auth_mfa_failure_spike has no template and
# no template declares use_case_id=auth_mfa_failure_spike. Fix the catalogue,
# not the scoring. Kept here so the rejection stays reproducible.
