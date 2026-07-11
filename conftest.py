"""Ensures the project root is importable as the `app` package when running
`pytest` (pytest's rootless import mode does not always add the repo root to
`sys.path` by itself)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
