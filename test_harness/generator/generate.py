"""Deterministic CIM Authentication synthetic event generator.

Reads ``fixtures.yaml`` and either:

  * emits HEC envelopes to stdout (offline mode), or
  * ingests them into Splunk via HEC (live mode), with optional pre-delete
    of prior synthetic events in the same window for idempotent reruns.

Plant counts are exact and time-stable: re-running with the same
``--base-timestamp`` and ``--fixtures`` produces the identical set of
events.

Usage examples are in ``test_harness/README.md``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Iterator

import yaml

from .hec_client import HecClient, HecConfig
from .splunk_search import SplunkApiConfig, SplunkSearchClient


_DEFAULT_FIXTURES = Path(__file__).with_name("fixtures.yaml")


@dataclass(frozen=True)
class GeneratorConfig:
    fixtures_path: Path
    base_timestamp: datetime
    only_datasets: tuple[str, ...] | None
    dry_run: bool
    clear_before_ingest: bool


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Synthetic CIM auth event generator.")
    parser.add_argument(
        "--fixtures", type=Path, default=_DEFAULT_FIXTURES, help="Path to fixtures.yaml."
    )
    parser.add_argument(
        "--base-timestamp",
        type=str,
        default=None,
        help="ISO 8601 base timestamp (UTC). Overrides fixtures default.",
    )
    parser.add_argument(
        "--dataset",
        action="append",
        default=None,
        help="Only generate this dataset (repeatable). Default: all datasets.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Emit HEC envelopes to stdout instead of ingesting via HEC.",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Delete prior synthetic events in the test window before ingesting.",
    )
    parser.add_argument(
        "--count-only",
        action="store_true",
        help="Don't emit or ingest — just print per-dataset planned counts.",
    )
    return parser.parse_args(argv)


def load_fixtures(path: Path | str) -> dict:
    p = path if isinstance(path, Path) else Path(path)
    with p.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _parse_iso_utc(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _epoch(dt: datetime) -> float:
    return dt.timestamp()


def _spread(
    count: int,
    start_offset_minutes: float,
    end_offset_minutes: float,
    base: datetime,
) -> list[datetime]:
    """Evenly distribute ``count`` timestamps across [start, end] inclusive."""
    if count <= 0:
        return []
    start = base + timedelta(minutes=start_offset_minutes)
    end = base + timedelta(minutes=end_offset_minutes)
    if count == 1:
        return [start]
    span = (end - start).total_seconds()
    step = span / (count - 1) if count > 1 else 0
    return [start + timedelta(seconds=i * step) for i in range(count)]


def _resolve_users(block: dict) -> list[str]:
    if "user" in block:
        return [str(block["user"])]
    if "users" in block:
        return [str(u) for u in block["users"]]
    if "user_pool_prefix" in block and "user_pool_size" in block:
        prefix = str(block["user_pool_prefix"])
        n = int(block["user_pool_size"])
        return [f"{prefix}{i:02d}" for i in range(n)]
    return ["unknown_user"]


def _resolve_sources(block: dict) -> list[str]:
    if "src" in block:
        return [str(block["src"])]
    if "src_pool" in block:
        return [str(s) for s in block["src_pool"]]
    return ["0.0.0.0"]


def _events_from_block(
    block: dict,
    defaults: dict,
    base: datetime,
    window_minutes: int,
) -> Iterator[dict]:
    count = int(block["count"])
    action = str(block.get("action", "success"))
    users = _resolve_users(block)
    sources = _resolve_sources(block)
    start_off = float(block.get("start_offset_minutes", 0))
    end_off = float(block.get("end_offset_minutes", window_minutes))
    timestamps = _spread(count, start_off, end_off, base)

    signature = block.get("signature")
    app = block.get("app", defaults.get("app"))
    dest = block.get("dest", defaults.get("dest"))
    host = block.get("host", defaults.get("host"))

    for i, ts in enumerate(timestamps):
        user = users[i % len(users)]
        src = sources[i % len(sources)]
        event = {
            "_time": ts.isoformat().replace("+00:00", "Z"),
            "action": action,
            "user": user,
            "src": src,
            "dest": dest,
            "app": app,
        }
        if signature is not None:
            event["signature"] = str(signature)

        yield {
            "time": _epoch(ts),
            "host": host,
            "source": defaults["source"],
            "sourcetype": defaults["sourcetype"],
            "index": defaults["index"],
            "event": event,
        }


def iter_dataset_events(
    fixtures: dict,
    only_datasets: tuple[str, ...] | None,
    base_timestamp_override: datetime | None,
) -> Iterator[tuple[str, dict]]:
    defaults = fixtures["defaults"]
    base = base_timestamp_override or _parse_iso_utc(fixtures["base_timestamp"])
    window_minutes = int(fixtures["window_minutes"])
    datasets = fixtures["datasets"]
    for name, dataset in datasets.items():
        if only_datasets and name not in only_datasets:
            continue
        for block in dataset["blocks"]:
            for envelope in _events_from_block(block, defaults, base, window_minutes):
                yield name, envelope


def compute_window(fixtures: dict, base_timestamp_override: datetime | None) -> tuple[str, str]:
    base = base_timestamp_override or _parse_iso_utc(fixtures["base_timestamp"])
    window_minutes = int(fixtures["window_minutes"])
    earliest = base
    # Pad latest by 1 minute to comfortably include the last edge timestamp.
    latest = base + timedelta(minutes=window_minutes + 1)
    return _splunk_time(earliest), _splunk_time(latest)


def _splunk_time(dt: datetime) -> str:
    # Splunk REST accepts epoch or ISO; epoch is unambiguous.
    return f"{int(dt.timestamp())}"


def per_dataset_counts(
    fixtures: dict,
    only_datasets: tuple[str, ...] | None,
    base_timestamp_override: datetime | None,
) -> dict[str, int]:
    out: dict[str, int] = {}
    for name, _envelope in iter_dataset_events(fixtures, only_datasets, base_timestamp_override):
        out[name] = out.get(name, 0) + 1
    return out


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    fixtures = load_fixtures(args.fixtures)
    base_override = _parse_iso_utc(args.base_timestamp) if args.base_timestamp else None
    only = tuple(args.dataset) if args.dataset else None

    if args.count_only:
        counts = per_dataset_counts(fixtures, only, base_override)
        for name, count in counts.items():
            print(f"{name}\t{count}")
        print(f"TOTAL\t{sum(counts.values())}")
        return 0

    events: list[dict] = [env for _name, env in iter_dataset_events(fixtures, only, base_override)]

    if args.dry_run:
        for envelope in events:
            sys.stdout.write(json.dumps(envelope, separators=(",", ":")) + "\n")
        sys.stderr.write(f"[dry-run] generated {len(events)} events\n")
        return 0

    if args.clear:
        api_config = SplunkApiConfig.from_env()
        defaults = fixtures["defaults"]
        earliest, latest = compute_window(fixtures, base_override)
        with SplunkSearchClient(api_config) as search:
            search.delete_events(
                index=defaults["index"],
                source=defaults["source"],
                earliest_time=earliest,
                latest_time=latest,
            )
        sys.stderr.write(
            f"[clear] deleted prior synthetic events in window [{earliest}, {latest}]\n"
        )

    hec_config = HecConfig.from_env()
    with HecClient(hec_config) as client:
        sent = client.send_all(events)
    sys.stderr.write(f"[hec] ingested {sent} events\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
