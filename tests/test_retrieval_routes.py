"""Tests for POST /v1/documents/ingest and POST /v1/retrieve (Phase 12B),
plus regression checks that /health and /v1/gateway/chat are unchanged.

Route tests share one module-level retriever singleton (`app/api/routes.py`
constructs it once at import time, pointed at `settings.retrieval_db_path`,
default `data/retrieval.db`) with every other test module in the same
pytest session -- unlike `tests/test_sqlite_bm25.py` and
`tests/test_ingestion.py`, which construct their own retriever against a
fresh `tmp_path` file for full per-test isolation. Setting the
`RETRIEVAL_DB_PATH` environment variable here would not reliably achieve
isolation either, because `app.core.config.settings` is built once at
first import and cached in `sys.modules` for the rest of the pytest
session, regardless of later environment changes. Every test in this file
therefore uses a unique, uuid-suffixed `external_id`/`source_key` pair so
assertions never depend on the retrieval database being empty -- only on
the specific documents each test itself created.

**Phase 12B Codex audit fix (Minor #4, "Route tests persist state in the
default runtime database"):** an autouse module-scoped fixture below
tracks every document_id created by this module's tests and deletes them
(via a fresh SqliteBM25Retriever pointed at the same configured database
file -- functionally equivalent to the routes.py singleton, since neither
holds any in-memory state beyond its config) at teardown, so repeated test
runs no longer grow `data/retrieval.db` without bound.
"""
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api import routes as routes_module
from app.core.config import settings
from app.main import app
from app.retrieval.sqlite_bm25 import IngestionBatchError, SqliteBM25Config, SqliteBM25Retriever

client = TestClient(app)

_created_document_ids: list[str] = []


@pytest.fixture(scope="module", autouse=True)
def _cleanup_test_documents():
    yield
    if not _created_document_ids:
        return
    cleanup_retriever = SqliteBM25Retriever(SqliteBM25Config(db_path=settings.retrieval_db_path))
    for document_id in _created_document_ids:
        cleanup_retriever.delete_document(document_id)


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _track(body: dict) -> dict:
    """Record every document_id from an ingest response for cleanup."""
    for item in body.get("items", []):
        if item.get("document_id"):
            _created_document_ids.append(item["document_id"])
    return body


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
    body = _track(response.json())
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
    ingest_response = client.post(
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
    _track(ingest_response.json())

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
    body = _track(response.json())
    assert body["rejected"] == 1
    assert body["indexed"] == 0
    assert body["items"][0]["status"] == "rejected"
    assert "unknown" in body["items"][0]["reason"].lower()


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
