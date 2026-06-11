"""Semantic 105-question match tier (WS1 T1.1).

Sits between the token-overlap near match and out_of_registry: paraphrases
that share meaning but not enough verbatim tokens still land on a canonical
registry row. Implementation is deterministic and dependency-free — the
configured embeddings connector is a hash-based mock (random vectors per
exact string), so true vector cosine is not available in this posture.
Instead: SOC synonym/phrase canonicalization followed by character-trigram +
word-token cosine. Handles word reorder, morphology, typos, and curated
synonymy; never invents a row — it only selects an existing registry entry.

Thresholds are module constants calibrated by the paraphrase eval (T1.2);
loosening them requires the eval evidence, not intuition.
"""

from __future__ import annotations

import re
from collections import Counter
from math import sqrt
from typing import Any

from app.coverage.question_runtime_map import list_question_runtime_entries

SEMANTIC_MATCH_THRESHOLD = 0.80
SEMANTIC_MATCH_MARGIN = 0.05

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP_WORDS = {
    "a", "an", "and", "any", "are", "by", "for", "from", "had", "have", "in",
    "is", "of", "or", "show", "the", "to", "what", "which", "who", "me", "us",
    "please", "can", "you", "list", "give",
}

# Curated SOC phrase canonicalization — applied to the normalized text before
# vectorization so synonym variants share surface form. Keep entries tight;
# every addition should be motivated by a paraphrase-eval miss.
_PHRASE_CANON: tuple[tuple[str, str], ...] = (
    ("password guessing", "brute force failed login"),
    ("password spraying", "brute force failed login spray"),
    ("credential stuffing", "brute force failed login"),
    ("logging in", "login"),
    ("logged in", "login"),
    ("log in", "login"),
    ("log on", "login"),
    ("logon", "login"),
    ("sign in", "login"),
    ("signed in", "login"),
    ("signin", "login"),
    ("command and control", "beaconing"),
    ("c2 ", "beaconing "),
    ("data theft", "exfiltration outbound data transfer"),
    ("exfil ", "exfiltration "),
    ("stealing data", "exfiltration outbound data transfer"),
    ("talking to", "contacted"),
    ("communicating with", "communicated with"),
    ("reaching out to", "contacted"),
    ("machines", "hosts"),
    ("endpoints", "hosts"),
    ("devices", "hosts"),
    ("systems", "hosts"),
    ("workstations", "hosts"),
    ("servers", "hosts"),
    ("accounts", "users"),
    ("admins", "administrators"),
    ("priv esc", "privilege escalation"),
    ("powershell scripts", "powershell"),
    ("dns lookups", "dns queries"),
    ("dns requests", "dns queries"),
    ("smb file sharing traffic", "smb traffic"),
)

_INDEX_CACHE: list[tuple[dict[str, Any], Counter[str], float]] | None = None


def clear_semantic_index_cache() -> None:
    global _INDEX_CACHE
    _INDEX_CACHE = None


def semantic_question_match(
    query: str,
    *,
    threshold: float | None = None,
    margin: float | None = None,
) -> dict[str, Any] | None:
    """Return the registry row a paraphrase selects, or None.

    Requires the best score >= threshold AND a clear winner (margin over the
    runner-up); ambiguous paraphrases fall through rather than guess.
    Defaults resolve at call time so the paraphrase eval can calibrate the
    module constants and tests can pin behavior at explicit values.
    """
    if threshold is None:
        threshold = SEMANTIC_MATCH_THRESHOLD
    if margin is None:
        margin = SEMANTIC_MATCH_MARGIN
    query_vector = _vectorize(query)
    if not query_vector:
        return None
    query_norm = _norm(query_vector)
    if query_norm == 0.0:
        return None

    scored: list[tuple[float, dict[str, Any]]] = []
    for entry, vector, vector_norm in _index():
        score = _cosine(query_vector, query_norm, vector, vector_norm)
        scored.append((score, entry))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best_entry = scored[0]
    if best_score < threshold:
        return None
    if len(scored) > 1 and best_score - scored[1][0] < margin:
        return None
    match = dict(best_entry)
    match["_semantic_match_score"] = round(best_score, 4)
    return match


def _index() -> list[tuple[dict[str, Any], Counter[str], float]]:
    global _INDEX_CACHE
    if _INDEX_CACHE is None:
        built: list[tuple[dict[str, Any], Counter[str], float]] = []
        for entry in list_question_runtime_entries():
            question = entry.get("question")
            if not isinstance(question, str):
                continue
            vector = _vectorize(question)
            built.append((entry, vector, _norm(vector)))
        _INDEX_CACHE = built
    return _INDEX_CACHE


def _canonicalize(text: str) -> str:
    lowered = f" {' '.join(text.lower().split())} "
    for phrase, canonical in _PHRASE_CANON:
        lowered = lowered.replace(f" {phrase.strip()} ", f" {canonical.strip()} ")
        if phrase.endswith(" ") and f" {phrase}" in lowered:
            lowered = lowered.replace(f" {phrase}", f" {canonical}")
    return lowered.strip()


def _vectorize(text: str) -> Counter[str]:
    canonical = _canonicalize(text)
    tokens = [
        token
        for token in _TOKEN_RE.findall(canonical)
        if token not in _STOP_WORDS and len(token) > 1
    ]
    vector: Counter[str] = Counter()
    for token in tokens:
        # Word feature weighted above trigrams: shared vocabulary should
        # dominate, trigrams absorb morphology and typos.
        vector[f"w:{token}"] += 3
        padded = f"#{token}#"
        for i in range(len(padded) - 2):
            vector[f"t:{padded[i:i + 3]}"] += 1
    return vector


def _norm(vector: Counter[str]) -> float:
    return sqrt(sum(count * count for count in vector.values()))


def _cosine(
    left: Counter[str],
    left_norm: float,
    right: Counter[str],
    right_norm: float,
) -> float:
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    smaller, larger = (left, right) if len(left) <= len(right) else (right, left)
    dot = sum(count * larger.get(feature, 0) for feature, count in smaller.items())
    return dot / (left_norm * right_norm)
