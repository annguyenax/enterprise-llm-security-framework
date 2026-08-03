"""Schema tests for the Phase 12D v2 benchmark (`datasets/v2/`).

Loads the generated JSONL artifacts directly (no import from `app/`, no
network, no database) and checks the corpus/case/label schemas described
in `docs/benchmark-v2-methodology.md`. Updated for the Code X Phase 12D
audit fixes: `evaluation_scope` on cases, `expected_document_ingestion_status`
moved into labels (corpus no longer carries `expected_ingestion_status`),
and the new authoring-metadata label fields (`template_id`,
`semantic_group_id`, `translation_group_id`, `authoring_set`).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "datasets" / "v2"
CORPUS_FILE = OUT_DIR / "corpus" / "documents.jsonl"
CASES_DIR = OUT_DIR / "cases"
LABELS_DIR = OUT_DIR / "labels"
PROVENANCE_FILE = OUT_DIR / "design" / "authoring-provenance.jsonl"
SPLITS = ("development", "validation", "holdout")
PROVENANCE_REQUIRED_FIELDS = {
    "artifact_id", "artifact_type", "split", "language", "scenario_family",
    "semantic_group_id", "translation_group_id", "authoring_set", "normalized_text_hash",
}

REPOSITORY_DECISION_VALUES = {"allow", "block", "sanitize", "log_only", "human_review"}
EVALUATION_SCOPE_VALUES = {"end_to_end", "component", "availability_fault", "residual_risk_only"}

CASE_ALLOWED_FIELDS = {
    "case_id", "split", "scenario_family", "language", "query", "top_k",
    "relevant_document_ids", "evaluation_scope",
}
LABEL_ONLY_FIELDS = {
    "category", "attack_family", "expected_final_decision", "allowed_final_decisions",
    "expected_stop_reason", "allowed_stop_reasons", "expected_provider_called",
    "expected_retrieval_behavior", "expected_context_behavior", "expected_dlp_action",
    "expected_redaction_categories", "expected_redaction_count", "expected_security_property",
    "rationale", "residual_risk", "is_poisoned", "expected_decision",
    "expected_document_ingestion_status", "template_id", "semantic_group_id",
    "translation_group_id", "authoring_set", "expected_ingestion_status",
}
CORPUS_PROHIBITED_FIELDS = {
    "is_poisoned", "expected_decision", "expected_ingestion_status",
    "expected_final_decision", "expected_document_ingestion_status",
}


def _load_jsonl(path: Path) -> list[dict]:
    assert path.exists(), f"missing benchmark artifact: {path}"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture(scope="module")
def corpus() -> list[dict]:
    return _load_jsonl(CORPUS_FILE)


@pytest.fixture(scope="module")
def cases() -> dict[str, list[dict]]:
    return {split: _load_jsonl(CASES_DIR / f"{split}.jsonl") for split in SPLITS}


@pytest.fixture(scope="module")
def labels() -> dict[str, list[dict]]:
    return {split: _load_jsonl(LABELS_DIR / f"{split}.jsonl") for split in SPLITS}


@pytest.fixture(scope="module")
def provenance() -> list[dict]:
    return _load_jsonl(PROVENANCE_FILE)


def test_corpus_documents_have_required_fields(corpus):
    required = {
        "document_id", "external_id", "source_key", "ingestion_mode",
        "title", "content", "metadata", "language", "scenario_family",
    }
    for doc in corpus:
        assert set(doc.keys()) == required, f"{doc.get('document_id')} field mismatch: {set(doc.keys()) ^ required}"


def test_corpus_contains_no_ground_truth_fields(corpus):
    for doc in corpus:
        leaked = CORPUS_PROHIBITED_FIELDS & doc.keys()
        assert not leaked, f"{doc['document_id']} illegally carries ground-truth field(s): {leaked}"
        dumped = json.dumps(doc)
        assert "is_poisoned" not in dumped
        assert "expected_ingestion_status" not in dumped


def test_corpus_no_longer_carries_expected_ingestion_status(corpus):
    """Code X Phase 12D audit, Major #2: the ingestion OUTCOME is a label,
    not corpus metadata. `ingestion_mode` (execution routing) is retained,
    `expected_ingestion_status` (ground truth) is not."""
    for doc in corpus:
        assert "expected_ingestion_status" not in doc
        assert "ingestion_mode" in doc


def test_corpus_documents_have_non_empty_content_and_title(corpus):
    for doc in corpus:
        assert doc["title"].strip()
        assert doc["content"].strip()


def test_case_files_contain_only_execution_inputs(cases):
    for split in SPLITS:
        for case in cases[split]:
            assert set(case.keys()) == CASE_ALLOWED_FIELDS, (
                f"case {case.get('case_id')} has unexpected keys: "
                f"{set(case.keys()) ^ CASE_ALLOWED_FIELDS}"
            )


def test_case_files_never_contain_label_fields(cases):
    for split in SPLITS:
        for case in cases[split]:
            leaked = LABEL_ONLY_FIELDS & case.keys()
            assert not leaked, f"case {case['case_id']} illegally contains label fields: {leaked}"


def test_case_files_never_contain_expected_decision_or_outcome_text(cases):
    for split in SPLITS:
        raw = (CASES_DIR / f"{split}.jsonl").read_text(encoding="utf-8")
        assert "expected_decision" not in raw
        assert "expected_final_decision" not in raw
        assert "expected_ingestion_status" not in raw
        assert "expected_document_ingestion_status" not in raw
        assert "is_poisoned" not in raw
        assert "template_id" not in raw
        assert "semantic_group_id" not in raw


def test_every_case_has_a_valid_evaluation_scope(cases):
    for split in SPLITS:
        for case in cases[split]:
            assert case["evaluation_scope"] in EVALUATION_SCOPE_VALUES, case["case_id"]


def test_label_files_have_required_fields(labels):
    required = {
        "case_id", "scenario_family", "language", "template_id", "semantic_group_id",
        "translation_group_id", "authoring_set", "expected_document_ingestion_status",
        "category", "attack_family", "expected_final_decision", "allowed_final_decisions",
        "expected_stop_reason", "allowed_stop_reasons", "expected_provider_called",
        "expected_retrieval_behavior", "expected_context_behavior", "expected_dlp_action",
        "expected_redaction_categories", "expected_redaction_count", "expected_security_property",
        "rationale", "residual_risk",
    }
    for split in SPLITS:
        for label in labels[split]:
            assert set(label.keys()) == required, (
                f"{label.get('case_id')} field mismatch: {set(label.keys()) ^ required}"
            )


def test_labels_use_repository_decision_values_exactly(labels):
    for split in SPLITS:
        for label in labels[split]:
            assert label["expected_final_decision"] in REPOSITORY_DECISION_VALUES, label["case_id"]
            for value in label["allowed_final_decisions"]:
                assert value in REPOSITORY_DECISION_VALUES, label["case_id"]


def test_labels_expected_document_ingestion_status_is_valid(labels):
    for split in SPLITS:
        for label in labels[split]:
            assert label["expected_document_ingestion_status"] in {"indexed", "rejected"}, label["case_id"]


def test_labels_authoring_set_matches_split(labels):
    for split in SPLITS:
        for label in labels[split]:
            assert label["authoring_set"] == split, label["case_id"]


def test_labels_template_id_and_translation_group_id_scoped_to_own_split(labels):
    for split in SPLITS:
        for label in labels[split]:
            assert f":{split}:" in label["template_id"], label["case_id"]
            assert f":{split}:" in label["translation_group_id"], label["case_id"]


def test_every_case_has_exactly_one_matching_label(cases, labels):
    for split in SPLITS:
        case_ids = {c["case_id"] for c in cases[split]}
        label_ids = {l["case_id"] for l in labels[split]}
        assert case_ids == label_ids, f"split {split}: case/label ID sets differ"


def test_source_keys_only_use_recognized_values(corpus):
    known = {"api_upload", "synthetic_clean_corpus", "synthetic_external_feed", "v2-unregistered-source-key"}
    for doc in corpus:
        assert doc["source_key"] in known, f"{doc['document_id']} has unrecognized source_key {doc['source_key']!r}"


# ---------------------------------------------------------------------------
# Code X Phase 12D RE-AUDIT, Critical #1.A: non-runtime authoring provenance
# artifact (datasets/v2/design/authoring-provenance.jsonl)
# ---------------------------------------------------------------------------


def test_provenance_entries_have_required_fields(provenance):
    for entry in provenance:
        assert set(entry.keys()) == PROVENANCE_REQUIRED_FIELDS, (
            f"{entry.get('artifact_id')} field mismatch: {set(entry.keys()) ^ PROVENANCE_REQUIRED_FIELDS}"
        )


def test_provenance_artifact_type_is_valid(provenance):
    for entry in provenance:
        assert entry["artifact_type"] in {"query", "document"}, entry["artifact_id"]


def test_provenance_split_and_authoring_set_agree(provenance):
    for entry in provenance:
        assert entry["split"] == entry["authoring_set"], entry["artifact_id"]
        assert entry["split"] in SPLITS, entry["artifact_id"]


def test_provenance_hash_is_64_char_hex(provenance):
    for entry in provenance:
        h = entry["normalized_text_hash"]
        assert isinstance(h, str) and len(h) == 64, entry["artifact_id"]
        int(h, 16)  # raises ValueError if not valid hex


def test_provenance_covers_every_query_and_document(corpus, cases, provenance):
    provenance_ids = {e["artifact_id"] for e in provenance}
    case_ids = {c["case_id"] for split in SPLITS for c in cases[split]}
    doc_ids = {d["document_id"] for d in corpus}
    missing_cases = case_ids - provenance_ids
    missing_docs = doc_ids - provenance_ids
    assert not missing_cases, f"cases missing a provenance entry: {missing_cases}"
    assert not missing_docs, f"documents missing a provenance entry: {missing_docs}"


def test_provenance_has_no_duplicate_artifact_ids(provenance):
    ids = [e["artifact_id"] for e in provenance]
    dupes = {i for i in ids if ids.count(i) > 1}
    assert not dupes, f"duplicate provenance artifact_id(s): {dupes}"


def test_provenance_semantic_and_translation_group_ids_never_cross_splits(provenance):
    owner_by_semantic: dict[str, str] = {}
    owner_by_translation: dict[str, str] = {}
    for entry in provenance:
        split = entry["split"]
        sem = entry["semantic_group_id"]
        trans = entry["translation_group_id"]
        assert owner_by_semantic.setdefault(sem, split) == split, f"semantic_group_id {sem!r} crosses splits"
        assert owner_by_translation.setdefault(trans, split) == split, f"translation_group_id {trans!r} crosses splits"


def test_provenance_is_not_part_of_runtime_case_or_corpus_schema(cases, corpus):
    """Provenance metadata must never appear in the runtime case/corpus
    inputs themselves -- only in the separate, non-runtime provenance
    file."""
    for split in SPLITS:
        for case in cases[split]:
            assert "normalized_text_hash" not in case
            assert "semantic_group_id" not in case
            assert "translation_group_id" not in case
    for doc in corpus:
        assert "normalized_text_hash" not in doc
        assert "semantic_group_id" not in doc
        assert "translation_group_id" not in doc
