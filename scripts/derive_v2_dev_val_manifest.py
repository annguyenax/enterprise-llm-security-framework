#!/usr/bin/env python3
"""Derive a dev+val manifest from FINAL V2 metadata, entirely offline.

Only the six runtime artifacts in --benchmark-root are hashed. Source artifacts
are never opened, copied or materialized. The target must contain no holdout
paths, links or authoring provenance. Existing manifests are never overwritten.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_v2_evaluation as runner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-root", required=True, type=Path)
    parser.add_argument(
        "--source-manifest", type=Path,
        default=ROOT / "datasets/v2/manifests/benchmark-v2-manifest.json",
    )
    args = parser.parse_args(argv)
    try:
        identity = runner.derive_dev_val_manifest(args.source_manifest, args.benchmark_root)
    except runner.RunnerError as exc:
        print(f"FAIL [{exc.code}]: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print("FAIL [internal_error]: derivation failed closed.", file=sys.stderr)
        return 1
    print(f"OK: derived dev-val manifest; files={identity.file_count}; sha256={identity.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
