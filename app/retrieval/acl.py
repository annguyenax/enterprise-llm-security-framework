"""Access-control facts for the enterprise knowledge base (Slice 1).

This module defines *what may be seen by whom*, and nothing else. It is
deliberately separate from `app/guards/provenance_guard.py`, which answers
the different question *where did this content come from and is that source
approved*. Keeping the two apart is not stylistic:

    `provenance_guard.ALLOWED_CLASSIFICATIONS` is the frozen set
    `{"internal"}`. Routing an enterprise `sensitivity` value such as
    `confidential` through the `classification` field would make every such
    chunk fail the provenance allow-list and stop the whole pipeline at
    `STOP_ALL_REJECTED_PROVENANCE`.

So `sensitivity` is an independent axis, and the trust axis
(`trust_level`/`classification`/`source_type`, assigned by
`app/core/source_policy.py`) is left exactly as the audited phases left it.

Two representations, on purpose
-------------------------------
`EnterpriseDocMetadata` is a Pydantic model used **at the edges only** --
dataset validation and ingestion -- where input is untrusted and rich
validation is worth its cost. It runs once per document, never per query.

`AclFacts` is a frozen dataclass built from already-validated, already-typed
storage columns and is the only thing `evaluate_acl` touches. The hot path
therefore performs no parsing, no Pydantic construction, and no datetime
arithmetic: just integer, set, and fixed-width string comparisons. This
mirrors how the rest of `app/retrieval/` is modelled (see
`app/retrieval/models.py`, which is all frozen dataclasses).

`evaluate_acl` is a *defence-in-depth* check, not the primary control. The
primary control is a pre-filter in the retriever's own SQL, applied before
`LIMIT`, so that documents a principal may not see never occupy a `top_k`
slot -- filtering after ranking would both starve low-clearance users of
legitimate results and leak the existence of restricted documents through
the size of the gap. The retriever lands in Slice 2; this module is what it
and the guard will both build on.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Sensitivity(str, Enum):
    """Enterprise data-sensitivity tiers, lowest to highest."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


# Ordered clearance ranks. Stored as an INTEGER column so the retriever can
# express "at or below this principal's clearance" as an indexable `<=`
# comparison rather than a set membership test.
SENSITIVITY_RANK: dict[str, int] = {
    Sensitivity.PUBLIC.value: 0,
    Sensitivity.INTERNAL.value: 1,
    Sensitivity.CONFIDENTIAL.value: 2,
    Sensitivity.RESTRICTED.value: 3,
}

# Clearance granted by each workspace role (`app/workspace/store.py`'s
# ROLE_RANK domain). Deliberately conservative: a role gets the tier its
# job requires, never the maximum. `restricted` is superadmin-only.
ROLE_CLEARANCE: dict[str, int] = {
    "member": SENSITIVITY_RANK[Sensitivity.INTERNAL.value],
    "leader": SENSITIVITY_RANK[Sensitivity.CONFIDENTIAL.value],
    "superadmin": SENSITIVITY_RANK[Sensitivity.RESTRICTED.value],
}

# Wildcard usable in `access_departments` for organisation-wide documents.
# Matches the workspace's existing `scope="global"` notion. There is no
# wildcard for `access_roles` by design -- a document readable by every role
# must list them, so the intent is visible in the artifact itself.
DEPARTMENT_WILDCARD = "*"

# The single curated ingestion channel for this knowledge base. Trust for
# this key is assigned server-side by `app/core/source_policy.py`; Slice 2
# registers it under the internal-only table (never `PUBLIC_SOURCE_POLICIES`,
# which would let an unauthenticated caller select an elevated trust tier --
# the exact defect the Phase 12B Codex audit fixed as Major #1).
ENTERPRISE_KB_SOURCE_KEY = "enterprise_kb"

# Canonical instant format: UTC, second precision, fixed width. Fixed width
# is what makes lexicographic string comparison a correct substitute for
# datetime comparison in the hot path, so this format is load-bearing, not
# cosmetic.
CANONICAL_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S+00:00"
_CANONICAL_TIMESTAMP_PATTERN = re.compile(
    r"\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00\Z"
)

REASON_ALLOWED = "acl_allowed"
REASON_ROLE_NOT_PERMITTED = "acl_role_not_permitted"
REASON_DEPARTMENT_NOT_PERMITTED = "acl_department_not_permitted"
REASON_SENSITIVITY_EXCEEDS_CLEARANCE = "acl_sensitivity_exceeds_clearance"
REASON_NOT_YET_VALID = "acl_not_yet_valid"
REASON_EXPIRED = "acl_expired"
REASON_MALFORMED_FACTS = "acl_malformed_facts"
REASON_MALFORMED_PRINCIPAL = "acl_malformed_principal"
REASON_MALFORMED_AS_OF = "acl_malformed_as_of"


def canonical_timestamp(value: datetime) -> str:
    """Render an aware `datetime` in `CANONICAL_TIMESTAMP_FORMAT`.

    Sub-second precision is truncated, so validity windows have one-second
    granularity. Naive datetimes are rejected rather than assumed to be UTC:
    silently guessing a timezone on a security-relevant validity boundary is
    exactly the kind of quiet default this project avoids elsewhere.
    """
    if not isinstance(value, datetime):
        raise TypeError("canonical_timestamp requires a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("canonical_timestamp requires a timezone-aware datetime")
    return value.astimezone(timezone.utc).strftime(CANONICAL_TIMESTAMP_FORMAT)


def is_canonical_timestamp(value: Any) -> bool:
    """Type-first shape check: `isinstance` before any pattern match."""
    return isinstance(value, str) and bool(_CANONICAL_TIMESTAMP_PATTERN.match(value))


def _normalize_token(value: str) -> str:
    return value.strip().lower()


# --- Edge model: dataset validation and ingestion --------------------------


class EnterpriseDocMetadata(BaseModel):
    """Operator-declared metadata for one knowledge-base document.

    `extra="forbid"` plus the deliberate *absence* of `trust_level`,
    `classification`, and `source_type` mirrors `IngestionDocument`
    (`app/retrieval/models.py`): there is no field here for a caller to set
    that could influence a trust decision, so there is nothing to strip and
    nothing to spoof. Trust is resolved from `source_key` server-side.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_key: str = Field(min_length=1, max_length=100)
    sensitivity: Sensitivity
    access_roles: frozenset[str] = Field(min_length=1)
    access_departments: frozenset[str] = Field(min_length=1)
    owner_department: str = Field(min_length=1, max_length=40)
    valid_from: datetime | None = None
    valid_to: datetime | None = None

    @field_validator("access_roles", mode="after")
    @classmethod
    def _check_roles(cls, value: frozenset[str]) -> frozenset[str]:
        normalized = frozenset(_normalize_token(role) for role in value if role.strip())
        if not normalized:
            raise ValueError("access_roles must contain at least one non-blank role")
        unknown = normalized - ROLE_CLEARANCE.keys()
        if unknown:
            # Sorted so the message is deterministic across runs.
            raise ValueError(f"unknown role(s): {sorted(unknown)}")
        return normalized

    @field_validator("access_departments", mode="after")
    @classmethod
    def _check_departments(cls, value: frozenset[str]) -> frozenset[str]:
        normalized = frozenset(
            _normalize_token(dept) for dept in value if dept.strip()
        )
        if not normalized:
            raise ValueError("access_departments must contain at least one entry")
        if DEPARTMENT_WILDCARD in normalized and len(normalized) > 1:
            raise ValueError(
                f"access_departments may not mix {DEPARTMENT_WILDCARD!r} with "
                "specific departments"
            )
        return normalized

    @field_validator("owner_department", mode="after")
    @classmethod
    def _normalize_owner(cls, value: str) -> str:
        return _normalize_token(value)

    @field_validator("valid_from", "valid_to", mode="after")
    @classmethod
    def _require_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("validity timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def _check_window_and_ownership(self) -> "EnterpriseDocMetadata":
        if (
            self.valid_from is not None
            and self.valid_to is not None
            and self.valid_from >= self.valid_to
        ):
            raise ValueError("valid_from must be strictly earlier than valid_to")
        if (
            DEPARTMENT_WILDCARD not in self.access_departments
            and self.owner_department not in self.access_departments
        ):
            # A document its own owning department cannot read is almost
            # certainly a data-entry mistake, and a silently unreadable
            # document is hard to notice in operation.
            raise ValueError(
                "owner_department must appear in access_departments "
                f"(or use {DEPARTMENT_WILDCARD!r})"
            )
        return self

    def to_facts(self) -> "AclFacts":
        """Project to the hot-path representation stored alongside the
        document and handed to `evaluate_acl`."""
        return AclFacts(
            sensitivity_rank=SENSITIVITY_RANK[self.sensitivity.value],
            access_roles=self.access_roles,
            access_departments=self.access_departments,
            valid_from=(
                canonical_timestamp(self.valid_from) if self.valid_from else None
            ),
            valid_to=(canonical_timestamp(self.valid_to) if self.valid_to else None),
        )


# --- Hot path: built from typed storage columns, never parsed --------------


@dataclass(frozen=True)
class AclFacts:
    """The access-control columns of one document, as stored.

    Every field is already in its comparison-ready form. `valid_from` and
    `valid_to` are canonical fixed-width UTC strings precisely so that both
    SQL (`d.valid_from <= :as_of`) and Python compare them the same way,
    with no divergence between the pre-filter and this guard.
    """

    sensitivity_rank: int
    access_roles: frozenset[str]
    access_departments: frozenset[str]
    valid_from: str | None = None
    valid_to: str | None = None

    def is_well_formed(self) -> bool:
        if type(self.sensitivity_rank) is not int:
            return False
        if self.sensitivity_rank not in set(SENSITIVITY_RANK.values()):
            return False
        for collection in (self.access_roles, self.access_departments):
            if not isinstance(collection, frozenset) or not collection:
                return False
            if any(not isinstance(item, str) for item in collection):
                return False
        for stamp in (self.valid_from, self.valid_to):
            if stamp is not None and not is_canonical_timestamp(stamp):
                return False
        if (
            self.valid_from is not None
            and self.valid_to is not None
            and self.valid_from >= self.valid_to
        ):
            return False
        return True


@dataclass(frozen=True)
class RetrievalPrincipal:
    """Who is asking. Built server-side from an authenticated session --
    never from a request field, for the same reason `trust_level` is not a
    request field (`app/core/source_policy.py`)."""

    user_id: int
    role: str
    department: str
    max_sensitivity_rank: int

    def is_well_formed(self) -> bool:
        if type(self.user_id) is not int:
            return False
        if not isinstance(self.role, str) or self.role not in ROLE_CLEARANCE:
            return False
        if not isinstance(self.department, str) or not self.department.strip():
            return False
        if type(self.max_sensitivity_rank) is not int:
            return False
        # A principal may never carry more clearance than its role grants.
        return 0 <= self.max_sensitivity_rank <= ROLE_CLEARANCE[self.role]


@dataclass(frozen=True)
class AclDecision:
    accepted: bool
    reason_code: str


_ALLOWED = AclDecision(accepted=True, reason_code=REASON_ALLOWED)


# --- ACL facts travelling on a RetrievalHit's metadata ---------------------
#
# A retriever attaches these so the ACL guard can re-derive the same facts
# without a second database round trip. The shared `acl_` prefix lets
# `app/services/rag_query.py` strip them before chunk metadata reaches a
# provider: authorization internals have no business inside an LLM prompt.
#
# These live here rather than in a backend module so that
# `app/guards/acl_guard.py` depends only on this contract, never on a
# concrete retriever implementation.

ACL_METADATA_PREFIX = "acl_"
ACL_SENSITIVITY_RANK_KEY = "acl_sensitivity_rank"
ACL_ROLES_KEY = "acl_access_roles"
ACL_DEPARTMENTS_KEY = "acl_access_departments"
ACL_VALID_FROM_KEY = "acl_valid_from"
ACL_VALID_TO_KEY = "acl_valid_to"

_ACL_FACT_KEYS = (ACL_SENSITIVITY_RANK_KEY, ACL_ROLES_KEY, ACL_DEPARTMENTS_KEY)
_SET_LIKE = (list, tuple, set, frozenset)


def acl_metadata(facts: "AclFacts") -> dict[str, object]:
    """Render `facts` as JSON-friendly metadata. Collections are sorted so
    two runs produce byte-identical metadata."""
    return {
        ACL_SENSITIVITY_RANK_KEY: facts.sensitivity_rank,
        ACL_ROLES_KEY: sorted(facts.access_roles),
        ACL_DEPARTMENTS_KEY: sorted(facts.access_departments),
        ACL_VALID_FROM_KEY: facts.valid_from,
        ACL_VALID_TO_KEY: facts.valid_to,
    }


def acl_facts_from_metadata(metadata: Any) -> "AclFacts | None":
    """Rebuild `AclFacts` from a hit's metadata mapping.

    Returns `None` only when the metadata carries **no** ACL keys at all --
    a meaningfully different case from facts that are present but broken,
    which the guard must reject rather than ignore. A partially-present fact
    set therefore yields deliberately-invalid facts (rank `-1`, empty
    collections) so `is_well_formed()` fails and the guard's malformed
    branch rejects it.

    Type-first: every value is `isinstance`-checked before it is iterated,
    compared, or used to build a frozenset.
    """
    if not isinstance(metadata, dict):
        try:
            metadata = dict(metadata)
        except (TypeError, ValueError):
            return None

    if not any(key in metadata for key in _ACL_FACT_KEYS):
        return None

    rank = metadata.get(ACL_SENSITIVITY_RANK_KEY)
    if type(rank) is not int:
        rank = -1

    roles = metadata.get(ACL_ROLES_KEY)
    if not isinstance(roles, _SET_LIKE):
        roles = ()

    departments = metadata.get(ACL_DEPARTMENTS_KEY)
    if not isinstance(departments, _SET_LIKE):
        departments = ()

    return AclFacts(
        sensitivity_rank=rank,
        access_roles=frozenset(item for item in roles if isinstance(item, str)),
        access_departments=frozenset(
            item for item in departments if isinstance(item, str)
        ),
        valid_from=metadata.get(ACL_VALID_FROM_KEY),
        valid_to=metadata.get(ACL_VALID_TO_KEY),
    )


def principal_from_actor(actor: Any) -> RetrievalPrincipal:
    """Build a principal from a workspace actor dict (`store.public_user`).

    Raises on anything unrecognised rather than degrading to a low-clearance
    principal: a malformed actor means the caller's identity is not
    established, and answering such a request with "public documents only"
    would be a silent partial authentication.
    """
    if not isinstance(actor, dict):
        raise TypeError("actor must be a mapping")
    role = actor.get("role")
    if not isinstance(role, str) or _normalize_token(role) not in ROLE_CLEARANCE:
        raise ValueError("actor has no recognised role")
    role = _normalize_token(role)
    department = actor.get("department")
    if not isinstance(department, str) or not department.strip():
        raise ValueError("actor has no department")
    user_id = actor.get("id")
    if type(user_id) is not int:
        raise ValueError("actor has no integer id")
    return RetrievalPrincipal(
        user_id=user_id,
        role=role,
        department=_normalize_token(department),
        max_sensitivity_rank=ROLE_CLEARANCE[role],
    )


def evaluate_acl(
    facts: AclFacts, principal: RetrievalPrincipal, *, as_of: str
) -> AclDecision:
    """Decide whether `principal` may read a document with `facts` at
    `as_of`, failing closed on anything malformed.

    Checks run in a fixed order so the reported `reason_code` identifies the
    *first* reason access was refused, deterministically -- the same
    convention `app/guards/provenance_guard.py` follows.

    `as_of` is an explicit canonical timestamp rather than a call to
    `datetime.now()` inside this function. Time is an input, and a guard
    that reads the wall clock cannot be replayed: two runs over the same
    frozen evaluation artifacts would disagree, which is exactly the
    non-determinism this project's freeze discipline exists to prevent.
    """
    if not isinstance(facts, AclFacts) or not facts.is_well_formed():
        return AclDecision(accepted=False, reason_code=REASON_MALFORMED_FACTS)
    if not isinstance(principal, RetrievalPrincipal) or not principal.is_well_formed():
        return AclDecision(accepted=False, reason_code=REASON_MALFORMED_PRINCIPAL)
    if not is_canonical_timestamp(as_of):
        return AclDecision(accepted=False, reason_code=REASON_MALFORMED_AS_OF)

    if principal.role not in facts.access_roles:
        return AclDecision(accepted=False, reason_code=REASON_ROLE_NOT_PERMITTED)

    if (
        DEPARTMENT_WILDCARD not in facts.access_departments
        and principal.department not in facts.access_departments
    ):
        return AclDecision(accepted=False, reason_code=REASON_DEPARTMENT_NOT_PERMITTED)

    if facts.sensitivity_rank > principal.max_sensitivity_rank:
        return AclDecision(
            accepted=False, reason_code=REASON_SENSITIVITY_EXCEEDS_CLEARANCE
        )

    # Half-open window [valid_from, valid_to): a document becomes readable at
    # its start instant and stops being readable at its end instant, so two
    # consecutive windows never both match the same second.
    if facts.valid_from is not None and as_of < facts.valid_from:
        return AclDecision(accepted=False, reason_code=REASON_NOT_YET_VALID)
    if facts.valid_to is not None and as_of >= facts.valid_to:
        return AclDecision(accepted=False, reason_code=REASON_EXPIRED)

    return _ALLOWED
