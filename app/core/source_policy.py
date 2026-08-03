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

**Phase 12B Codex audit fix (Major #1, "Public caller can select a
trusted source policy"):** the original design let any caller of the
public `POST /v1/documents/ingest` endpoint select `source_key=
"synthetic_clean_corpus"` and receive `trust_level="trusted_internal"` --
the trust *tier mapping* was server-defined, but *which tier a given
upload receives* was effectively caller-chosen, which does not satisfy
"server-controlled trust" (`docs/modernization-final-plan.md` required
decision C). Phase 12B has no authentication layer, so there is no
server-side signal (other than "this came through the one public route")
to decide trust from. The fix: elevated-trust policies
(`synthetic_clean_corpus`, `synthetic_external_feed`) are moved to a
separate table that `resolve_source_policy()` only consults when
`allow_internal=True` is passed explicitly -- `IngestionService`
(`app/services/ingestion.py`), the sole caller reachable from the public
route, never passes it, so `PUBLIC_SOURCE_POLICIES` (effectively just
`api_upload`) is the only reachable outcome through the public API today.
`allow_internal=True` exists for tests and for a future authenticated/
internal ingestion channel (not yet implemented) to use deliberately.
"""
from __future__ import annotations

from app.retrieval.models import SourcePolicyDecision

PUBLIC_SOURCE_POLICIES: dict[str, SourcePolicyDecision] = {
    "api_upload": SourcePolicyDecision(
        source_key="api_upload",
        source_type="api_upload",
        classification="internal",
        trust_level="untrusted_external",
        policy_id="policy-v1-api-upload",
    ),
}

# Elevated-trust policies. Deliberately NOT merged into
# PUBLIC_SOURCE_POLICIES and NOT resolvable by the default
# resolve_source_policy() call (the one used by the public ingestion
# path) -- see the module docstring's Phase 12B Codex audit note.
_INTERNAL_ONLY_SOURCE_POLICIES: dict[str, SourcePolicyDecision] = {
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
    reachable in the current resolution mode (strict rejection, the
    default, is in effect), or when it names an internal-only policy but
    `allow_internal` was not passed."""


def known_source_keys(*, include_internal: bool = False) -> tuple[str, ...]:
    keys = dict(PUBLIC_SOURCE_POLICIES)
    if include_internal:
        keys.update(_INTERNAL_ONLY_SOURCE_POLICIES)
    return tuple(sorted(keys))


def resolve_source_policy(
    source_key: str, *, strict: bool = True, allow_internal: bool = False
) -> SourcePolicyDecision:
    """Resolve a caller-supplied source_key to a server-controlled policy.

    By default (`allow_internal=False`), only `PUBLIC_SOURCE_POLICIES` is
    consulted -- this is what `IngestionService` (the only caller reachable
    from the public `POST /v1/documents/ingest` endpoint) always uses, so
    an elevated-trust `source_key` is unreachable through public input.
    Pass `allow_internal=True` only from a context that is not directly
    driven by an unauthenticated caller (tests, internal tooling, or a
    future authenticated ingestion channel).

    Raises `UnknownSourceKeyError` for an unrecognized (or, without
    `allow_internal`, an internal-only) source_key unless `strict=False`
    is explicitly passed.
    """
    policy = PUBLIC_SOURCE_POLICIES.get(source_key)
    if policy is None and allow_internal:
        policy = _INTERNAL_ONLY_SOURCE_POLICIES.get(source_key)
    if policy is not None:
        return policy
    if strict:
        raise UnknownSourceKeyError(f"Unknown source_key: {source_key!r}")
    return UNKNOWN_SOURCE_POLICY
