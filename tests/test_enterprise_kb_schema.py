"""Tests for the enterprise knowledge base schema, ACL model, and validator.

The validator is loaded with `importlib.util.spec_from_file_location` because
`scripts/` is not a Python package -- the same convention the other
script-backed test modules in this directory use.

Two things are being protected here:

1. **The committed corpus stays valid and canonical**, so its manifest hash
   means something and a future freeze is possible.
2. **`evaluate_acl` fails closed on every axis**, including the ones that are
   easy to get subtly wrong: a principal carrying more clearance than its
   role grants, a validity window evaluated at its exact boundary, and
   malformed facts arriving from storage.
"""
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.retrieval.acl import (
    DEPARTMENT_WILDCARD,
    ENTERPRISE_KB_SOURCE_KEY,
    REASON_ALLOWED,
    REASON_DEPARTMENT_NOT_PERMITTED,
    REASON_EXPIRED,
    REASON_MALFORMED_AS_OF,
    REASON_MALFORMED_FACTS,
    REASON_MALFORMED_PRINCIPAL,
    REASON_NOT_YET_VALID,
    REASON_ROLE_NOT_PERMITTED,
    REASON_SENSITIVITY_EXCEEDS_CLEARANCE,
    ROLE_CLEARANCE,
    SENSITIVITY_RANK,
    AclFacts,
    EnterpriseDocMetadata,
    RetrievalPrincipal,
    Sensitivity,
    canonical_timestamp,
    evaluate_acl,
    is_canonical_timestamp,
    principal_from_actor,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
KB_ROOT = REPO_ROOT / "datasets" / "enterprise-kb"
CORPUS = KB_ROOT / "corpus" / "documents.jsonl"

NOW = "2026-08-05T00:00:00+00:00"


def _load_script(name: str):
    path = REPO_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = _load_script("validate_enterprise_kb")
builder = _load_script("build_enterprise_kb")


def _corpus_rows() -> list[dict]:
    return [
        json.loads(line)
        for line in CORPUS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _facts(
    *,
    rank: int = 1,
    roles=("member", "leader", "superadmin"),
    departments=("it",),
    valid_from: str | None = None,
    valid_to: str | None = None,
) -> AclFacts:
    return AclFacts(
        sensitivity_rank=rank,
        access_roles=frozenset(roles),
        access_departments=frozenset(departments),
        valid_from=valid_from,
        valid_to=valid_to,
    )


def _principal(role: str = "member", department: str = "it") -> RetrievalPrincipal:
    return RetrievalPrincipal(
        user_id=3,
        role=role,
        department=department,
        max_sensitivity_rank=ROLE_CLEARANCE[role],
    )


# --- The committed corpus --------------------------------------------------


def test_committed_corpus_passes_the_validator():
    report = validator.validate(KB_ROOT)
    assert report.errors == []


def test_corpus_on_disk_matches_its_builder():
    """`.gitignore` excludes `*.jsonl` on purpose, so the corpus is not a
    tracked file -- it is reproduced from `scripts/build_enterprise_kb.py`
    and verified by hash. That makes builder/disk drift invisible to code
    review, so it has to be visible to the test suite instead."""
    assert builder.check(KB_ROOT) == []


def test_builder_is_deterministic():
    first_corpus, first_manifest = builder.build(KB_ROOT)
    second_corpus, second_manifest = builder.build(KB_ROOT)
    assert first_corpus == second_corpus
    assert first_manifest == second_manifest


def test_builder_never_awards_itself_a_final_freeze():
    """A FINAL freeze in this project is an adjudicated outcome of
    independent audit; no script may declare one for itself."""
    _corpus, manifest_text = builder.build(KB_ROOT)
    assert json.loads(manifest_text)["manifest_status"] == "draft"


def test_corpus_covers_every_sensitivity_tier():
    tiers = {row["sensitivity"] for row in _corpus_rows()}
    assert tiers == set(SENSITIVITY_RANK)


def test_corpus_covers_every_validity_window_shape():
    rows = _corpus_rows()
    assert any(r["valid_from"] is None and r["valid_to"] is None for r in rows)
    assert any(r["valid_from"] is not None and r["valid_to"] is None for r in rows)
    assert any(r["valid_from"] is not None and r["valid_to"] is not None for r in rows)


def test_corpus_carries_no_server_assigned_field():
    for row in _corpus_rows():
        assert validator.FORBIDDEN_ROW_KEYS.isdisjoint(row.keys())
        assert row["source_key"] == ENTERPRISE_KB_SOURCE_KEY


def test_every_corpus_row_projects_to_well_formed_facts():
    for row in _corpus_rows():
        metadata = EnterpriseDocMetadata(
            source_key=row["source_key"],
            sensitivity=row["sensitivity"],
            access_roles=frozenset(row["access_roles"]),
            access_departments=frozenset(row["access_departments"]),
            owner_department=row["owner_department"],
            valid_from=row["valid_from"],
            valid_to=row["valid_to"],
        )
        assert metadata.to_facts().is_well_formed()


def test_expired_and_future_documents_are_actually_unreadable_today():
    """The corpus must genuinely exercise the time axis, not just declare it."""
    by_id = {row["document_id"]: row for row in _corpus_rows()}
    admin = _principal("superadmin", "workspace")

    expired = by_id["ekb-doc-0008"]
    facts = EnterpriseDocMetadata(
        source_key=expired["source_key"],
        sensitivity=expired["sensitivity"],
        access_roles=frozenset(expired["access_roles"]),
        access_departments=frozenset(expired["access_departments"]),
        owner_department=expired["owner_department"],
        valid_from=expired["valid_from"],
        valid_to=expired["valid_to"],
    ).to_facts()
    assert evaluate_acl(facts, admin, as_of=NOW).reason_code == REASON_EXPIRED


# --- Validator behaviour ---------------------------------------------------


def _write_kb(tmp_path: Path, rows: list[dict], *, manifest_overrides: dict | None = None) -> Path:
    import hashlib

    root = tmp_path / "kb"
    (root / "corpus").mkdir(parents=True)
    (root / "manifests").mkdir(parents=True)
    payload = (
        "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + "\n"
    )
    (root / "corpus" / "documents.jsonl").write_text(payload, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["sensitivity"]] = counts.get(row["sensitivity"], 0) + 1
    manifest = {
        "corpus_sha256": digest,
        "document_count": len(rows),
        "files": [
            {
                "path": "corpus/documents.jsonl",
                "sha256": digest,
                "size_bytes": len(payload.encode("utf-8")),
            }
        ],
        "manifest_status": "draft",
        "schema_version": validator.SCHEMA_VERSION,
        "sensitivity_counts": counts,
        "source_key": ENTERPRISE_KB_SOURCE_KEY,
    }
    manifest.update(manifest_overrides or {})
    (root / "manifests" / "enterprise-kb-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return root


def _valid_row(**overrides) -> dict:
    row = {
        "access_departments": ["it"],
        "access_roles": ["leader", "member", "superadmin"],
        "content": "Noi dung tong hop.",
        "document_id": "ekb-doc-9001",
        "external_id": "ekb-doc-9001",
        "language": "vi",
        "owner_department": "it",
        "sensitivity": "internal",
        "source_key": ENTERPRISE_KB_SOURCE_KEY,
        "title": "Tai lieu thu nghiem",
        "valid_from": None,
        "valid_to": None,
    }
    row.update(overrides)
    return row


def test_validator_accepts_a_well_formed_fixture(tmp_path: Path):
    report = validator.validate(_write_kb(tmp_path, [_valid_row()]))
    assert report.errors == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"trust_level": "trusted_internal"},
        {"classification": "internal"},
        {"is_poisoned": False},
        {"source_type": "api_upload"},
    ],
)
def test_validator_rejects_server_assigned_fields(tmp_path: Path, overrides):
    report = validator.validate(_write_kb(tmp_path, [_valid_row(**overrides)]))
    assert any("server gan" in error for error in report.errors)


@pytest.mark.parametrize(
    "overrides",
    [
        {"access_roles": ["superadmin", "leader"]},          # not sorted
        {"access_roles": ["member", "member"]},              # duplicate
        {"access_roles": []},                                 # empty
        {"access_roles": ["auditor"]},                        # unknown role
        {"access_departments": []},                           # empty
        {"access_departments": ["*", "it"]},                  # wildcard mixed
        {"owner_department": "hr"},                           # not in access_departments
        {"sensitivity": "top_secret"},                        # unknown tier
        {"source_key": "api_upload"},                         # wrong channel
        {"external_id": "different"},                         # id mismatch
        {"valid_from": "2027-01-01T00:00:00+00:00", "valid_to": "2026-01-01T00:00:00+00:00"},
        {"valid_from": "05/08/2026"},                         # not ISO-8601
        {"content": ""},                                      # empty content
    ],
)
def test_validator_rejects_malformed_rows(tmp_path: Path, overrides):
    report = validator.validate(_write_kb(tmp_path, [_valid_row(**overrides)]))
    assert report.errors, f"expected a failure for {overrides}"


def test_validator_detects_manifest_hash_drift(tmp_path: Path):
    root = _write_kb(tmp_path, [_valid_row()])
    corpus = root / "corpus" / "documents.jsonl"
    corpus.write_text(
        corpus.read_text(encoding="utf-8").replace("Noi dung", "Noi dung khac"),
        encoding="utf-8",
        newline="\n",
    )
    report = validator.validate(root)
    assert any("sha256" in error or "corpus_sha256" in error for error in report.errors)


def test_validator_detects_non_canonical_lines(tmp_path: Path):
    root = _write_kb(tmp_path, [_valid_row()])
    corpus = root / "corpus" / "documents.jsonl"
    row = json.loads(corpus.read_text(encoding="utf-8").strip())
    # Identical data, non-canonical serialization: keys emitted in reverse
    # order. Byte-level canonicality is what makes the manifest hash a
    # meaningful drift signal rather than an artifact of the writing tool.
    reordered = {key: row[key] for key in reversed(list(row))}
    corpus.write_text(
        json.dumps(reordered, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    assert json.loads(corpus.read_text(encoding="utf-8")) == row
    report = validator.validate(root)
    assert any("canonical" in error for error in report.errors)


def test_validator_reports_relative_paths_only(tmp_path: Path):
    report = validator.validate(_write_kb(tmp_path, [_valid_row(sensitivity="nope")]))
    assert report.errors
    for error in report.errors:
        assert str(tmp_path) not in error
        assert ":\\" not in error


def test_validator_reports_missing_kb_without_raising(tmp_path: Path):
    report = validator.validate(tmp_path / "khong-ton-tai")
    assert report.errors
    assert not report.ok


# --- Timestamps ------------------------------------------------------------


def test_canonical_timestamp_normalizes_to_utc_second_precision():
    from datetime import timedelta

    value = datetime(2026, 8, 5, 7, 30, 15, 987654, tzinfo=timezone(timedelta(hours=7)))
    assert canonical_timestamp(value) == "2026-08-05T00:30:15+00:00"


def test_canonical_timestamp_rejects_naive_datetime():
    with pytest.raises(ValueError):
        canonical_timestamp(datetime(2026, 8, 5))


def test_canonical_timestamps_compare_lexicographically_like_datetimes():
    """Fixed-width UTC rendering is what lets the SQL pre-filter and this
    guard agree; if the two orderings ever diverged they would disagree."""
    moments = [
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 8, 5, 0, 0, 1, tzinfo=timezone.utc),
        datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        datetime(2027, 1, 1, tzinfo=timezone.utc),
    ]
    rendered = [canonical_timestamp(m) for m in moments]
    assert rendered == sorted(rendered)
    assert all(is_canonical_timestamp(value) for value in rendered)


@pytest.mark.parametrize(
    "value",
    ["2026-08-05", "2026-08-05T00:00:00Z", "2026-08-05T00:00:00+07:00", "", None, 20260805],
)
def test_non_canonical_timestamps_are_rejected(value):
    assert not is_canonical_timestamp(value)


# --- evaluate_acl ----------------------------------------------------------


def test_allows_a_principal_meeting_every_condition():
    decision = evaluate_acl(_facts(), _principal(), as_of=NOW)
    assert decision.accepted
    assert decision.reason_code == REASON_ALLOWED


def test_role_is_checked_before_department():
    """Fixed check order makes the reported reason deterministic, matching
    the convention in provenance_guard."""
    facts = _facts(roles=("superadmin",), departments=("hr",))
    decision = evaluate_acl(facts, _principal("member", "it"), as_of=NOW)
    assert decision.reason_code == REASON_ROLE_NOT_PERMITTED


def test_department_restriction_applies():
    facts = _facts(departments=("hr",))
    decision = evaluate_acl(facts, _principal("member", "it"), as_of=NOW)
    assert decision.reason_code == REASON_DEPARTMENT_NOT_PERMITTED


def test_department_wildcard_admits_any_department():
    facts = _facts(departments=(DEPARTMENT_WILDCARD,))
    assert evaluate_acl(facts, _principal("member", "hr"), as_of=NOW).accepted


def test_clearance_ceiling_is_enforced_per_role():
    confidential = _facts(rank=SENSITIVITY_RANK[Sensitivity.CONFIDENTIAL.value])
    assert not evaluate_acl(confidential, _principal("member"), as_of=NOW).accepted
    assert (
        evaluate_acl(confidential, _principal("member"), as_of=NOW).reason_code
        == REASON_SENSITIVITY_EXCEEDS_CLEARANCE
    )
    assert evaluate_acl(confidential, _principal("leader"), as_of=NOW).accepted


def test_restricted_tier_is_superadmin_only():
    restricted = _facts(
        rank=SENSITIVITY_RANK[Sensitivity.RESTRICTED.value],
        departments=(DEPARTMENT_WILDCARD,),
    )
    assert not evaluate_acl(restricted, _principal("leader"), as_of=NOW).accepted
    assert evaluate_acl(
        restricted, _principal("superadmin", "workspace"), as_of=NOW
    ).accepted


def test_validity_window_is_half_open():
    facts = _facts(
        valid_from="2026-08-05T00:00:00+00:00", valid_to="2026-08-06T00:00:00+00:00"
    )
    principal = _principal()
    # Start instant is inside the window.
    assert evaluate_acl(facts, principal, as_of="2026-08-05T00:00:00+00:00").accepted
    # End instant is outside it, so two consecutive windows never overlap.
    assert (
        evaluate_acl(facts, principal, as_of="2026-08-06T00:00:00+00:00").reason_code
        == REASON_EXPIRED
    )
    assert (
        evaluate_acl(facts, principal, as_of="2026-08-04T23:59:59+00:00").reason_code
        == REASON_NOT_YET_VALID
    )


def test_malformed_as_of_fails_closed():
    for bad in ("2026-08-05", "", None, 12345):
        decision = evaluate_acl(_facts(), _principal(), as_of=bad)
        assert not decision.accepted
        assert decision.reason_code == REASON_MALFORMED_AS_OF


@pytest.mark.parametrize(
    "facts",
    [
        AclFacts(sensitivity_rank=99, access_roles=frozenset({"member"}), access_departments=frozenset({"it"})),
        AclFacts(sensitivity_rank=True, access_roles=frozenset({"member"}), access_departments=frozenset({"it"})),
        AclFacts(sensitivity_rank=1, access_roles=frozenset(), access_departments=frozenset({"it"})),
        AclFacts(sensitivity_rank=1, access_roles=frozenset({"member"}), access_departments=frozenset()),
        AclFacts(sensitivity_rank=1, access_roles=frozenset({1}), access_departments=frozenset({"it"})),
        AclFacts(
            sensitivity_rank=1,
            access_roles=frozenset({"member"}),
            access_departments=frozenset({"it"}),
            valid_from="not-a-timestamp",
        ),
        AclFacts(
            sensitivity_rank=1,
            access_roles=frozenset({"member"}),
            access_departments=frozenset({"it"}),
            valid_from="2027-01-01T00:00:00+00:00",
            valid_to="2026-01-01T00:00:00+00:00",
        ),
        "not-facts-at-all",
    ],
)
def test_malformed_facts_fail_closed(facts):
    decision = evaluate_acl(facts, _principal(), as_of=NOW)
    assert not decision.accepted
    assert decision.reason_code == REASON_MALFORMED_FACTS


@pytest.mark.parametrize(
    "principal",
    [
        RetrievalPrincipal(user_id=1, role="auditor", department="it", max_sensitivity_rank=1),
        RetrievalPrincipal(user_id=1, role="member", department="", max_sensitivity_rank=1),
        # Escalation attempt: more clearance than the role grants.
        RetrievalPrincipal(user_id=1, role="member", department="it", max_sensitivity_rank=3),
        RetrievalPrincipal(user_id=True, role="member", department="it", max_sensitivity_rank=1),
        "not-a-principal",
    ],
)
def test_malformed_or_escalated_principal_fails_closed(principal):
    decision = evaluate_acl(_facts(), principal, as_of=NOW)
    assert not decision.accepted
    assert decision.reason_code == REASON_MALFORMED_PRINCIPAL


# --- principal_from_actor --------------------------------------------------


def test_principal_from_actor_assigns_role_clearance():
    principal = principal_from_actor(
        {"id": 3, "username": "it.user1", "role": "member", "department": "IT"}
    )
    assert principal.department == "it"
    assert principal.max_sensitivity_rank == ROLE_CLEARANCE["member"]
    assert principal.is_well_formed()


@pytest.mark.parametrize(
    "actor",
    [
        {"id": 3, "role": "hacker", "department": "it"},
        {"id": 3, "role": "member", "department": ""},
        {"id": "3", "role": "member", "department": "it"},
        {"id": True, "role": "member", "department": "it"},
        {"role": "member", "department": "it"},
        "not-a-dict",
    ],
)
def test_principal_from_actor_refuses_unrecognised_actors(actor):
    """Refusing beats degrading: answering a malformed identity with
    'public documents only' would be a silent partial authentication."""
    with pytest.raises((TypeError, ValueError)):
        principal_from_actor(actor)


# --- EnterpriseDocMetadata edge model --------------------------------------


def test_metadata_forbids_unknown_and_server_assigned_fields():
    with pytest.raises(Exception):
        EnterpriseDocMetadata(
            source_key=ENTERPRISE_KB_SOURCE_KEY,
            sensitivity="internal",
            access_roles=frozenset({"member"}),
            access_departments=frozenset({"it"}),
            owner_department="it",
            trust_level="trusted_internal",
        )


def test_metadata_normalizes_case_and_whitespace():
    metadata = EnterpriseDocMetadata(
        source_key=ENTERPRISE_KB_SOURCE_KEY,
        sensitivity="internal",
        access_roles=frozenset({" Member ", "LEADER"}),
        access_departments=frozenset({" IT "}),
        owner_department=" It ",
    )
    assert metadata.access_roles == frozenset({"member", "leader"})
    assert metadata.access_departments == frozenset({"it"})
    assert metadata.owner_department == "it"


def test_metadata_is_frozen():
    metadata = EnterpriseDocMetadata(
        source_key=ENTERPRISE_KB_SOURCE_KEY,
        sensitivity="internal",
        access_roles=frozenset({"member"}),
        access_departments=frozenset({"it"}),
        owner_department="it",
    )
    with pytest.raises(Exception):
        metadata.sensitivity = Sensitivity.RESTRICTED
