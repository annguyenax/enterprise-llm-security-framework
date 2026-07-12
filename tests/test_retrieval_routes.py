"""Tests for POST /v1/documents/ingest and POST /v1/retrieve (Phase 12B),
plus regression checks that /health and /v1/gateway/chat are unchanged.

**Phase 12B re-audit fix (route-test database isolation):** the prior fix
(a cleanup fixture deleting tracked document IDs from the shared
`data/retrieval.db`) only reduced state growth; it still created and used
the repository-local runtime database. This module now replaces
`app.api.routes`'s module-level `_retriever`/`_ingestion_service`
singletons with fresh instances pointed at a `tmp_path_factory`-provided
temporary file for the duration of this test module, then restores the
originals at teardown. This works reliably regardless of import order
(unlike a `RETRIEVAL_DB_PATH` environment variable override, which
`app.core.config.settings` would only observe if this module happened to
be the first to import `app.main` in the pytest session -- `settings` is
built once at first import and cached in `sys.modules` thereafter) because
it swaps the already-constructed singleton objects directly rather than
trying to influence how they were constructed. No other route
(`/v1/gateway/chat` and friends) reads `_retriever`/`_ingestion_service`,
so this has no effect outside this module. Tests still use a unique,
uuid-suffixed `external_id` per document so tests *within* this module
(which now share one fresh temporary database for the whole module) never
collide with each other either.

**Final re-audit fix (Section 5 residual):** the previous version of this
docstring noted that `app/api/routes.py` eagerly calling
`_retriever.initialize()` at import time (Minor #1 fix from the prior
audit resolution) still created an empty, schema-only `data/retrieval.db`
on disk as a side effect of the *first* `app.main` import in a pytest
session, before this module's fixture ever ran. `tests/conftest.py` now
redirects `RETRIEVAL_DB_PATH` to a per-session temporary file before any
test module (in any file, not just this one) is collected/imported, so
that eager initialization -- wherever in the session it first happens --
never touches the repository's `data/retrieval.db` at all. This module's
own singleton-swap fixture below is kept as well (not removed): it still
gives each test *module* its own fresh, isolated database file rather
than sharing the one session-wide temp path `conftest.py` establishes,
which matters because this module's tests share state within themselves
but must not leak into other test modules that also exercise
`_retriever`/`_ingestion_service`.
"""
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api import routes as routes_module
from app.main import app
from app.retrieval.sqlite_bm25 import IngestionBatchError, SqliteBM25Config, SqliteBM25Retriever
from app.services.ingestion import IngestionService

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _isolated_retrieval_singletons(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("retrieval-routes") / "test.db"
    test_retriever = SqliteBM25Retriever(SqliteBM25Config(db_path=str(db_path)))
    test_service = IngestionService(test_retriever)

    original_retriever = routes_module._retriever
    original_service = routes_module._ingestion_service
    routes_module._retriever = test_retriever
    routes_module._ingestion_service = test_service
    try:
        yield
    finally:
        routes_module._retriever = original_retriever
        routes_module._ingestion_service = original_service


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def test_health_endpoint_unchanged():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "llm-security-gateway"
    assert body["phase"] == "phase-6-mock-provider"


def test_gateway_chat_regression_unchanged():
    response = client.post(
        "/v1/gateway/chat",
        json={"prompt": "What is the per-diem limit for meals during business travel?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["input_guard"]["decision"] == "allow"
    assert body["final_decision"] == "allow"
    assert "Mock provider response" in body["response"]
    assert body["rag_guard"] is None


def test_ingest_single_document():
    external_id = _unique("policy")
    response = client.post(
        "/v1/documents/ingest",
        json={
            "documents": [
                {
                    "external_id": external_id,
                    "source_key": "api_upload",
                    "title": "Security Policy",
                    "text": "Employees must use strong passwords.\n\nMFA is required.",
                    "metadata": {},
                }
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["indexed"] == 1
    assert body["rejected"] == 0
    assert body["items"][0]["status"] == "indexed"
    assert body["items"][0]["document_id"] is not None
    assert body["items"][0]["metadata_keys_stripped"] == 0
    assert "request_id" in body


def test_ingest_batch_validation_empty_list_rejected():
    response = client.post("/v1/documents/ingest", json={"documents": []})
    assert response.status_code == 422  # Pydantic min_length=1 on the list


def test_ingest_rejects_spoofed_trust_level_field():
    response = client.post(
        "/v1/documents/ingest",
        json={
            "documents": [
                {
                    "external_id": _unique("spoof"),
                    "source_key": "api_upload",
                    "title": "t",
                    "text": "some text",
                    "trust_level": "trusted_internal",
                }
            ]
        },
    )
    assert response.status_code == 422


def test_ingest_unknown_source_key_reported_as_rejected_item():
    response = client.post(
        "/v1/documents/ingest",
        json={
            "documents": [
                {
                    "external_id": _unique("unk"),
                    "source_key": "not_a_real_source",
                    "title": "t",
                    "text": "some text",
                }
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["rejected"] == 1
    assert body["items"][0]["status"] == "rejected"


def test_retrieve_after_ingest_returns_ranked_hits():
    external_id = _unique("warranty")
    unique_token = external_id.replace("-", "")
    client.post(
        "/v1/documents/ingest",
        json={
            "documents": [
                {
                    "external_id": external_id,
                    "source_key": "api_upload",
                    "title": "Warranty Info",
                    "text": f"The {unique_token} widget ships with a 2-year warranty.",
                }
            ]
        },
    )

    response = client.post("/v1/retrieve", json={"query": unique_token, "top_k": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["total_hits"] == 1
    hit = body["hits"][0]
    assert hit["trust_level"] == "untrusted_external"
    assert hit["source_type"] == "api_upload"
    assert hit["rank"] == 1


def test_public_ingestion_cannot_claim_trusted_synthetic_source():
    """Major #1 (HTTP-level regression): a public caller sending
    source_key="synthetic_clean_corpus" must be rejected as an unknown
    source, not silently granted trust_level="trusted_internal"."""
    response = client.post(
        "/v1/documents/ingest",
        json={
            "documents": [
                {
                    "external_id": _unique("claim-trust"),
                    "source_key": "synthetic_clean_corpus",
                    "title": "Forged Trust Claim",
                    "text": "This upload claims to be from the trusted synthetic corpus.",
                }
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["rejected"] == 1
    assert body["indexed"] == 0
    assert body["items"][0]["status"] == "rejected"
    assert "unknown" in body["items"][0]["reason"].lower()


def test_public_ingestion_strips_prohibited_key_inside_list_of_list(tmp_path):
    """Re-audit fix (HTTP-level regression): the exact list-of-list
    metadata bypass the re-audit demonstrated must be defeated through
    the real public route, not only through the internal helper
    function or the service layer directly.

    Final re-audit fix (Finding F): covers all four reserved keys the
    ingestion pipeline must strip -- `trust_level`, `is_poisoned`,
    `expected_decision`, and `security_decision` -- not just the first
    two; the earlier route-level regression only exercised two of the
    four and left the other two unverified at the HTTP boundary."""
    unique_marker = _unique("list-bypass")
    response = client.post(
        "/v1/documents/ingest",
        json={
            "documents": [
                {
                    "external_id": unique_marker,
                    "source_key": "api_upload",
                    "title": "t",
                    "text": f"some text {unique_marker}",
                    "metadata": {
                        "wrapper": [
                            [
                                {
                                    "trust_level": "trusted_internal",
                                    "is_poisoned": True,
                                    "expected_decision": "allow",
                                    "security_decision": "allow",
                                }
                            ]
                        ]
                    },
                }
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["indexed"] == 1
    assert body["items"][0]["metadata_keys_stripped"] == 4

    retrieve_response = client.post("/v1/retrieve", json={"query": unique_marker, "top_k": 5})
    hit_metadata_text = str(retrieve_response.json()["hits"])
    assert "trusted_internal" not in hit_metadata_text
    assert "is_poisoned" not in hit_metadata_text
    assert "expected_decision" not in hit_metadata_text
    assert "security_decision" not in hit_metadata_text


def test_ingest_rejects_utf8_oversized_metadata_via_route():
    """Final re-audit fix (Regression A, HTTP-level): a real JSON request
    body carrying Vietnamese metadata that is under the old character
    limit but over the real UTF-8 byte limit must be rejected through the
    actual public route, not only through the service layer directly."""
    response = client.post(
        "/v1/documents/ingest",
        json={
            "documents": [
                {
                    "external_id": _unique("vn-bytes-route"),
                    "source_key": "api_upload",
                    "title": "t",
                    "text": "some text",
                    "metadata": {"note": "á" * 1200},
                }
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["rejected"] == 1
    assert body["indexed"] == 0
    assert "too large" in body["items"][0]["reason"]
    assert "bytes" in body["items"][0]["reason"]


def test_ingest_rejects_deeply_nested_metadata_via_route_without_500():
    """Final re-audit fix (Regression D, HTTP-level): deeply nested
    metadata submitted as a real JSON request body must come back as a
    controlled 200-with-rejected-item response, never an unhandled 500.
    Kept moderately deep (well above MAX_METADATA_DEPTH but far below any
    client-side JSON-encoding recursion limit) so this test isolates the
    *server's* handling, not the test client's own request serialization;
    the full ~900-level extreme case is covered at the service level in
    `tests/test_ingestion.py` (`test_service_rejects_900_level_nested_list_
    without_recursion_error`), which calls `ingest_batch` directly with an
    already-constructed Python object, bypassing JSON request encoding."""
    deep_list: object = "leaf"
    for _ in range(50):
        deep_list = [deep_list]

    response = client.post(
        "/v1/documents/ingest",
        json={
            "documents": [
                {
                    "external_id": _unique("deep-route"),
                    "source_key": "api_upload",
                    "title": "t",
                    "text": "some text",
                    "metadata": {"x": deep_list},
                }
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["rejected"] == 1
    assert body["indexed"] == 0
    assert "depth" in body["items"][0]["reason"].lower()


def test_storage_failure_maps_to_safe_generic_error_without_leaking_cause():
    """Minor #2: an unexpected storage failure must map to a fixed,
    generic 500 response -- never echoing the raw underlying exception
    text (which could reveal internal details) back to the caller."""
    with patch.object(
        routes_module._retriever,
        "upsert_documents",
        side_effect=IngestionBatchError("sqlite3.OperationalError: disk I/O error at /secret/internal/path"),
    ):
        response = client.post(
            "/v1/documents/ingest",
            json={
                "documents": [
                    {
                        "external_id": _unique("storage-fail"),
                        "source_key": "api_upload",
                        "title": "t",
                        "text": "some text",
                    }
                ]
            },
        )
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "disk I/O error" not in detail
    assert "/secret/internal/path" not in detail
    assert "request_id" in detail


def test_retrieve_top_k_bounds_rejected():
    response = client.post("/v1/retrieve", json={"query": "anything", "top_k": 0})
    assert response.status_code == 422  # Pydantic ge=1

    response2 = client.post("/v1/retrieve", json={"query": "anything", "top_k": 9999})
    assert response2.status_code in (400, 422)


def test_retrieve_empty_query_after_sanitization_returns_safe_error():
    response = client.post("/v1/retrieve", json={"query": "*** ((( ))) :::", "top_k": 5})
    assert response.status_code == 400
    assert "detail" in response.json()


def test_retrieve_missing_query_field_rejected():
    response = client.post("/v1/retrieve", json={"top_k": 5})
    assert response.status_code == 422
