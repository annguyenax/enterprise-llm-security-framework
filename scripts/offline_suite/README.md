# Offline availability suite (item 003)

Mock/in-sample only. Test doubles throughout; no real LLM providers, no
external network services, no holdout. Never a gate PASS.

## Layout

- `preflight.py` — real preflight, OUTSIDE the 11 logic tests. Starts without
  importing pytest (importlib probes). Checks `pytest`, `fastapi`, `httpx`,
  `aiohttp`, the `unshare -r -n` isolation mechanism, and required test
  paths. Any failure blocks the suite with a specific reason and nonzero
  exit; nothing is downloaded.
- `launcher.py` — runs preflight, then pytest on `tests/offline_suite` +
  `tests/provenance_v1` (11 logic IDs), then writes the JSON report.
  Pytest itself is not wrapped in `unshare`. Only the A02 OS-layer probe
  process runs under `unshare -r -n`. The rest of the suite is offline by
  construction (entry guards, in-sample doubles, no external services),
  not because the entire pytest process tree is in a new netns.
- `report.py` — manifest + selected/executed/skip/xfail per ID, logic count
  vs invocation count, branch mapping from `REQUIRED_BRANCHES` (or each
  test function when a file declares none). A `complete` verdict also
  requires `pytest_exit_code == 0`. Setup/collection `<error>` is not an
  executed test body.
- A03–A05 (`tests/offline_suite/_doubles.py`) are harness test doubles,
  not product fail-closed evidence from the live app/gateway/RAG pipeline.
  Timeouts and faults are injected in those doubles only.

## Commands

```bash
.venv/bin/python scripts/offline_suite/preflight.py --repo-root .
.venv/bin/python scripts/offline_suite/launcher.py --repo-root . --report /tmp/suite-report.json
.venv/bin/pytest -q tests/offline_suite tests/provenance_v1 --basetemp=/tmp/shield-003-pytest
```

## Reading the report

- `selected` is always the 11-ID manifest; `executed` counts only IDs whose
  test body actually ran.
- Preflight-blocked run: `executed=[]`, verdict `blocked`, no `executed=11`
  requirement.
- Complete run: verdict `complete` needs all 11 executed, every declared
  required branch covered by a passed invocation, `pytest_exit_code == 0`,
  and zero failures, errors, skips, or xfails (skip/xfail is not a pass).
- Invocation count may exceed 11 (parametrization); logic count stays 11.
- Isolation evidence for A02 uses a parent-hosted listener as a positive
  control, a different `/proc/self/ns/net` inode, and parent receive
  counters. Arbitrary exceptions, TEST-NET timeouts, and UDP
  send-then-timeout are not deny evidence. A probe run without unshare is
  detected as not isolated.
- A01 and A06 also record harness regression branches (launcher blocker,
  complete-requires-exit-0, junit `<error>` handling). Those are harness
  checks, not A06 product health-limit behaviour.
