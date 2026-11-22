"""Build the synthetic furniture SQLite database used by the P4 SQL agent lab.

Applies datasets/furniture/sql/schema.sql then seed.sql. Stdlib only.
Refuses to overwrite an existing file unless --force is given.

Usage:
    python scripts/build_furniture_db.py --out data/furniture.db [--force]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "datasets" / "furniture" / "sql"
TABLES = ["branches", "warehouses", "products", "inventory", "customers", "orders",
          "order_items", "suppliers", "receivables", "product_reviews", "employees", "promotions",
          "shipments", "warranty_claims", "support_tickets", "internal_secrets"]


def build(out: Path, force: bool = False) -> dict[str, int]:
    if out.exists():
        if not force:
            raise FileExistsError(f"{out.name} already exists; pass --force to rebuild")
        out.unlink()
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()
    conn = sqlite3.connect(tmp)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript((SQL_DIR / "schema.sql").read_text(encoding="utf-8"))
        conn.executescript((SQL_DIR / "seed.sql").read_text(encoding="utf-8"))
        problems = conn.execute("PRAGMA foreign_key_check").fetchall()
        if problems:
            raise RuntimeError(f"foreign key check failed: {len(problems)} row(s)")
        counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}
        conn.commit()
    finally:
        conn.close()
    tmp.replace(out)
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="data/furniture.db")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    try:
        counts = build(out, args.force)
    except FileExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for table, n in counts.items():
        print(f"{table:18s} {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
