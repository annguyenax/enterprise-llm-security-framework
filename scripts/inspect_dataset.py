"""Phase 5 dataset inspection helper, invoked by scripts/inspect_dataset.ps1.

Prints: number of clean docs, number of poisoned docs, number of chunks
generated, and sample doc IDs. Uses only app/services/dataset_loader.py
(standard library only) -- does not require the app's FastAPI/pydantic
dependencies to be installed.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.dataset_loader import load_all_chunks, load_all_documents  # noqa: E402


def main() -> None:
    documents = load_all_documents()
    clean_docs = [d for d in documents if not d.is_poisoned]
    poisoned_docs = [d for d in documents if d.is_poisoned]
    chunks = load_all_chunks()

    print("=== Phase 5 dataset inspection ===")
    print(f"Clean docs:    {len(clean_docs)}")
    print(f"Poisoned docs: {len(poisoned_docs)}")
    print(f"Total chunks:  {len(chunks)}")
    print("")
    print("Sample clean doc IDs:")
    for doc in clean_docs:
        print(f"  - {doc.doc_id}  ({doc.source_path})")
    print("")
    print("Sample poisoned doc IDs:")
    for doc in poisoned_docs:
        print(f"  - {doc.doc_id}  ({doc.source_path})")


if __name__ == "__main__":
    main()
