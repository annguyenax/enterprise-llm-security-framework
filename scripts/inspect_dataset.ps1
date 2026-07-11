# Phase 5 dataset inspection script.
#
# Usage (from the repository root):
#   powershell -ExecutionPolicy Bypass -File scripts/inspect_dataset.ps1
#
# Prints: number of clean docs, number of poisoned docs, number of chunks
# generated, and sample doc IDs, by running scripts/inspect_dataset.py
# (which only uses app/services/dataset_loader.py -- standard library
# only, no FastAPI/pydantic required). Uses only ASCII output so it
# renders correctly in any PowerShell console codepage (same convention
# as scripts/smoke_test_gateway.ps1).

$ErrorActionPreference = "Stop"

python scripts/inspect_dataset.py
