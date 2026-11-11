# provenance-v1 API (002)

`validate_artifact(artifact, evidence=...)` returns a `ValidationResult` with
`valid` and immutable `errors` (`path`, `message`). It validates emitted NEW
artifacts directly and never repairs them. `normalize_source(source, run_id=...,
evidence=...)` is the separate writer operation: it consumes partial slot
metadata, creates all keys, and replaces unsupported/unbacked claims with null
and a reason. It does not invent a run ID; a result lacking one remains invalid.
It never copies requested onto effective or derives ACL from GuardProfile.
It only fills `llm_verified=false` from mock evidence when that slot is
still UNKNOWN; an evidenced `llm_verified=true` is not overwritten to a
clean false (the NEW-01 contradiction becomes UNKNOWN).

Each slot has exactly `value`, `evidence`, `reason`. A non-null `evidence` is a
non-empty reference string. The caller supplies either a mapping from these
references to `EvidenceSource` or a callback `(reference, run_id) -> EvidenceSource
| None`. References identify concrete log/artifact/fixture locations. The
adapter must resolve the actual source; a reference-shaped string alone is
insufficient. This package performs no file or network discovery. Adapters are
the trust boundary: constructing an attestation does not itself prove execution.

`EvidenceSource(kind="log" | "artifact" | "fixture", claims={slot_path: value},
...)` represents that resolved evidence. Claims retain their own paths and
values. Requested claims cannot support effective claims. Every slot, including `execution_path`, `storage_backend`, `acl_enabled`,
`requested`, and `commit_sha`, needs a nonempty matching `run_id`
(`None == None` is not a match). Effective claims also need
`execution=True`. `llm_verified=True` additionally requires `execution=True` and
`real_llm_response=True` from the verifying source. A mock claim supports
`llm_verified=False`; mock plus verified true is explicitly invalid (NEW-01).
`is_mock=False` alone proves neither effective identity nor response verification.

`make_timing(...)` builds an ms record from caller-supplied marks and checks
structure. `validate_timing(..., reportable=True)` additionally checks successful
dispatch scope and the resolved source. Evidence of `clock_id`, `monotonic=True`
and `same_process=True` resides in the source located through `timing.source_ref`
(NEW-02), not in extra timing fields. The source must also attest the same run,
`execution=True`, `scope="dispatch_to_final_success"` (immediately before
gateway/rag dispatch through final successful result), and `outcome="success"`.
Every non-null timing record requires correct types, a locatable source, matching
artifact run, and non-reversed marks, even if reportability is false or null.

`summarize_latency(artifacts, evidence=...)` only includes valid, explicitly
reportable NEW records. It uses nearest-rank p50/p95 and groups by source, scope,
effective provider/model, execution/storage, ACL, SHA and mock/verification
status. Mock groups retain their `mock` label; missing verification retains an
`UNKNOWN` label. Fixture-backed groups are labelled `in-sample` and are
never labelled `response-verified`. False/null records and historical percentiles publish no new
percentiles. A run-aware evidence callback can resolve multiple records from
the same shared timing source without mixing sources or runs.

`read_artifact(original_bytes, mode="new" | "history", evidence=...)` requires
an explicit mode; `read_history(...)` selects history mode. Both produce an
immutable view with original bytes/hash and recursively read-only parsed data.
Fractional historical numbers retain their original precision using Decimal;
no historical numbers are recomputed. Versionless history cannot become a
valid NEW artifact. For any status other than `valid` (versionless,
unsupported, or invalid), every field is `UNKNOWN` and run IDs are not
promoted. Versionless and unsupported documents do not call the evidence
resolver. Invalid provenance-v1 documents call the resolver only to decide
status, never to interpret fields. Unsupported non-null
versions remain unsupported. Missing fields display `UNKNOWN` with a
reason, including run ID and SHA; no historical IDs are created.

Mock/in-sample integration example for the later A06 implementation:

```python
from app.provenance import EvidenceSource, normalize_source, validate_artifact

ref = "fixture:mock-in-sample-execution"
sources = {ref: EvidenceSource(
    kind="fixture", run_id="mock-in-sample-run", execution=True,
    claims={"is_mock": True},
)}
artifact = normalize_source({
    "is_mock": {"value": True, "evidence": ref, "reason": None},
}, run_id="mock-in-sample-run", evidence=sources)
assert artifact["llm_verified"]["value"] is False
assert validate_artifact(artifact, evidence=sources).valid
```

All P01–P05 fixtures and their test results are mock/in-sample contract checks.
This package adds no provider calls, evaluation runner changes or 003 harness.
