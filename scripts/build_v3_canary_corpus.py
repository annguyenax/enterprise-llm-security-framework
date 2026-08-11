#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sinh corpus canary CÙNG namespace với exfil_target của datasets/v3/cases.

Mỗi case malicious có `exfil_target` dạng FLAG{...}. Runner chỉ coi exfil
đo được khi canary đó có trong corpus đã seed. Script này đọc all.jsonl
(hoặc malicious.jsonl) và ghi:

  datasets/v3/corpus/canary-docs.jsonl

Mỗi dòng:
  {"filename": "canary-case-001.md", "content": "...FLAG{...}...", "canary": "FLAG{...}"}

Chạy:
  .venv\\Scripts\\python.exe scripts/build_v3_canary_corpus.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = REPO_ROOT / "datasets" / "v3" / "cases" / "all.jsonl"
DEFAULT_OUT = REPO_ROOT / "datasets" / "v3" / "corpus" / "canary-docs.jsonl"
DEFAULT_MANIFEST = REPO_ROOT / "datasets" / "v3" / "manifests" / "v3-canary-corpus-manifest.json"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build canary corpus aligned to v3 cases")
    p.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    p.add_argument("--output", type=Path, default=DEFAULT_OUT)
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = p.parse_args(argv)

    cases_path = args.cases if args.cases.is_absolute() else REPO_ROOT / args.cases
    out_path = args.output if args.output.is_absolute() else REPO_ROOT / args.output
    manifest_path = args.manifest if args.manifest.is_absolute() else REPO_ROOT / args.manifest

    if not cases_path.is_file():
        print(f"FAIL: missing {cases_path}", file=sys.stderr)
        return 2

    rows: list[dict] = []
    seen: set[str] = set()
    with cases_path.open(encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, 1):
            if not raw.strip():
                continue
            rec = json.loads(raw)
            if not isinstance(rec, dict):
                print(f"FAIL: {cases_path.name}:{line_no} not object", file=sys.stderr)
                return 2
            if rec.get("expected_label") != "malicious":
                continue
            target = rec.get("exfil_target")
            if not isinstance(target, str) or not target.strip():
                continue
            target = target.strip()
            if target in seen:
                continue
            seen.add(target)
            case_id = str(rec.get("id") or f"anon-{line_no}")
            safe_id = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in case_id)
            filename = f"canary-{safe_id}.md"
            content = (
                f"# Synthetic canary document for {case_id}\n\n"
                f"Lab-only Northwind Retail Group fixture.\n\n"
                f"Sensitive marker for exfiltration measurement:\n\n"
                f"`{target}`\n\n"
                f"Dữ liệu nhạy cảm: {target}\n"
            )
            rows.append(
                {
                    "filename": filename,
                    "content": content,
                    "canary": target,
                    "case_id": case_id,
                }
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            # Content-free relative to answers: still contains canary by design
            # (this is the seed corpus, not a result artifact).
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    rel = out_path.relative_to(REPO_ROOT).as_posix()
    manifest = {
        "files": {rel: _sha256_file(out_path)},
        "canary_count": len(rows),
        "schema": "phase13-v3-canary-corpus-v1",
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Wrote {len(rows)} canary docs → {out_path.relative_to(REPO_ROOT)}")
    print(f"Manifest → {manifest_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
