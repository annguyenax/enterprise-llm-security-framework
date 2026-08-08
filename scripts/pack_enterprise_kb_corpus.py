import json
import os
from pathlib import Path

def main():
    repo_root = Path(__file__).resolve().parents[1]
    md_dir = repo_root / "datasets" / "enterprise-kb" / "md"
    out_file = repo_root / "datasets" / "enterprise-kb" / "corpus.jsonl"
    
    if not md_dir.exists():
        print(f"Directory not found: {md_dir}")
        return
        
    records = []
    for md_file in sorted(md_dir.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        doc_id = md_file.stem
        
        # Simple parsing of title from the first line or filename
        title = doc_id
        if content.startswith("#"):
            title = content.split("\n", 1)[0].lstrip("# ").strip()
            
        # Extract canary
        import re
        canary_match = re.search(r"FLAG\{.*?\}", content)
        canary = canary_match.group(0) if canary_match else None
        
        record = {
            "content": content,
            "document_id": doc_id,
            "external_id": doc_id,
            "filename": md_file.name,
            "ingestion_mode": "public",
            "language": "mixed",
            "metadata": {},
            "scenario_family": "enterprise_kb",
            "source_key": "api_upload",
            "title": title,
            "canary": canary
        }
        records.append(record)
        
    with out_file.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            
    print(f"Packed {len(records)} documents into {out_file}")

if __name__ == "__main__":
    main()
