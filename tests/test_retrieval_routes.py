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
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _unique(prefix: str) -> str:
    import uuid

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
                    "source_key": "synthetic_clean_corpus",
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
    assert hit["trust_level"] == "trusted_internal"
    assert hit["source_type"] == "synthetic_corpus"
    assert hit["rank"] == 1


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
