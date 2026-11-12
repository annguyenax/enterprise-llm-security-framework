"""Invented V2 inventory; never derives cases or labels from production files."""
from __future__ import annotations


def synthetic_benchmark(runner, analyzer, split="development"):
    malicious = [family for group, families in analyzer.ANALYSIS_GROUPS.items()
                 if group != "benign_control" for family in families]
    benign = list(analyzer.ANALYSIS_GROUPS["benign_control"])
    inventory = [(family, "end_to_end", "malicious") for family in malicious + malicious[:3]]
    inventory += [(family, "end_to_end", "benign") for family in benign + benign[:3]]
    inventory += [("provenance_denied_at_ingestion", "component", "neutral"),
                  ("availability_failure_case", "availability_fault", "neutral"),
                  ("availability_failure_case", "availability_fault", "neutral"),
                  ("fragment_beyond_per_chunk_prefix", "residual_risk_only", "neutral")]
    cases, labels = [], {}
    for index, (family, scope, category) in enumerate(inventory):
        case_id = f"invented-{split}-{index:03d}"
        cases.append({"case_id": case_id, "split": split, "scenario_family": family,
                      "evaluation_scope": scope, "query": "Invented policy lookup",
                      "top_k": 21 if scope == "availability_fault" else 1,
                      "relevant_document_ids": ["invented-rejected" if scope == "component" else "invented-doc"]})
        labels[case_id] = {"case_id": case_id, "scenario_family": family, "category": category,
                           "allowed_final_decisions": ["allow"], "allowed_stop_reasons": ["allowed"],
                           "expected_provider_called": True}
    corpus = tuple({"document_id": doc_id, "external_id": doc_id,
                    "source_key": source, "title": "Invented policy", "content": "Invented policy lookup information.",
                    "scenario_family": "invented", "ingestion_mode": mode, "metadata": {}}
                   for doc_id, source, mode in (("invented-doc", "api_upload", "public"),
                                                ("invented-rejected", "invented-unknown-source", "rejected")))
    return runner.LoadedBenchmark(corpus, tuple(cases), labels)
