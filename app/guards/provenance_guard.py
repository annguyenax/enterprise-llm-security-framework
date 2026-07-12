"""Deterministic Provenance/Trust Guard (Phase 12C).

Decides whether each **retrieved** chunk (`app.retrieval.models.RetrievalHit`)
may enter the LLM context, based only on its server-assigned
`trust_level`/`classification`/`source_type` -- the same fields
`app/core/source_policy.py` assigns at ingestion time and that a caller
can never set directly (see that module's docstring and
`docs/modernization-v2-architecture.md` §4). This guard never reads
request input, so there is nothing for a caller to spoof here even in
principle.

Deliberately simple and explicit -- three fixed allow-lists, fail-closed
on anything not on them. Not a scoring model, per this phase's explicit
"do not implement a complex scoring model" instruction. Do not invent new
trust/classification/source_type labels here: the allow-lists below list
only the values `app/core/source_policy.py` actually produces today
(`trusted_internal`/`untrusted_external` trust levels, `internal`
classification, `api_upload`/`synthetic_corpus` source types) -- adding a
new server-assigned value anywhere in the project requires updating both
`source_policy.py` and these lists together, by design.

**Trust does not prove content safety.** An ACCEPTED chunk (even from
`trusted_internal`) still goes through the full content-based RAG Context
Guard afterward in `app/services/rag_query.py` -- this guard only
controls which chunks are *eligible* to reach that stage, per
`docs/modernization-v2-architecture.md` §4 ("a high-trust chunk is still
subject to full content scanning; trust does not bypass content
checks"). A compromised high-trust source is a documented residual risk,
not something this guard can detect -- see
`docs/modernization-v2-threat-model.md` §3, Tampering row.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.retrieval.models import RetrievalHit

ALLOWED_TRUST_LEVELS = frozenset({"trusted_internal", "untrusted_external"})
ALLOWED_CLASSIFICATIONS = frozenset({"internal"})
ALLOWED_SOURCE_TYPES = frozenset({"api_upload", "synthetic_corpus"})

REASON_ALLOWED = "allowed_source"
REASON_UNKNOWN_TRUST = "unknown_trust_level"
REASON_UNKNOWN_SOURCE_TYPE = "unknown_source_type"
REASON_CLASSIFICATION_RESTRICTED = "classification_restricted"
REASON_GUARD_EXCEPTION = "provenance_guard_exception"


@dataclass(frozen=True)
class ProvenanceDecision:
    hit: RetrievalHit
    accepted: bool
    reason_code: str


def _evaluate_single(hit: RetrievalHit) -> ProvenanceDecision:
    # Checked in this fixed order so the reported reason_code identifies
    # the *first* thing wrong with the hit's provenance, deterministically.
    if hit.trust_level not in ALLOWED_TRUST_LEVELS:
        return ProvenanceDecision(hit=hit, accepted=False, reason_code=REASON_UNKNOWN_TRUST)
    if hit.source_type not in ALLOWED_SOURCE_TYPES:
        return ProvenanceDecision(hit=hit, accepted=False, reason_code=REASON_UNKNOWN_SOURCE_TYPE)
    if hit.classification not in ALLOWED_CLASSIFICATIONS:
        return ProvenanceDecision(
            hit=hit, accepted=False, reason_code=REASON_CLASSIFICATION_RESTRICTED
        )
    return ProvenanceDecision(hit=hit, accepted=True, reason_code=REASON_ALLOWED)


def evaluate_provenance(hits: list[RetrievalHit]) -> list[ProvenanceDecision]:
    """Evaluate every retrieved hit independently and return one
    `ProvenanceDecision` per hit, preserving input order. A mixture of
    accepted and rejected hits is handled deterministically -- each hit's
    outcome depends only on its own fields, never on other hits in the
    batch. Malformed/unrecognized provenance fails closed (rejected), not
    silently accepted."""
    return [_evaluate_single(hit) for hit in hits]
