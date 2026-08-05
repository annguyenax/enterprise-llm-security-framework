"""Tests for the enterprise ACL retriever, the ACL guard, and their wiring.

The properties under test, in order of how badly a regression would hurt:

1. **A principal never retrieves a document they may not read** -- across
   role, department, clearance, and validity-window restrictions.
2. **Filtering happens before `LIMIT`**, so a low-clearance principal is not
   starved of legitimate results by documents they cannot see, and the size
   of the result set is not an oracle for restricted content.
3. **The SQL pre-filter and `evaluate_acl` agree** on every document for
   every principal. They are two independent implementations of one rule;
   the moment they disagree, one of them is wrong.
4. **The legacy path is unchanged** -- the Phase 12B backend, whose corpus
   carries no ACL facts, still behaves exactly as before.
"""
import importlib.util
import json
from pathlib import Path

import pytest

from app.core.decisions import Decision
from app.core.source_policy import (
    PUBLIC_SOURCE_POLICIES,
    UnknownSourceKeyError,
    resolve_source_policy,
)
from app.guards import acl_guard
from app.retrieval.acl import (
    ACL_METADATA_PREFIX,
    ROLE_CLEARANCE,
    AclFacts,
    RetrievalPrincipal,
    acl_facts_from_metadata,
    acl_metadata,
    evaluate_acl,
    principal_from_actor,
)
from app.retrieval.enterprise_acl_bm25 import (
    RETRIEVER_NAME,
    AclFactsUnavailableError,
    EnterpriseAclBm25Config,
    EnterpriseAclBm25Retriever,
    MissingPrincipalError,
)
from app.retrieval.models import RetrievalHit, RetrievalQuery
from app.retrieval.registry import available_retrievers, get_retriever

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS = REPO_ROOT / "datasets" / "enterprise-kb" / "corpus" / "documents.jsonl"

NOW = "2026-08-05T00:00:00+00:00"


def _load_script(name: str):
    path = REPO_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ingester = _load_script("ingest_enterprise_kb")


def _rows() -> list[dict]:
    return [
        json.loads(line)
        for line in CORPUS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.fixture
def kb(tmp_path: Path) -> EnterpriseAclBm25Retriever:
    """A retriever loaded with the full committed corpus."""
    db_path = str(tmp_path / "ekb.db")
    ingester.ingest(db_path)
    return EnterpriseAclBm25Retriever(EnterpriseAclBm25Config(db_path=db_path))


MEMBER_IT = RetrievalPrincipal(
    user_id=3, role="member", department="it", max_sensitivity_rank=ROLE_CLEARANCE["member"]
)
MEMBER_HR = RetrievalPrincipal(
    user_id=6, role="member", department="hr", max_sensitivity_rank=ROLE_CLEARANCE["member"]
)
LEADER_IT = RetrievalPrincipal(
    user_id=2, role="leader", department="it", max_sensitivity_rank=ROLE_CLEARANCE["leader"]
)
LEADER_HR = RetrievalPrincipal(
    user_id=5, role="leader", department="hr", max_sensitivity_rank=ROLE_CLEARANCE["leader"]
)
SUPERADMIN = RetrievalPrincipal(
    user_id=1,
    role="superadmin",
    department="workspace",
    max_sensitivity_rank=ROLE_CLEARANCE["superadmin"],
)

ALL_PRINCIPALS = (MEMBER_IT, MEMBER_HR, LEADER_IT, LEADER_HR, SUPERADMIN)


def _search(kb, principal, query="tài liệu chính sách nội bộ công ty", top_k=50):
    return kb.search(
        RetrievalQuery(query=query, top_k=top_k, principal=principal, as_of=NOW)
    )


def _visible_document_ids(kb, principal, top_k=50) -> set[str]:
    seen: set[str] = set()
    # Several disjoint queries, so the assertion is about access control
    # rather than about one query's lexical recall.
    for query in (
        "chính sách nghỉ phép lương nhân sự",
        "IT hệ thống mật khẩu sự cố hạ tầng",
        "hợp đồng chi phí thù lao kỷ luật tuyển dụng",
        "an toàn thông tin VPN xác thực",
    ):
        result = kb.search(
            RetrievalQuery(query=query, top_k=top_k, principal=principal, as_of=NOW)
        )
        seen.update(hit.document_id for hit in result.hits)
    return seen


# --- Registration ----------------------------------------------------------


def test_retriever_is_registered_under_its_honest_name():
    assert RETRIEVER_NAME in available_retrievers()
    # Not "hybrid": this backend is BM25 + ACL, with no dense retrieval and
    # no rank fusion. The name should not promise otherwise.
    assert "hybrid" not in RETRIEVER_NAME


def test_registry_constructs_the_backend_by_name(monkeypatch, tmp_path: Path):
    """`Settings` is a frozen dataclass, so the whole singleton is replaced
    rather than mutated -- which is also what proves the factory reads
    configuration at construction time, not at import time."""
    from dataclasses import replace

    from app.core import config as config_module

    monkeypatch.setattr(
        config_module,
        "settings",
        replace(config_module.settings, enterprise_kb_db_path=str(tmp_path / "x.db")),
    )
    retriever = get_retriever(RETRIEVER_NAME)
    assert isinstance(retriever, EnterpriseAclBm25Retriever)


def test_unknown_retriever_name_fails_closed():
    with pytest.raises(ValueError):
        get_retriever("definitely_not_registered")


# --- Source policy ---------------------------------------------------------


def test_enterprise_kb_policy_is_internal_only():
    """The public ingestion route must not be able to buy elevated trust by
    naming a source_key -- the Phase 12B Codex Major #1 defect."""
    assert "enterprise_kb" not in PUBLIC_SOURCE_POLICIES
    with pytest.raises(UnknownSourceKeyError):
        resolve_source_policy("enterprise_kb")

    policy = resolve_source_policy("enterprise_kb", allow_internal=True)
    assert policy.trust_level == "trusted_internal"
    # Sensitivity must not have leaked into the provenance axis: the
    # provenance guard's classification allow-list is exactly {"internal"}.
    assert policy.classification == "internal"


def test_ingested_documents_pass_the_provenance_allow_lists(kb):
    from app.guards.provenance_guard import (
        ALLOWED_CLASSIFICATIONS,
        ALLOWED_SOURCE_TYPES,
        ALLOWED_TRUST_LEVELS,
    )

    for row in _rows():
        document = kb.get_document(row["document_id"])
        assert document is not None
        assert document.trust_level in ALLOWED_TRUST_LEVELS
        assert document.classification in ALLOWED_CLASSIFICATIONS
        assert document.source_type in ALLOWED_SOURCE_TYPES


# --- Access control: the core property -------------------------------------


def test_no_principal_ever_retrieves_a_document_they_may_not_read(kb):
    """The exhaustive check: for every principal, every returned document
    must independently pass `evaluate_acl`."""
    for principal in ALL_PRINCIPALS:
        for document_id in _visible_document_ids(kb, principal):
            row = next(r for r in _rows() if r["document_id"] == document_id)
            facts = AclFacts(
                sensitivity_rank=_rank(row["sensitivity"]),
                access_roles=frozenset(row["access_roles"]),
                access_departments=frozenset(row["access_departments"]),
                valid_from=row["valid_from"],
                valid_to=row["valid_to"],
            )
            decision = evaluate_acl(facts, principal, as_of=NOW)
            assert decision.accepted, (
                f"{principal.role}/{principal.department} retrieved {document_id} "
                f"but evaluate_acl says {decision.reason_code}"
            )


def test_sql_prefilter_and_evaluate_acl_agree_on_the_whole_corpus(kb):
    """Two independent implementations of one rule. If they ever diverge,
    the pre-filter (which nothing else double-checks) is the dangerous one."""
    for principal in ALL_PRINCIPALS:
        retrieved = _visible_document_ids(kb, principal)
        expected = {
            row["document_id"]
            for row in _rows()
            if evaluate_acl(
                AclFacts(
                    sensitivity_rank=_rank(row["sensitivity"]),
                    access_roles=frozenset(row["access_roles"]),
                    access_departments=frozenset(row["access_departments"]),
                    valid_from=row["valid_from"],
                    valid_to=row["valid_to"],
                ),
                principal,
                as_of=NOW,
            ).accepted
        }
        assert retrieved == expected, f"divergence for {principal.role}/{principal.department}"


def _rank(sensitivity: str) -> int:
    from app.retrieval.acl import SENSITIVITY_RANK

    return SENSITIVITY_RANK[sensitivity]


def test_member_cannot_reach_confidential_documents(kb):
    visible = _visible_document_ids(kb, MEMBER_HR)
    assert "ekb-doc-0003" not in visible  # confidential salary bands
    assert "ekb-doc-0005" not in visible  # restricted board compensation


def test_department_isolation_between_peers(kb):
    """An IT member must not see an IT-only document's HR counterpart, and
    vice versa."""
    it_visible = _visible_document_ids(kb, MEMBER_IT)
    hr_visible = _visible_document_ids(kb, MEMBER_HR)
    assert "ekb-doc-0006" in it_visible       # IT-only onboarding checklist
    assert "ekb-doc-0006" not in hr_visible


def test_leader_sees_own_department_confidential_but_not_the_other(kb):
    hr_visible = _visible_document_ids(kb, LEADER_HR)
    it_visible = _visible_document_ids(kb, LEADER_IT)
    assert "ekb-doc-0003" in hr_visible       # HR salary bands
    assert "ekb-doc-0003" not in it_visible
    assert "ekb-doc-0004" in it_visible       # IT postmortem
    assert "ekb-doc-0004" not in hr_visible


def test_restricted_documents_are_superadmin_only(kb):
    admin_visible = _visible_document_ids(kb, SUPERADMIN)
    assert "ekb-doc-0005" in admin_visible
    for principal in (MEMBER_IT, MEMBER_HR, LEADER_IT, LEADER_HR):
        assert "ekb-doc-0005" not in _visible_document_ids(kb, principal)


def test_validity_windows_are_enforced_by_the_prefilter(kb):
    visible = _visible_document_ids(kb, SUPERADMIN)
    assert "ekb-doc-0008" not in visible   # expired 2026-01-01
    assert "ekb-doc-0007" not in visible   # not in force until 2027-01-01
    assert "ekb-doc-0009" in visible       # currently within its window


def test_as_of_moves_the_validity_boundary(kb):
    """The same query at a different instant returns a different set --
    proof that time is an input rather than a hidden clock read."""
    def visible_at(as_of: str) -> set[str]:
        result = kb.search(
            RetrievalQuery(
                query="VPN xác thực hai yếu tố truy cập",
                top_k=50,
                principal=SUPERADMIN,
                as_of=as_of,
            )
        )
        return {hit.document_id for hit in result.hits}

    assert "ekb-doc-0008" in visible_at("2025-06-01T00:00:00+00:00")
    assert "ekb-doc-0008" not in visible_at(NOW)


# --- Pre-filter, not post-filter -------------------------------------------


def test_filtering_happens_before_limit(kb):
    """With top_k=1, a member must still receive their best *readable*
    document -- not an empty result because a restricted document outranked
    it and was discarded afterwards."""
    result = kb.search(
        RetrievalQuery(
            query="lương bậc nhân sự chính sách nghỉ phép",
            top_k=1,
            principal=MEMBER_HR,
            as_of=NOW,
        )
    )
    assert len(result.hits) == 1
    assert result.hits[0].document_id != "ekb-doc-0003"


def test_result_count_is_not_an_oracle_for_restricted_documents(kb):
    """A member's result set is full, not gappy: had filtering run after
    ranking, the count would drop by exactly the number of restricted
    matches, which is itself a disclosure."""
    query = "chính sách nội bộ tài liệu công ty quy trình"
    member = kb.search(
        RetrievalQuery(query=query, top_k=3, principal=MEMBER_IT, as_of=NOW)
    )
    admin = kb.search(
        RetrievalQuery(query=query, top_k=3, principal=SUPERADMIN, as_of=NOW)
    )
    assert len(member.hits) == len(admin.hits) == 3


# --- Fail-closed behaviour --------------------------------------------------


def test_search_without_a_principal_is_refused(kb):
    """No anonymous mode, and no 'public documents only' degradation --
    that would be a silent partial authentication."""
    with pytest.raises(MissingPrincipalError):
        kb.search(RetrievalQuery(query="chính sách", top_k=5))


def test_search_with_an_escalated_principal_is_refused(kb):
    escalated = RetrievalPrincipal(
        user_id=3, role="member", department="it", max_sensitivity_rank=3
    )
    with pytest.raises(MissingPrincipalError):
        kb.search(RetrievalQuery(query="chính sách", top_k=5, principal=escalated, as_of=NOW))


def test_ingesting_a_document_without_acl_facts_is_refused(tmp_path: Path):
    from app.retrieval.models import ChunkRecord, DocumentRecord

    retriever = EnterpriseAclBm25Retriever(
        EnterpriseAclBm25Config(db_path=str(tmp_path / "x.db"))
    )
    retriever.initialize()
    document = DocumentRecord(
        document_id="no-acl",
        external_id="no-acl",
        source_key="enterprise_kb",
        source_id="p",
        source_type="synthetic_corpus",
        classification="internal",
        trust_level="trusted_internal",
        title="Khong co ACL",
        content_hash="h",
        created_at="t",
        updated_at="t",
        metadata={},
    )
    chunk = ChunkRecord(
        chunk_id="c", document_id="no-acl", chunk_index=0, text="noi dung", content_hash="h"
    )
    with pytest.raises(AclFactsUnavailableError):
        retriever.upsert_documents([(document, [chunk])])
    # And nothing was written.
    assert retriever.get_document("no-acl") is None


def test_malformed_acl_facts_are_refused_at_ingestion(tmp_path: Path):
    from app.retrieval.models import ChunkRecord, DocumentRecord

    retriever = EnterpriseAclBm25Retriever(
        EnterpriseAclBm25Config(db_path=str(tmp_path / "y.db"))
    )
    retriever.initialize()
    document = DocumentRecord(
        document_id="bad-acl",
        external_id="bad-acl",
        source_key="enterprise_kb",
        source_id="p",
        source_type="synthetic_corpus",
        classification="internal",
        trust_level="trusted_internal",
        title="ACL hong",
        content_hash="h",
        created_at="t",
        updated_at="t",
        metadata={"acl_sensitivity_rank": 99, "acl_access_roles": [], "acl_access_departments": []},
    )
    chunk = ChunkRecord(
        chunk_id="c2", document_id="bad-acl", chunk_index=0, text="noi dung", content_hash="h"
    )
    with pytest.raises(AclFactsUnavailableError):
        retriever.upsert_documents([(document, [chunk])])


# --- ACL guard: the four-way applicability rule -----------------------------


def _hit(metadata: dict | None = None) -> RetrievalHit:
    return RetrievalHit(
        chunk_id="c1",
        document_id="d1",
        title="T",
        text="noi dung",
        rank=1,
        retrieval_score=-1.0,
        source_id="s",
        source_type="synthetic_corpus",
        classification="internal",
        trust_level="trusted_internal",
        metadata=metadata or {},
    )


def _facts_metadata(**overrides) -> dict:
    facts = AclFacts(
        sensitivity_rank=overrides.pop("rank", 1),
        access_roles=frozenset(overrides.pop("roles", ("member", "leader", "superadmin"))),
        access_departments=frozenset(overrides.pop("departments", ("it",))),
        valid_from=overrides.pop("valid_from", None),
        valid_to=overrides.pop("valid_to", None),
    )
    return acl_metadata(facts)


def test_guard_allows_when_neither_side_carries_access_control():
    """The legacy path: a corpus with no ACL facts, queried with no
    principal. Access control does not apply; the guard says so rather than
    blocking a pipeline that never claimed to enforce it."""
    decisions = acl_guard.evaluate_access([_hit()], None, as_of=NOW)
    assert decisions[0].accepted
    assert decisions[0].reason_code == acl_guard.REASON_NOT_APPLICABLE


def test_guard_rejects_labelled_document_when_no_principal_is_present():
    decisions = acl_guard.evaluate_access([_hit(_facts_metadata())], None, as_of=NOW)
    assert not decisions[0].accepted
    assert decisions[0].reason_code == acl_guard.REASON_PRINCIPAL_MISSING


def test_guard_rejects_unlabelled_document_when_a_principal_is_present():
    decisions = acl_guard.evaluate_access([_hit()], MEMBER_IT, as_of=NOW)
    assert not decisions[0].accepted
    assert decisions[0].reason_code == acl_guard.REASON_FACTS_MISSING


def test_guard_evaluates_normally_when_both_sides_are_present():
    allowed = acl_guard.evaluate_access([_hit(_facts_metadata())], MEMBER_IT, as_of=NOW)
    assert allowed[0].accepted

    denied = acl_guard.evaluate_access(
        [_hit(_facts_metadata(roles=("superadmin",)))], MEMBER_IT, as_of=NOW
    )
    assert not denied[0].accepted


def test_guard_rejects_partially_present_facts():
    """Half a fact set is malformed, not absent -- it must not fall through
    to the 'not applicable' allowance."""
    decisions = acl_guard.evaluate_access(
        [_hit({"acl_access_roles": ["member"]})], MEMBER_IT, as_of=NOW
    )
    assert not decisions[0].accepted


def test_guard_evaluates_each_hit_independently():
    hits = [
        _hit(_facts_metadata()),
        _hit(_facts_metadata(roles=("superadmin",))),
        _hit(_facts_metadata()),
    ]
    decisions = acl_guard.evaluate_access(hits, MEMBER_IT, as_of=NOW)
    assert [d.accepted for d in decisions] == [True, False, True]


def test_guard_exception_fails_closed(monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("guard failure")

    monkeypatch.setattr(acl_guard, "evaluate_acl", boom)
    decisions = acl_guard.evaluate_access([_hit(_facts_metadata())], MEMBER_IT, as_of=NOW)
    assert not decisions[0].accepted
    assert decisions[0].reason_code == acl_guard.REASON_GUARD_EXCEPTION


# --- Metadata round-trip ----------------------------------------------------


def test_acl_metadata_round_trips_through_a_hit(kb):
    result = _search(kb, SUPERADMIN, query="thù lao ban điều hành")
    assert result.hits
    facts = acl_facts_from_metadata(result.hits[0].metadata)
    assert facts is not None and facts.is_well_formed()


def test_acl_metadata_is_deterministic():
    facts = AclFacts(
        sensitivity_rank=2,
        access_roles=frozenset({"superadmin", "leader"}),
        access_departments=frozenset({"workspace", "hr"}),
    )
    assert acl_metadata(facts) == acl_metadata(facts)
    assert acl_metadata(facts)["acl_access_roles"] == ["leader", "superadmin"]


# --- Pipeline integration ---------------------------------------------------


def _pipeline(kb, principal, query="chính sách nghỉ phép thường niên", **kwargs):
    from app.services.rag_query import run_rag_query

    return run_rag_query(
        query=query, top_k=5, retriever=kb, principal=principal, as_of=NOW, **kwargs
    )


def test_pipeline_serves_an_authorized_principal(kb):
    result = _pipeline(kb, MEMBER_IT)
    assert result.stop_reason == "allowed"
    assert result.accepted_context_count >= 1


class _UnfilteredRetriever:
    """A backend that ignores access control entirely.

    This is the scenario the ACL guard exists for: the real retriever's
    pre-filter is good enough that no query can produce an unauthorized hit,
    so the only way to exercise the guard's stop path is to simulate the
    backend bug (or the future backend) that forgets to filter. If the guard
    were ever removed as "redundant", this test is what would fail.
    """

    def __init__(self, hits):
        self._hits = tuple(hits)

    def initialize(self):  # pragma: no cover - not used by the pipeline
        return None

    def upsert_documents(self, prepared):  # pragma: no cover
        raise NotImplementedError

    def get_document(self, document_id):  # pragma: no cover
        return None

    def delete_document(self, document_id):  # pragma: no cover
        return False

    def search(self, query):
        from app.retrieval.models import RetrievalResult

        return RetrievalResult(
            normalized_query=query.query,
            term_count=1,
            total_hits=len(self._hits),
            hits=self._hits,
        )


def test_pipeline_blocks_when_every_hit_is_unauthorized():
    from app.services.rag_query import STOP_ALL_REJECTED_ACL, run_rag_query

    restricted = _hit(_facts_metadata(rank=3, roles=("superadmin",), departments=("*",)))
    result = run_rag_query(
        query="thù lao ban điều hành",
        top_k=5,
        retriever=_UnfilteredRetriever([restricted]),
        principal=MEMBER_IT,
        as_of=NOW,
    )
    assert result.retrieved_count == 1
    assert result.stop_reason == STOP_ALL_REJECTED_ACL
    assert result.final_decision == Decision.BLOCK
    assert result.provider_called is False


def test_unauthorized_hit_never_reaches_the_provenance_summary():
    """A chunk refused for access reasons must not contribute its
    `trust_level` to the provenance the caller gets back."""
    from app.services.rag_query import run_rag_query

    restricted = _hit(_facts_metadata(roles=("superadmin",)))
    result = run_rag_query(
        query="tài liệu",
        top_k=5,
        retriever=_UnfilteredRetriever([restricted]),
        principal=MEMBER_IT,
        as_of=NOW,
    )
    assert result.provenance == ()


def test_acl_stage_appears_only_when_access_control_applies(kb):
    result = _pipeline(kb, MEMBER_IT)
    assert any(stage.stage == "acl_guard" for stage in result.stage_results)


def test_acl_facts_never_reach_the_provider(kb):
    """Chunk metadata is rendered into the prompt by the Ollama provider.
    A document's role/clearance rules are authorization internals and have
    no business inside an LLM context."""
    from app.services.llm_provider import (
        BaseLLMProvider,
        LLMProviderRequest,
        LLMProviderResponse,
    )

    class SpyProvider(BaseLLMProvider):
        def __init__(self):
            self.requests: list[LLMProviderRequest] = []

        def generate(self, request):
            self.requests.append(request)
            return LLMProviderResponse(
                text="Phan hoi an toan.",
                provider_name="spy",
                model_name="spy-v1",
                is_mock=True,
            )

    provider = SpyProvider()
    result = _pipeline(kb, MEMBER_IT, provider=provider)
    assert result.provider_called
    assert provider.requests
    for chunk in provider.requests[0].context_chunks:
        leaked = [k for k in chunk.metadata if str(k).startswith(ACL_METADATA_PREFIX)]
        assert leaked == [], f"ACL internals leaked into provider context: {leaked}"


def test_pipeline_answer_does_not_disclose_that_results_were_withheld(kb):
    """A blocked-by-ACL answer must be indistinguishable from a genuine
    no-results answer, or the difference becomes an existence oracle."""
    from app.services.rag_query import _ANSWER_ALL_REJECTED_ACL, _ANSWER_NO_HITS

    assert _ANSWER_ALL_REJECTED_ACL == _ANSWER_NO_HITS


def test_principal_from_actor_matches_workspace_roles():
    for role in ("member", "leader", "superadmin"):
        principal = principal_from_actor(
            {"id": 1, "role": role, "department": "IT", "username": "u"}
        )
        assert principal.is_well_formed()
        assert principal.max_sensitivity_rank == ROLE_CLEARANCE[role]
