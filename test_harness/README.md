# AI SOC Assistant — Skill → SPL → Result Test Harness

Self-contained scaffold for testing the routing → SPL-generation →
execution pipeline end-to-end. This package is **not** wired into the
live orchestration graph or backend application. Real routing and SPL-generation components drop in later
by passing them into `Runner` in place of the bundled stubs.

```
test_harness/
├── generator/         # CIM Authentication event generator + HEC client
│   ├── generate.py
│   ├── fixtures.yaml  # planted datasets with exact, deterministic counts
│   ├── hec_client.py
│   └── splunk_search.py
├── cases/
│   ├── test_cases.yaml       # query, expected_skill, SPL clause spec
│   └── expected_findings.json
├── harness/
│   ├── interfaces.py  # RoutingClient / SplGenerator / SplunkSearch protocols
│   ├── stubs.py       # keyword routing, canned SPL, in-memory Splunk
│   ├── spl_spec.py    # clause + findings assertions
│   ├── audit.py       # JSONL audit emitter
│   └── runner.py      # per-layer pass/fail runner
├── audit_logs/        # test_runs.jsonl is appended here by default
└── requirements.txt
```

## Environment

| Variable                 | Used by                | Purpose                              |
|--------------------------|------------------------|--------------------------------------|
| `SPLUNK_HEC_URL`         | generator (live)       | HEC base URL (e.g. `https://splunk:8088`) |
| `SPLUNK_HEC_TOKEN`       | generator (live)       | HEC token. Sent only as auth header. |
| `SPLUNK_HEC_VERIFY_TLS`  | generator (live)       | `false` to skip TLS verify (dev only) |
| `SPLUNK_API_URL`         | generator clear / live search | Splunk REST URL (e.g. `https://splunk:8089`) |
| `SPLUNK_API_TOKEN`       | generator clear / live search | Splunk auth token. Header only. |
| `SPLUNK_API_VERIFY_TLS`  | generator clear / live search | `false` to skip TLS verify (dev only) |
| `AI_SOC_TEST_AUDIT_PATH` | runner audit           | Override audit log path (default `test_harness/audit_logs/test_runs.jsonl`) |

Tokens are read from env, used only as HTTP headers, and are never
logged or echoed.

## Install

```bash
pip install -r test_harness/requirements.txt
```

Or run any of the commands below inside an ephemeral container with the
repo bind-mounted:

```bash
docker run --rm -v "$PWD":/repo -w /repo python:3.12-slim bash -c "
  pip install -q -r test_harness/requirements.txt && <command>
"
```

## Running the generator standalone

Print planned counts per dataset (no ingest, no network):

```bash
python -m test_harness.generator.generate --count-only
```

Dump events to stdout as HEC envelopes (offline; no Splunk required):

```bash
python -m test_harness.generator.generate --dry-run > /tmp/events.jsonl
```

Live ingest to Splunk via HEC (requires `SPLUNK_HEC_URL`, `SPLUNK_HEC_TOKEN`):

```bash
python -m test_harness.generator.generate
```

Idempotent re-ingest (deletes prior synthetic events in the test window
before ingesting; requires `can_delete` role and `SPLUNK_API_*`):

```bash
python -m test_harness.generator.generate --clear
```

Only generate a subset of datasets:

```bash
python -m test_harness.generator.generate --dataset brute_force_user --dry-run
```

Override the base timestamp (fixtures are time-stable):

```bash
python -m test_harness.generator.generate --base-timestamp 2026-05-22T10:00:00Z --dry-run
```

### Validating the generator independently of the harness

Before running the test loop, confirm planted counts are queryable in
Splunk. Pseudo-code (do this from your own script or notebook):

```python
from test_harness.generator.splunk_search import SplunkSearchClient
from test_harness.harness.runner import precheck_planted_counts

with SplunkSearchClient() as splunk:
    counts = precheck_planted_counts(splunk_search=splunk)
print(counts)
# Expect: baseline=50, brute_force_user=184, brute_force_src=327,
#         success_after_failures=13, top_users_volume=167,
#         account_lockouts=7, new_source_ips=3
```

If `--clear`-then-ingest produced fewer events than these counts, the
generator is broken; fix it before running the harness.

## Running the harness

Run all 6 cases (uses the bundled in-memory Splunk stub — no Splunk
required):

```bash
python -m test_harness.harness.runner
```

Run a single case:

```bash
python -m test_harness.harness.runner --case case_03_success_after_failures
```

Machine-readable output (one JSON object per case, one per line):

```bash
python -m test_harness.harness.runner --json
```

Process exit code is `0` only when **every** case passes all three
layers.

### Reading the per-layer output

Each case prints three independent verdicts plus reasons. Example
failure:

```
[FAIL] case_02_failed_logins_by_source_ip  trace=test-…
  skill   : ok    routed=attack_discovery expected=attack_discovery
  spl_spec: ok 
  findings: FAIL  row_count=1
             - row {'src': '10.1.2.55'} field 'fail_count': expected 327, got 326
```

Reading the verdicts:

| Layer       | What it tests                                  | Failure means              |
|-------------|------------------------------------------------|----------------------------|
| `skill`     | Routing decision matches the expected skill    | Routing layer broke        |
| `spl_spec`  | Generated SPL contains required clauses        | SPL-generation layer broke |
| `findings`  | Executed SPL returns planted exact values      | Execution / fixture broke  |

Independence is the point — when `findings` fails but the other two
pass, the upstream layers are fine and the bug is in SPL execution
against the planted data.

Each case appends one JSON line to `test_harness/audit_logs/test_runs.jsonl`
containing `case_id`, `trace_id`, the three per-layer booleans, the
generated SPL, and any failure reasons. The path can be redirected with
`AI_SOC_TEST_AUDIT_PATH`. If the default repo-local path is not writable in a
restricted shell, the harness falls back to `/tmp/ai_soc_test_runs.jsonl`.

To import JSONL audit records into the application telemetry DB, run the
backend-owned adapter after the harness completes:

```bash
cd backend
python3 -m app.scripts.import_harness_runs --path ../test_harness/audit_logs/test_runs.jsonl
```

## Plugging in real components

`Runner` accepts any objects satisfying the three protocols in
`harness/interfaces.py`:

```python
from test_harness.harness.runner import Runner
from test_harness.generator.splunk_search import SplunkSearchClient

runner = Runner(
    routing=YourRealRoutingClient(),
    spl_generator=YourRealSplGenerator(),
    splunk_factory=lambda active_datasets: SplunkSearchClient(),
)
runner.run_all()
```

When you swap in the real Splunk client, the harness will run SPL
against the live `pgcil_soc` index, so the generator must have already
ingested the relevant datasets for each case (clear + ingest before each
case, or once per run if cases are independent).

## Scope

This scaffold covers the six authentication / access cases only. OT/ICS
data, the asset graph, and cases 7–10 are intentionally out of scope.
