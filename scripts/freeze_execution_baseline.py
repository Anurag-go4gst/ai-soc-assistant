#!/usr/bin/env python3
"""Freeze and verify the pre-change baseline for a multi-commit refactor.

The per-item Verify commands in a plan prove that each change works. They do not
prove that nothing *else* moved: a frozen eval baseline can be silently rewritten
by a script that regenerates it, a governed fixture can drift, and the three
published copies of a doc can fall out of sync. This captures a SHA256 manifest of
the artifacts that must not change during execution, then re-checks it.

    python3 scripts/freeze_execution_baseline.py --capture --out /tmp/exec-baseline.json
    python3 scripts/freeze_execution_baseline.py --check  --in  /tmp/exec-baseline.json

Exit codes: 0 = unchanged, 1 = drift detected, 2 = usage/IO error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Artifacts that a corrective-refactor commit must never modify. Grouped so a
#: drift report says what kind of guarantee broke, not just which file moved.
PROTECTED: dict[str, tuple[str, ...]] = {
    "eval_baselines": (
        "docs/evals/reference_knowledge_baseline.md",
        "docs/evals/regression_baseline.md",
        "docs/evals/paraphrase_baseline.md",
        "docs/evals/intent_out_of_set_probes_baseline.json",
        "docs/evals/out_of_catalog_ot_probe_baseline.json",
        "docs/evals/baseline_pre_final_resolution.json",
        # Plan 4 R1.5. The OFF arm that R3 and R2 are measured against; the
        # evaluator can rewrite it with --freeze, so it is guarded here to make a
        # re-baseline a visible decision rather than a side effect of a run.
        "docs/evals/routing_truth_set_baseline_v1.json",
    ),
    "golden_answers": (
        "backend/app/evals/golden_answers/question_105_golden.jsonl",
    ),
    "governed_registries": (
        "backend/app/use_cases/catalog.json",
        "backend/app/skills/catalog.json",
        "backend/app/spl/templates.json",
    ),
    "published_doc_mirrors": (
        "docs/architecture/details.html",
        "frontend/public/docs/architecture/details.html",
        "frontend/dist/docs/architecture/details.html",
    ),
}

#: Groups whose members must all hash identically to each other, not merely be
#: unchanged — the published doc is deployed from three paths.
MIRROR_GROUPS: tuple[str, ...] = ("published_doc_mirrors",)

#: The manifest is committed rather than written to /tmp. A gate whose baseline evaporates on reboot
#: — and is simply absent on a fresh host — cannot be cited as evidence that anything was protected.
DEFAULT_MANIFEST_PATH = ROOT / "docs" / "evals" / "protected_execution_baseline.json"


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def _collect() -> dict[str, dict[str, str | None]]:
    return {
        group: {rel: _sha256(ROOT / rel) for rel in members}
        for group, members in PROTECTED.items()
    }


def _check_mirrors(manifest: dict[str, dict[str, str | None]]) -> list[str]:
    problems: list[str] = []
    for group in MIRROR_GROUPS:
        digests = {rel: d for rel, d in manifest.get(group, {}).items() if d is not None}
        if len(set(digests.values())) > 1:
            problems.append(
                f"[{group}] copies are not byte-identical: "
                + ", ".join(f"{rel}={d[:12]}" for rel, d in sorted(digests.items()))
            )
    return problems


def capture(out: Path) -> int:
    manifest = _collect()
    missing = [
        rel
        for group in manifest.values()
        for rel, digest in group.items()
        if digest is None
    ]
    payload = {"root": str(ROOT), "protected": manifest}
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    counted = sum(len(g) for g in manifest.values())
    print(f"captured {counted} artifacts -> {out}")
    for problem in _check_mirrors(manifest):
        print(f"  WARN at capture time: {problem}")
    for rel in missing:
        print(f"  WARN missing (recorded as absent): {rel}")
    return 0


def check(src: Path) -> int:
    try:
        payload = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read baseline {src}: {exc}", file=sys.stderr)
        return 2

    before: dict[str, dict[str, str | None]] = payload.get("protected") or {}
    after = _collect()
    drift: list[str] = []

    # A member added to PROTECTED but never re-captured would otherwise be skipped silently, and the
    # gate would report green while guarding less than it declares. That is how
    # docs/evals/routing_truth_set_baseline_v1.json went unguarded from Plan 4 R1.5 to Plan 5.
    for group, members in PROTECTED.items():
        for rel in members:
            if rel not in before.get(group, {}):
                drift.append(
                    f"[{group}] {rel}: declared protected but absent from the manifest — "
                    "re-capture deliberately, do not ignore"
                )

    for group, members in before.items():
        for rel, old in members.items():
            new = after.get(group, {}).get(rel)
            if old == new:
                continue
            if old is None:
                drift.append(f"[{group}] {rel}: was absent, now present")
            elif new is None:
                drift.append(f"[{group}] {rel}: DELETED")
            else:
                drift.append(f"[{group}] {rel}: {old[:12]} -> {new[:12]}")

    drift.extend(_check_mirrors(after))

    if drift:
        print("PROTECTED ARTIFACT DRIFT:")
        for line in drift:
            print(f"  {line}")
        print(
            "\nIf a change here is intentional, say so explicitly and re-capture the "
            "baseline. Never refresh it as a side effect of a verification run."
        )
        return 1

    counted = sum(len(g) for g in before.values())
    print(f"protected artifacts unchanged ({counted} checked)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--capture", action="store_true", help="write a manifest of protected artifacts")
    mode.add_argument("--check", action="store_true", help="compare current artifacts against a manifest")
    ap.add_argument("--out", type=Path, default=DEFAULT_MANIFEST_PATH)
    ap.add_argument("--in", dest="src", type=Path, default=DEFAULT_MANIFEST_PATH)
    args = ap.parse_args()
    if args.capture:
        return capture(args.out)
    return check(args.src)


if __name__ == "__main__":
    raise SystemExit(main())
