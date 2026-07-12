# Phase 12B manual smoke test for the SQLite FTS5/BM25 retrieval
# foundation (POST /v1/documents/ingest, POST /v1/retrieve).
#
# Usage (from the repository root):
#   1. Start the server against a dedicated scratch database (recommended,
#      so this script never touches your normal data/retrieval.db):
#        $env:RETRIEVAL_DB_PATH = "$env:TEMP\smoke-retrieval.db"
#        uvicorn app.main:app --reload
#   2. In a second shell:
#        powershell -ExecutionPolicy Bypass -File scripts/smoke_test_retrieval.ps1
#
# This is a manual QA convenience script, not the automated test suite --
# see tests/test_sqlite_bm25.py, tests/test_ingestion.py,
# tests/test_chunking.py, and tests/test_retrieval_routes.py for that.
# Uses only ASCII output so it renders correctly in any PowerShell console
# codepage (same convention as scripts/smoke_test_gateway.ps1).
#
# Does not touch datasets/, redteam/, or any frozen benchmark file --
# every document ingested here is synthetic content created by this
# script, ingested under the "api_upload" source policy.

$ErrorActionPreference = "Stop"
$BaseUrl = "http://127.0.0.1:8000"
$RunId = [guid]::NewGuid().ToString("N").Substring(0, 8)

function Write-Section($title) {
    Write-Host ""
    Write-Host "=== $title ===" -ForegroundColor Cyan
}

Write-Section "1. GET /health"
$health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get
$health | ConvertTo-Json

Write-Section "2. POST /v1/documents/ingest (2 synthetic documents)"
$docA = "policy-a-$RunId"
$docB = "policy-b-$RunId"
$ingestBody = @{
    documents = @(
        @{
            external_id = $docA
            source_key  = "api_upload"
            title       = "Smoke Test Warranty Policy $RunId"
            text        = "The SmokeWidget-$RunId ships with a 2-year limited warranty.`n`nReturns are accepted within 30 days of purchase."
            metadata    = @{}
        },
        @{
            external_id = $docB
            source_key  = "api_upload"
            title       = "Smoke Test Shipping Policy $RunId"
            text        = "Standard shipping for SmokeWidget-$RunId takes 3-5 business days.`n`nExpedited shipping is available at checkout."
            metadata    = @{}
        }
    )
} | ConvertTo-Json -Depth 5
$ingestResult = Invoke-RestMethod -Uri "$BaseUrl/v1/documents/ingest" -Method Post -Body $ingestBody -ContentType "application/json"
$ingestResult | ConvertTo-Json -Depth 5

Write-Section "3. POST /v1/retrieve (query: warranty)"
$retrieveBody = @{ query = "SmokeWidget-$RunId warranty"; top_k = 5 } | ConvertTo-Json
$retrieveResult = Invoke-RestMethod -Uri "$BaseUrl/v1/retrieve" -Method Post -Body $retrieveBody -ContentType "application/json"
$retrieveResult | ConvertTo-Json -Depth 5

Write-Section "4. POST /v1/documents/ingest (update document A -> new warranty period)"
$updateBody = @{
    documents = @(
        @{
            external_id = $docA
            source_key  = "api_upload"
            title       = "Smoke Test Warranty Policy $RunId (updated)"
            text        = "The SmokeWidget-$RunId now ships with a 3-year extended warranty as of this update."
            metadata    = @{}
        }
    )
} | ConvertTo-Json -Depth 5
$updateResult = Invoke-RestMethod -Uri "$BaseUrl/v1/documents/ingest" -Method Post -Body $updateBody -ContentType "application/json"
$updateResult | ConvertTo-Json -Depth 5

# Phase 12B Codex audit fix (Major #5 follow-on): retrieval terms are now
# combined with OR (see app/retrieval/sqlite_bm25.py::_build_safe_match_query
# and ADR-002-retrieval-engine.md), so a query naming both the shared
# "SmokeWidget-<id>" token and a stale term like "2-year" will still match
# document B (the shipping policy, which only shares the SmokeWidget
# token) even after document A's "2-year" content is replaced -- that is
# expected, correct OR-mode behavior, not a stale-row bug. The actual
# invariant this script checks ("no stale FTS row survives an update") is
# tested directly instead: search broadly for the shared token, then
# assert no returned hit's *text* still contains the old phrase, and that
# the new phrase is present.
Write-Section "5. POST /v1/retrieve (query: SmokeWidget token -- check for stale text)"
$combinedBody = @{ query = "SmokeWidget-$RunId warranty"; top_k = 5 } | ConvertTo-Json
$combinedResult = Invoke-RestMethod -Uri "$BaseUrl/v1/retrieve" -Method Post -Body $combinedBody -ContentType "application/json"
$combinedResult | ConvertTo-Json -Depth 5

$staleTextPresent = $false
$freshTextPresent = $false
foreach ($hit in $combinedResult.hits) {
    if ($hit.text -like "*2-year limited warranty*") { $staleTextPresent = $true }
    if ($hit.text -like "*3-year extended warranty*") { $freshTextPresent = $true }
}

Write-Section "Summary"
$ingestOk = ($ingestResult.indexed -eq 2) -and ($ingestResult.rejected -eq 0)
$retrieveOk = $retrieveResult.total_hits -ge 1
$updateOk = $updateResult.updated -eq 1
$staleGone = -not $staleTextPresent
$freshFound = $freshTextPresent

Write-Host "health.status:                 $($health.status)"
Write-Host "ingest indexed/rejected:       $($ingestResult.indexed) / $($ingestResult.rejected)"
Write-Host "retrieve total_hits:           $($retrieveResult.total_hits)"
Write-Host "update status:                 $($updateResult.items[0].status)"
Write-Host "stale text ('2-year') absent:  $staleGone"
Write-Host "fresh text ('3-year') present: $freshFound"

if ($health.status -eq "ok" -and $ingestOk -and $retrieveOk -and $updateOk -and $staleGone -and $freshFound) {
    Write-Host ""
    Write-Host "SMOKE TEST PASSED" -ForegroundColor Green
    Write-Host "Note: if the server was started with a scratch RETRIEVAL_DB_PATH, you"
    Write-Host "can delete that file now that the server has been stopped (SQLite keeps"
    Write-Host "the file open while the server process is running, so it cannot be"
    Write-Host "safely deleted from this script while the server is still up)."
} else {
    Write-Host ""
    Write-Host "SMOKE TEST FAILED - review output above" -ForegroundColor Red
    exit 1
}
