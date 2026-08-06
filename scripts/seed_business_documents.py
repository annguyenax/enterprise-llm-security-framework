"""Seed synthetic payroll, employment, and vendor-contract documents."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.workspace.business_document_seed import seed_business_documents


if __name__ == "__main__":
    print(json.dumps(seed_business_documents(), ensure_ascii=False, indent=2))
