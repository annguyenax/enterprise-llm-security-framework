<#
.SYNOPSIS
    Chạy toàn bộ checklist verification của một phase và in ra EVIDENCE BLOCK
    sẵn định dạng để dán vào prompt audit (Code X / Gemini / Grok).

.DESCRIPTION
    Thay thế việc gõ tay ~15 lệnh mỗi vòng fix. Không sửa file nào, không cài
    gói nào, không gọi mạng, không gọi LLM — thuần deterministic.

    Đây là "Test Verifier" trong quy trình multi-agent: verifier phải là script,
    không phải LLM, vì LLM có thể báo sai số liệu còn script thì không.

.PARAMETER Focused
    Chỉ chạy các test module trọng tâm của phase (nhanh, dùng khi đang lặp fix).

.PARAMETER SkipBenchmark
    Bỏ qua validator/determinism/manifest của benchmark v2 (dùng cho phase
    không đụng datasets/v2).

.EXAMPLE
    .\scripts\verify_phase.ps1
    .\scripts\verify_phase.ps1 -Focused
#>
[CmdletBinding()]
param(
    [switch]$Focused,
    [switch]$SkipBenchmark
)

$ErrorActionPreference = "Continue"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$BaseTemp = Join-Path $env:TEMP "pytest-verify-phase"

# Test module trọng tâm của phase hiện tại (Phase 12D). Cập nhật khi sang phase mới.
$FocusedModules = @(
    "tests/test_benchmark_v2_schema.py",
    "tests/test_benchmark_v2_integrity.py",
    "tests/test_benchmark_v2_freeze.py"
)

# Đường dẫn KHÔNG được thay đổi ngoài scope (invariant check).
$ProtectedPaths = @("app/", "requirements.txt", "redteam/", "reports/evaluation/", "report-latex-template/")

$results = [ordered]@{}
$failures = @()

function Write-Section($name) {
    Write-Host ""
    Write-Host "=== $name ===" -ForegroundColor Cyan
}

function Record($key, $ok, $detail) {
    $script:results[$key] = [pscustomobject]@{ Ok = $ok; Detail = $detail }
    if (-not $ok) { $script:failures += $key }
    $mark = if ($ok) { "PASS" } else { "FAIL" }
    $color = if ($ok) { "Green" } else { "Red" }
    Write-Host ("  [{0}] {1}: {2}" -f $mark, $key, $detail) -ForegroundColor $color
}

if (-not (Test-Path $Python)) {
    Write-Host "FAIL: khong tim thay $Python. Tao venv truoc." -ForegroundColor Red
    exit 1
}

Set-Location $RepoRoot

# ---------------------------------------------------------------------------
Write-Section "1. Python compile"
# ---------------------------------------------------------------------------
$changed = @(git diff --name-only) + @(git ls-files --others --exclude-standard)
$pyFiles = $changed | Where-Object { $_ -like "*.py" -and (Test-Path $_) } | Select-Object -Unique
if ($pyFiles.Count -eq 0) {
    Record "compile" $true "khong co file .py thay doi"
} else {
    & $Python -m py_compile @pyFiles 2>&1 | Out-Null
    Record "compile" ($LASTEXITCODE -eq 0) ("$($pyFiles.Count) file(s)")
}

# ---------------------------------------------------------------------------
Write-Section "2. Focused test suite"
# ---------------------------------------------------------------------------
$existing = $FocusedModules | Where-Object { Test-Path $_ }
$out = & $Python -m pytest -q -p no:cacheprovider @existing --basetemp=$BaseTemp 2>&1 | Out-String
$focusedLine = ($out -split "`n" | Where-Object { $_ -match "\d+ passed|\d+ failed|error" } | Select-Object -Last 1).Trim()
Record "focused_tests" ($LASTEXITCODE -eq 0) $focusedLine

# ---------------------------------------------------------------------------
if (-not $Focused) {
    Write-Section "3. Full repository suite (khong --ignore)"
    $out = & $Python -m pytest -q -p no:cacheprovider --basetemp=$BaseTemp 2>&1 | Out-String
    $fullLine = ($out -split "`n" | Where-Object { $_ -match "\d+ passed|\d+ failed|error" } | Select-Object -Last 1).Trim()
    Record "full_suite" ($LASTEXITCODE -eq 0) $fullLine
} else {
    $fullLine = "not_run (-Focused)"
    Write-Host "  [SKIP] full_suite: -Focused" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
if (-not $SkipBenchmark -and (Test-Path "datasets/v2")) {
    Write-Section "4. Benchmark v2: validator / determinism / manifest"

    $out = & $Python scripts/validate_v2_benchmark.py 2>&1 | Out-String
    Record "validator" ($LASTEXITCODE -eq 0) ($out.Trim() -split "`n")[0]

    $out = & $Python scripts/build_v2_benchmark.py --verify-determinism 2>&1 | Out-String
    Record "determinism" ($LASTEXITCODE -eq 0) ($out.Trim() -split "`n")[0]

    $out = & $Python scripts/freeze_v2_benchmark.py verify 2>&1 | Out-String
    Record "manifest" ($LASTEXITCODE -eq 0) ($out.Trim() -split "`n")[0]

    # Chín artifact đã freeze phải bat bien (Gemini/Grok đã audit đúng bytes này).
    $manifest = Get-Content "datasets/v2/manifests/benchmark-v2-manifest.json" -Raw | ConvertFrom-Json
    $drift = @()
    foreach ($entry in $manifest.files) {
        $p = Join-Path "datasets/v2" $entry.path
        if (-not (Test-Path $p)) { $drift += "$($entry.path) MISSING"; continue }
        $h = (Get-FileHash $p -Algorithm SHA256).Hash.ToLower()
        if ($h -ne $entry.sha256) { $drift += "$($entry.path) CHANGED" }
    }
    if ($drift.Count -eq 0) {
        $driftDetail = "$($manifest.file_count) file byte-identical (status=$($manifest.manifest_status))"
    } else {
        $driftDetail = $drift -join "; "
    }
    Record "frozen_artifacts" ($drift.Count -eq 0) $driftDetail
}

# ---------------------------------------------------------------------------
Write-Section "5. Git hygiene + scope invariants"
# ---------------------------------------------------------------------------
git diff --check 2>&1 | Out-Null
Record "git_diff_check" ($LASTEXITCODE -eq 0) "khong co whitespace error"

$violations = @()
foreach ($p in $ProtectedPaths) {
    $hit = $changed | Where-Object { $_ -like "$p*" }
    if ($hit) { $violations += $hit }
}
if ($violations.Count -eq 0) {
    $scopeDetail = "khong dung vao: " + ($ProtectedPaths -join ', ')
} else {
    $scopeDetail = "VI PHAM: " + ($violations -join ', ')
}
Record "scope_invariants" ($violations.Count -eq 0) $scopeDetail

$tmpDirs = @(@(".pytest_cache", ".tmp", ".pytest-tmp") | Where-Object { Test-Path $_ })
if ($tmpDirs.Count -eq 0) { $tmpDetail = "sach" } else { $tmpDetail = "con lai: " + ($tmpDirs -join ', ') }
Record "no_temp_dirs" ($tmpDirs.Count -eq 0) $tmpDetail

$dbPattern = '\.(db|sqlite|sqlite3)$'
$dbFiles = @(git ls-files | Where-Object { $_ -match $dbPattern })
if ($dbFiles.Count -eq 0) { $dbDetail = "khong co db duoc track" } else { $dbDetail = $dbFiles -join ', ' }
Record "no_tracked_db" ($dbFiles.Count -eq 0) $dbDetail

# ---------------------------------------------------------------------------
# EVIDENCE BLOCK — dán thẳng vào prompt audit
# ---------------------------------------------------------------------------
$commit = (git rev-parse HEAD).Trim()
$branch = (git branch --show-current).Trim()
$nameStatus = (git diff --name-status | Out-String).Trim()
$untracked = (git ls-files --others --exclude-standard | Out-String).Trim()

Write-Host ""
Write-Host "=============== EVIDENCE BLOCK (copy vao prompt audit) ===============" -ForegroundColor Yellow
Write-Host @"

## Verification Evidence
- branch: $branch
- base_commit: $commit
- focused_tests: $focusedLine
- full_suite: $fullLine
"@
foreach ($k in $results.Keys) {
    if ($k -eq "focused_tests" -or $k -eq "full_suite") { continue }
    $r = $results[$k]
    if ($r.Ok) { $mark = "PASS" } else { $mark = "FAIL" }
    Write-Host ("- {0}: {1} ({2})" -f $k, $mark, $r.Detail)
}
if (-not $nameStatus) { $nameStatus = "(none)" }
if (-not $untracked) { $untracked = "(none)" }
Write-Host ""
Write-Host "### Modified (tracked)"
Write-Host $nameStatus
Write-Host ""
Write-Host "### Untracked"
Write-Host $untracked
Write-Host ""
Write-Host "=====================================================================" -ForegroundColor Yellow

if ($failures.Count -gt 0) {
    Write-Host ""
    Write-Host ("KET QUA: FAIL - {0} hang muc: {1}" -f $failures.Count, ($failures -join ', ')) -ForegroundColor Red
    exit 1
}
Write-Host ""
Write-Host "KET QUA: TAT CA PASS - san sang gui audit." -ForegroundColor Green
exit 0
