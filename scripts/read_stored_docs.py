import sys
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parent.parent

if len(sys.argv) < 2:
    raise SystemExit("Usage: python scripts/read_stored_docs.py <document-id> [...]")

paths = [ROOT / 'data' / 'documents' / f'{UUID(value)}.txt' for value in sys.argv[1:]]

for p in paths:
    print('---', p)
    try:
        print(p.read_text(encoding='utf-8'))
    except FileNotFoundError:
        print('(missing)')
