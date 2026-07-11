"""Server-controlled source policy for document ingestion (Phase 12B).

Trust and classification are never accepted from the ingestion caller --
see `docs/modernization-v2-architecture.md` §4 and required decision C in
`docs/modernization-final-plan.md`. This module is the single place that
maps a caller-supplied `source_key` to server-controlled trust/
classification/source_type values. Adding a new source requires a code
change and review here, not a request field, by design.

**Chosen behavior for unknown source keys (documented per the Phase 12B
task's explicit requirement to pick one and document it):** unknown
source keys are REJECTED by default, not silently downgraded to a
low-trust policy. Rationale:

- `docs/modernization-v2-architecture.md` §4 describes this as an
  "allow-listed ingestion source/config" -- an allowlist that silently
  admits anything not on the list at a lower trust tier is not really an
  allowlist, it is a default-permit policy with an extra label.
- A rejected ingestion is safe-by-default and immediately visible to the
  caller/operator (an explicit 4xx-equivalent error), matching the same
  fail-closed posture already adopted for the FTS5 capability check in
  `docs/decisions/ADR-002-retrieval-engine.md` -- this project's general
  pattern for security-relevant capability/policy gaps is "fail clearly",
  not "silently degrade."
- Silently accepting an unrecognized source under an "unknown/low-trust"
  label risks normalizing unreviewed sources being quietly ingested at
  scale, which is harder to notice than an outright rejection.

`UNKNOWN_SOURCE_POLICY` and `resolve_source_policy(..., strict=False)` are
kept available for tests/tooling that explicitly want to exercise the
low-trust fallback path, but this is never the default and is never
reachable from a caller-settable request field.
"""
from __future__ import annotations

from app.retrieval.models import SourcePolicyDecision

_SOURCE_POLICIES: dict[str, SourcePolicyDecision] = {
    "api_upload": SourcePolicyDecision(
        source_key="api_upload",
        source_type="api_upload",
        classification="internal",
        trust_level="untrusted_external",
        policy_id="policy-v1-api-upload",
    ),
    "synthetic_clean_corpus": SourcePolicyDecision(
        source_key="synthetic_clean_corpus",
        source_type="synthetic_corpus",
        classification="internal",
        trust_level="trusted_internal",
        policy_id="policy-v1-synthetic-clean",
    ),
    "synthetic_external_feed": SourcePolicyDecision(
        source_key="synthetic_external_feed",
        source_type="synthetic_corpus",
        classification="internal",
        trust_level="untrusted_external",
        policy_id="policy-v1-synthetic-external",
    ),
}

UNKNOWN_SOURCE_POLICY = SourcePolicyDecision(
    source_key="unknown",
    source_type="unknown",
    classification="unverified",
    trust_level="untrusted_unknown",
    policy_id="policy-v1-unknown-fallback",
)


class UnknownSourceKeyError(ValueError):
    """Raised when a caller-supplied source_key has no configured policy
    and strict rejection (the default) is in effect."""


def known_source_keys() -> tuple[str, ...]:
    return tuple(sorted(_SOURCE_POLICIES))


def resolve_source_policy(source_key: str, *, strict: bool = True) -> SourcePolicyDecision:
    """Resolve a caller-supplied source_key to a server-controlled policy.

    Raises `UnknownSourceKeyError` for an unrecognized source_key unless
    `strict=False` is explicitly passed (see module docstring for why the
    default is strict rejection, and why this parameter is never wired to
    a caller-settable request field).
    """
    policy = _SOURCE_POLICIES.get(source_key)
    if policy is not None:
        return policy
    if strict:
        raise UnknownSourceKeyError(f"Unknown source_key: {source_key!r}")
    return UNKNOWN_SOURCE_POLICY
