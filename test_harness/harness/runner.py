"""End-to-end runner for the skill → SPL → result harness.

Per case:
  1. (optional) clear the test window in Splunk and re-ingest only the
     datasets the case depends on
  2. route the natural-language query
  3. generate SPL for the routed skill
  4. execute the SPL against Splunk (or the in-memory stub)
  5. assert all three layers independently and append a JSONL audit record

A case is "pass" only when skill, SPL-spec, and findings all pass.
Per-layer pass/fail is reported so a failure tells you which layer broke
(routing vs generation vs execution).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..generator.generate import (
    compute_window,
    iter_dataset_events,
    load_fixtures,
)
from .audit import CaseAuditRecord, emit
from .interfaces import RoutingClient, SKILL_ENUM, SplGenerator, SplunkSearch
from .spl_spec import validate_findings, validate_spl_spec
from .stubs import (
    CannedSplGenerator,
    InMemorySplunkSearch,
    KeywordRoutingStub,
)


_DEFAULT_FIXTURES = Path(__file__).resolve().parent.parent / "generator" / "fixtures.yaml"
_DEFAULT_CASES = Path(__file__).resolve().parent.parent / "cases" / "test_cases.yaml"
_DEFAULT_FINDINGS = Path(__file__).resolve().parent.parent / "cases" / "expected_findings.json"


@dataclass
class CaseResult:
    case_id: str
    trace_id: str
    user_query: str
    skill_pass: bool
    spl_spec_pass: bool
    findings_pass: bool
    routed_skill: str
    expected_skill: str
    spl: str
    expected_findings: dict[str, Any]
    spl_reasons: tuple[str, ...]
    findings_reasons: tuple[str, ...]
    row_count: int

    @property
    def overall_pass(self) -> bool:
        return self.skill_pass and self.spl_spec_pass and self.findings_pass


@dataclass
class Runner:
    routing: RoutingClient
    spl_generator: SplGenerator
    fixtures_path: Path = _DEFAULT_FIXTURES
    cases_path: Path = _DEFAULT_CASES
    findings_path: Path = _DEFAULT_FINDINGS
    splunk_factory: Any = None  # callable(active_datasets: tuple[str, ...]) -> SplunkSearch

    def load(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        with self.cases_path.open("r", encoding="utf-8") as handle:
            cases = yaml.safe_load(handle)["cases"]
        with self.findings_path.open("r", encoding="utf-8") as handle:
            findings = json.load(handle)
        return cases, findings

    def run_case(self, case: dict[str, Any], findings: dict[str, Any]) -> CaseResult:
        case_id = case["id"]
        query = case["query"]
        expected_skill = case["expected_skill"]
        spl_spec = case["expected_spl_spec"]
        active_datasets: tuple[str, ...] = tuple(case.get("fixture_ref", []))
        expected_findings = findings[case_id]

        # If the generator is canned, tell it which case to emit SPL for.
        if isinstance(self.spl_generator, CannedSplGenerator):
            self.spl_generator.set_current_case(case_id)

        decision = self.routing.route(query)
        skill_pass = decision.skill == expected_skill

        spl = self.spl_generator.generate(query, decision.skill)
        spec_result = validate_spl_spec(spl, spl_spec)

        splunk = self._build_splunk(active_datasets)
        rows = splunk.run(spl)
        findings_result = validate_findings(rows, expected_findings)

        return CaseResult(
            case_id=case_id,
            trace_id=decision.trace_id,
            user_query=query,
            skill_pass=skill_pass,
            spl_spec_pass=spec_result.passed,
            findings_pass=findings_result.passed,
            routed_skill=decision.skill,
            expected_skill=expected_skill,
            spl=spl,
            expected_findings=expected_findings,
            spl_reasons=spec_result.reasons,
            findings_reasons=findings_result.reasons,
            row_count=len(rows),
        )

    def _build_splunk(self, active_datasets: tuple[str, ...]) -> SplunkSearch:
        if self.splunk_factory is not None:
            return self.splunk_factory(active_datasets)
        return InMemorySplunkSearch.from_fixtures(
            str(self.fixtures_path), active_datasets
        )

    def run_all(self, only: tuple[str, ...] | None = None) -> list[CaseResult]:
        cases, findings = self.load()
        results: list[CaseResult] = []
        for case in cases:
            if only and case["id"] not in only:
                continue
            result = self.run_case(case, findings)
            _emit_audit(result)
            results.append(result)
        return results


def _emit_audit(result: CaseResult) -> None:
    record = CaseAuditRecord(
        case_id=result.case_id,
        trace_id=result.trace_id,
        user_query=result.user_query,
        skill_pass=result.skill_pass,
        spl_spec_pass=result.spl_spec_pass,
        findings_pass=result.findings_pass,
        overall_pass=result.overall_pass,
        routed_skill=result.routed_skill,
        expected_skill=result.expected_skill,
        spl=result.spl,
        expected_findings=result.expected_findings,
        spl_reasons=tuple(result.spl_reasons),
        findings_reasons=tuple(result.findings_reasons),
        row_count=result.row_count,
    )
    emit(record)


def precheck_planted_counts(
    fixtures_path: Path = _DEFAULT_FIXTURES,
    splunk_search: SplunkSearch | None = None,
) -> dict[str, int]:
    """Independent validator for the generator.

    Confirms each dataset's planted count is queryable in Splunk before
    the harness runs the routing loop. Returns a dict of
    ``{dataset_name: observed_count}``. Caller compares against the
    generator's planned counts.
    """
    fixtures = load_fixtures(fixtures_path)
    earliest, latest = compute_window(fixtures, None)
    defaults = fixtures["defaults"]
    out: dict[str, int] = {}
    for name in fixtures["datasets"].keys():
        spl = (
            f"index={defaults['index']} sourcetype={defaults['sourcetype']} "
            f"source={defaults['source']}"
        )
        if splunk_search is None:
            # Offline path: count from generator.
            count = sum(
                1
                for _ds_name, _env in iter_dataset_events(fixtures, (name,), None)
            )
        else:
            rows = splunk_search.run(spl, earliest_time=earliest, latest_time=latest)
            count = len(rows)
        out[name] = count
    return out


# --- CLI ------------------------------------------------------------------


def _print_results(results: list[CaseResult], pretty: bool) -> None:
    if not pretty:
        for r in results:
            sys.stdout.write(json.dumps(_result_to_dict(r), separators=(",", ":")) + "\n")
        return

    for r in results:
        status_ok = "PASS" if r.overall_pass else "FAIL"
        sys.stdout.write(f"\n[{status_ok}] {r.case_id}  trace={r.trace_id}\n")
        sys.stdout.write(
            f"  skill   : {_layer_tag(r.skill_pass)}  "
            f"routed={r.routed_skill} expected={r.expected_skill}\n"
        )
        sys.stdout.write(f"  spl_spec: {_layer_tag(r.spl_spec_pass)}\n")
        for reason in r.spl_reasons:
            sys.stdout.write(f"             - {reason}\n")
        sys.stdout.write(
            f"  findings: {_layer_tag(r.findings_pass)}  row_count={r.row_count}\n"
        )
        for reason in r.findings_reasons:
            sys.stdout.write(f"             - {reason}\n")

    overall = sum(1 for r in results if r.overall_pass)
    sys.stdout.write(f"\nSummary: {overall}/{len(results)} cases passed\n")


def _layer_tag(passed: bool) -> str:
    return "ok " if passed else "FAIL"


def _result_to_dict(r: CaseResult) -> dict[str, Any]:
    return {
        "case_id": r.case_id,
        "trace_id": r.trace_id,
        "user_query": r.user_query,
        "overall_pass": r.overall_pass,
        "skill_pass": r.skill_pass,
        "spl_spec_pass": r.spl_spec_pass,
        "findings_pass": r.findings_pass,
        "routed_skill": r.routed_skill,
        "expected_skill": r.expected_skill,
        "spl": r.spl,
        "expected_findings": r.expected_findings,
        "spl_reasons": list(r.spl_reasons),
        "findings_reasons": list(r.findings_reasons),
        "row_count": r.row_count,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the skill → SPL → result harness.")
    parser.add_argument(
        "--case",
        action="append",
        default=None,
        help="Only run this case id (repeatable). Default: all cases.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit per-case JSON Lines instead of human-readable output.",
    )
    args = parser.parse_args(argv)

    runner = Runner(routing=KeywordRoutingStub(), spl_generator=CannedSplGenerator())
    only = tuple(args.case) if args.case else None
    results = runner.run_all(only=only)
    _print_results(results, pretty=not args.json)
    return 0 if all(r.overall_pass for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
