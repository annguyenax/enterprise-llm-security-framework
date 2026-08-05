"""Access-control guard: a second, independent check on retrieved hits.

The primary control is the retriever's in-SQL pre-filter
(`app/retrieval/enterprise_acl_bm25.py`), which keeps unreadable documents
out of the candidate set entirely. This guard re-evaluates the same rule in
Python over whatever actually came back. That is deliberate duplication: a
bug in one SQL predicate, an index that silently stops being used, or a
future backend that forgets to filter at all would otherwise be invisible.
A test asserts the two implementations agree on the whole corpus.

Where this sits in the pipeline
-------------------------------
Immediately after retrieval and **before** the Provenance Guard. ACL asks
"may this principal see this document at all", which is both the cheapest
question and the one whose answer must never depend on anything else. Only
after it passes does the pipeline ask the provenance question, so a chunk
rejected for access reasons never contributes its `trust_level` to the
provenance summary returned to the caller.

Why this is not part of `GuardProfile`
--------------------------------------
`GuardProfile` (`app/core/pipeline.py`) exists to ablate guard layers for
the Phase 12E study, and its `profile_id` is a hash over exactly six
controls that the evaluation runner, the analyzer, and already-adjudicated
audit records all depend on. Adding a seventh would change every existing
profile identity.

The design reason is the stronger one, though: **authorization is not
ablatable**. Running an experimental configuration with access control
switched off would mean deliberately serving one user another user's data,
which is not a measurement, it is the incident. `GuardProfile`'s own
docstring already places resource bounds and audit safety outside its
contract for the same reason; ACL belongs in that category.

The four-way applicability rule
-------------------------------
A hit carries ACL facts or it does not; a query carries a principal or it
does not. All four combinations are handled explicitly, and three of the
four reject:

===================  ==================  ==========================================
hit has ACL facts    query has principal outcome
===================  ==================  ==========================================
yes                  yes                 evaluate normally
yes                  no                  REJECT -- cannot authorize a restricted doc
no                   yes                 REJECT -- cannot verify an unlabelled doc
no                   no                  not applicable; allow
===================  ==================  ==========================================

The last row is what keeps the Phase 12B backend working unchanged: its
corpus carries no ACL facts and `/v1/rag/query` supplies no principal, so
the guard correctly reports that access control does not apply rather than
blocking a pipeline that never claimed to enforce it. The two mismatch rows
are what stop that same allowance from becoming a bypass the moment either
side starts carrying real data.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.retrieval.acl import (
    REASON_ALLOWED,
    AclDecision,
    RetrievalPrincipal,
    acl_facts_from_metadata,
    evaluate_acl,
)
from app.retrieval.models import RetrievalHit

REASON_NOT_APPLICABLE = "acl_not_applicable"
REASON_PRINCIPAL_MISSING = "acl_principal_missing"
REASON_FACTS_MISSING = "acl_facts_missing"
REASON_GUARD_EXCEPTION = "acl_guard_exception"


@dataclass(frozen=True)
class AclGuardDecision:
    hit: RetrievalHit
    accepted: bool
    reason_code: str


def _evaluate_single(
    hit: RetrievalHit, principal: RetrievalPrincipal | None, as_of: str
) -> AclGuardDecision:
    try:
        facts = acl_facts_from_metadata(hit.metadata)
    except Exception:  # noqa: BLE001 -- deliberate fail-closed safety net
        return AclGuardDecision(hit=hit, accepted=False, reason_code=REASON_GUARD_EXCEPTION)

    has_principal = isinstance(principal, RetrievalPrincipal)

    if facts is None:
        if has_principal:
            # An access-controlled query must not be answered from a
            # document whose access rules are unknown.
            return AclGuardDecision(
                hit=hit, accepted=False, reason_code=REASON_FACTS_MISSING
            )
        return AclGuardDecision(hit=hit, accepted=True, reason_code=REASON_NOT_APPLICABLE)

    if not has_principal:
        return AclGuardDecision(
            hit=hit, accepted=False, reason_code=REASON_PRINCIPAL_MISSING
        )

    try:
        decision: AclDecision = evaluate_acl(facts, principal, as_of=as_of)
    except Exception:  # noqa: BLE001 -- deliberate fail-closed safety net
        return AclGuardDecision(hit=hit, accepted=False, reason_code=REASON_GUARD_EXCEPTION)

    return AclGuardDecision(
        hit=hit,
        accepted=decision.accepted,
        reason_code=decision.reason_code if not decision.accepted else REASON_ALLOWED,
    )


def evaluate_access(
    hits: list[RetrievalHit],
    principal: RetrievalPrincipal | None,
    *,
    as_of: str,
) -> list[AclGuardDecision]:
    """Evaluate every hit independently, preserving input order.

    Each hit's outcome depends only on its own facts and the principal --
    never on other hits in the batch -- so a mixture of accepted and
    rejected hits is handled deterministically, the same property
    `app/guards/provenance_guard.py` guarantees.
    """
    return [_evaluate_single(hit, principal, as_of) for hit in hits]
