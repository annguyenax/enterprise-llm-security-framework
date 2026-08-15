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

.PARAMETER ReleaseReadiness
    Chạy chế độ release-hardening (Phase 12F): focused tests + kiểm tra frozen
    artifact ở mức byte, báo cáo basetemp đã chọn, phát hiện khả năng tạo
    symlink, và phân biệt lỗi setup do path-length với lỗi assertion. Chế độ này
    KHÔNG chạy holdout, analyzer, validator hay determinism builder. Không đặt cờ
    này thì script giữ nguyên hành vi cũ.

.PARAMETER BaseTemp
    Đường dẫn pytest --basetemp tường minh, nên NGẮN để tránh vượt MAX_PATH trên
    Windows. Nếu bỏ trống, script tự chọn một default ngắn bên ngoài repo.

.EXAMPLE
    .\scripts\verify_phase.ps1
    .\scripts\verify_phase.ps1 -Focused
    .\scripts\verify_phase.ps1 -ReleaseReadiness
    .\scripts\verify_phase.ps1 -ReleaseReadiness -BaseTemp D:\p12f-bt
#>
[CmdletBinding()]
param(
    [switch]$Focused,
    [switch]$SkipBenchmark,
    [switch]$ReleaseReadiness,
    [string]$BaseTemp = ""
)

$ErrorActionPreference = "Continue"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$ExternalTempParent = Split-Path -Parent $RepoRoot
$VerificationToken = "{0}-{1}" -f $PID, ([guid]::NewGuid().ToString("N").Substring(0, 8))

# Release mode may take an explicit short basetemp; otherwise a short external
# default is chosen. A short root avoids Windows MAX_PATH failures during pytest
# fixture setup. The chosen root is reported below.
$BaseTempExplicit = $false
if ($BaseTemp -and $BaseTemp.Trim()) {
    $VerificationTempRoot = $BaseTemp.Trim()
    $BaseTempExplicit = $true
} elseif ($ReleaseReadiness) {
    # Deliberately short: <parent>\p12f<token>.
    $VerificationTempRoot = Join-Path $ExternalTempParent ("p12f" + $VerificationToken.Substring($VerificationToken.Length - 6))
} else {
    $VerificationTempRoot = Join-Path $ExternalTempParent ".p12e-$VerificationToken"
}
$FocusedBaseTemp = Join-Path $VerificationTempRoot "f"
$FullBaseTemp = Join-Path $VerificationTempRoot "a"
$FocusedCacheDir = Join-Path $VerificationTempRoot "cf"
$FullCacheDir = Join-Path $VerificationTempRoot "ca"
$env:PYTHONPYCACHEPREFIX = Join-Path $VerificationTempRoot "p"

# Test module trọng tâm của phase hiện tại (Phase 12E.3). Cập nhật khi sang phase mới.
$FocusedModules = @(
    "tests/test_guard_profile.py",
    "tests/test_rag_pipeline.py",
    "tests/test_v2_evaluation_runner.py",
    "tests/test_v2_result_analyzer.py",
    "tests/test_v2_holdout_authorization.py"
)

# Đường dẫn KHÔNG được thay đổi ngoài scope (invariant check).
# `app/` was removed from this list by maintainer decision when the enterprise
# KB / ACL retriever workstream began: that workstream's whole purpose is to
# change `app/`, so keeping it here would fail the gate on every commit and
# train reviewers to ignore the result. The remaining entries are unchanged.
#
# `report-latex-template/` was dropped from this list in the 2026-08-14 repo
# hygiene cleanup: that legacy LaTeX tree is no longer tracked (the live report
# source is `bao_cao_latex_dot2/`, which is edited every report cycle and so is
# deliberately not protected).
$ProtectedPaths = @("requirements.txt", "redteam/", "reports/evaluation/")

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

# Record a tri-state result (PASS / SKIP-CAPABILITY / FAIL). Only FAIL counts as
# a failure; SKIP-CAPABILITY is a neutral host-capability note.
function Record3($key, $state, $detail) {
    $script:results[$key] = [pscustomobject]@{ Ok = ($state -ne "FAIL"); Detail = $detail; State = $state }
    if ($state -eq "FAIL") { $script:failures += $key }
    $color = switch ($state) { "PASS" { "Green" } "FAIL" { "Red" } default { "Yellow" } }
    Write-Host ("  [{0}] {1}: {2}" -f $state, $key, $detail) -ForegroundColor $color
}

# Detect whether this host can create a symbolic link. Returns one of
# PASS (created and cleaned up), SKIP-CAPABILITY (OS/privilege refusal) or FAIL.
function Test-SymlinkCapability($tempRoot) {
    $probeDir = Join-Path $tempRoot "slp"
    $target = Join-Path $probeDir "t.txt"
    $link = Join-Path $probeDir "l.txt"
    try {
        New-Item -ItemType Directory -Path $probeDir -Force -ErrorAction Stop | Out-Null
        Set-Content -LiteralPath $target -Value "probe" -Encoding utf8 -ErrorAction Stop
        try {
            New-Item -ItemType SymbolicLink -Path $link -Target $target -ErrorAction Stop | Out-Null
        } catch {
            # A privilege / developer-mode / unsupported-OS refusal is a capability
            # gap, not a verification failure.
            return @{ State = "SKIP-CAPABILITY"; Detail = "symlink creation not permitted on this host" }
        }
        if (Test-Path -LiteralPath $link) {
            return @{ State = "PASS"; Detail = "symlink creation available" }
        }
        return @{ State = "FAIL"; Detail = "symlink reported created but is absent" }
    } catch {
        return @{ State = "FAIL"; Detail = "unexpected error probing symlink capability" }
    } finally {
        Remove-Item -LiteralPath $probeDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# Byte-level check of the governed auxiliary release-test fixture manifest.
# Requires: manifest present + final; exactly one file; expected path;
# file present; SHA-256 and size match. Returns @{ Ok; Detail }.
# No JSONL record is parsed.
function Test-AuxiliaryFixture($manifestPath, $baseDir) {
    if (-not (Test-Path $manifestPath)) {
        return @{ Ok = $false; Detail = "redteam/prompts-manifest.json not found" }
    }
    $am = Get-Content $manifestPath -Raw | ConvertFrom-Json
    $problems = @()
    if ($am.manifest_status -ne "final") { $problems += "manifest_status=$($am.manifest_status) (expected final)" }
    $files = @($am.files)
    if ($files.Count -ne 1) {
        $problems += "expected exactly 1 file, got $($files.Count)"
    } elseif ($files[0].path -ne "redteam/prompts.jsonl") {
        $problems += "unexpected path $($files[0].path)"
    } else {
        $p = Join-Path $baseDir $files[0].path
        if (-not (Test-Path $p)) {
            $problems += "$($files[0].path) MISSING"
        } else {
            $h = (Get-FileHash $p -Algorithm SHA256).Hash.ToLower()
            if ($h -ne $files[0].sha256) { $problems += "$($files[0].path) HASH MISMATCH" }
            $sz = (Get-Item $p).Length
            if ($sz -ne $files[0].size_bytes) { $problems += "$($files[0].path) SIZE MISMATCH ($sz)" }
        }
    }
    if ($problems.Count -eq 0) {
        return @{ Ok = $true; Detail = "1/1 byte-identical (redteam/prompts.jsonl, status=final)" }
    }
    return @{ Ok = $false; Detail = ($problems -join "; ") }
}

# Heuristic: does pytest output indicate a Windows path-length / MAX_PATH setup
# failure rather than a test assertion failure?
function Test-PathLengthFailure($output) {
    if (-not $output) { return $false }
    $patterns = @(
        "WinError 3",              # cannot find the path specified (often long-path)
        "WinError 206",            # filename or extension too long
        "MAX_PATH",
        "path too long",
        "filename or extension is too long",
        "The system cannot find the path"
    )
    foreach ($p in $patterns) {
        if ($output -match [regex]::Escape($p)) { return $true }
    }
    return $false
}

if (-not (Test-Path $Python)) {
    Write-Host "FAIL: khong tim thay $Python. Tao venv truoc." -ForegroundColor Red
    exit 1
}

try {
    New-Item -ItemType Directory -Path $VerificationTempRoot -ErrorAction Stop | Out-Null
} catch {
    Write-Host "FAIL: khong the tao external verification temp root." -ForegroundColor Red
    exit 1
}

Set-Location $RepoRoot

# ===========================================================================
# RELEASE-READINESS MODE (Phase 12F) — early-exit branch.
# Runs focused tests + byte-level frozen verify + symlink capability + basetemp
# report. Never runs holdout, analyzer, validator or determinism builder.
# Legacy behavior below is untouched when -ReleaseReadiness is not set.
# ===========================================================================
if ($ReleaseReadiness) {
    Write-Section "Release-readiness: environment"
    if ($BaseTempExplicit) { $btSource = "explicit" } else { $btSource = "short-default" }
    Record "basetemp_selected" $true ("{0} ({1})" -f $VerificationTempRoot, $btSource)

    $sym = Test-SymlinkCapability $VerificationTempRoot
    Record3 "symlink_capability" $sym.State $sym.Detail

    Write-Section "Release-readiness: focused tests (owned scope)"
    $relModules = @(
        "tests/test_v2_release_artifacts.py",
        "tests/test_verify_phase_release.py"
    )
    $relExisting = $relModules | Where-Object { Test-Path $_ }
    $relBaseTemp = Join-Path $VerificationTempRoot "rf"
    $relCache = Join-Path $VerificationTempRoot "rc"
    $out = & $Python -m pytest -q -p no:cacheprovider @relExisting --basetemp=$relBaseTemp -o "cache_dir=$relCache" 2>&1 | Out-String
    $relLine = ($out -split "`n" | Where-Object { $_ -match "\d+ passed|\d+ failed|error" } | Select-Object -Last 1).Trim()
    if ($LASTEXITCODE -eq 0) {
        Record "release_focused_tests" $true $relLine
    } elseif (Test-PathLengthFailure $out) {
        # Distinguish a path-length SETUP failure from a genuine assertion failure.
        Record "release_focused_tests" $false ("SETUP/path-length failure (not an assertion): {0}" -f $relLine)
    } else {
        Record "release_focused_tests" $false ("assertion/other failure: {0}" -f $relLine)
    }

    Write-Section "Release-readiness: frozen artifacts (byte-level only)"
    if (Test-Path "datasets/v2/manifests/benchmark-v2-manifest.json") {
        $manifest = Get-Content "datasets/v2/manifests/benchmark-v2-manifest.json" -Raw | ConvertFrom-Json
        $drift = @()
        $present = 0
        foreach ($entry in $manifest.files) {
            $p = Join-Path "datasets/v2" $entry.path
            if (-not (Test-Path $p)) { $drift += "$($entry.path) MISSING"; continue }
            $present++
            $h = (Get-FileHash $p -Algorithm SHA256).Hash.ToLower()
            if ($h -ne $entry.sha256) { $drift += "$($entry.path) CHANGED" }
        }
        if ($drift.Count -eq 0) {
            Record "frozen_artifacts_bytelevel" $true ("{0}/{1} byte-identical (status={2})" -f $present, $manifest.file_count, $manifest.manifest_status)
        } else {
            # Missing frozen artifacts are the known release-fragility case; report
            # them, but this is a byte-level check only (no semantic parsing).
            Record "frozen_artifacts_bytelevel" $false ($drift -join "; ")
        }
    } else {
        Record "frozen_artifacts_bytelevel" $false "FINAL manifest not found"
    }

    Write-Section "Release-readiness: auxiliary release test fixture (byte-level only)"
    $aux = Test-AuxiliaryFixture "redteam/prompts-manifest.json" $RepoRoot
    Record "release_auxiliary_artifacts_bytelevel" $aux.Ok $aux.Detail

    Write-Section "Release-readiness: explicit non-actions"
    Write-Host "  [INFO] holdout: not run" -ForegroundColor DarkGray
    Write-Host "  [INFO] analyzer: not run" -ForegroundColor DarkGray
    Write-Host "  [INFO] validator/determinism: not run (byte-level only)" -ForegroundColor DarkGray

    $commit = (git rev-parse HEAD).Trim()
    $branch = (git branch --show-current).Trim()
    Write-Host ""
    Write-Host "=============== RELEASE-READINESS EVIDENCE BLOCK ===============" -ForegroundColor Yellow
    Write-Host @"

## Release-Readiness Evidence
- branch: $branch
- base_commit: $commit
- basetemp: $VerificationTempRoot
"@
    foreach ($k in $results.Keys) {
        $r = $results[$k]
        if ($r.PSObject.Properties.Name -contains "State") {
            $mark = $r.State
        } elseif ($r.Ok) { $mark = "PASS" } else { $mark = "FAIL" }
        Write-Host ("- {0}: {1} ({2})" -f $k, $mark, $r.Detail)
    }
    Write-Host "===============================================================" -ForegroundColor Yellow

    try {
        Remove-Item -LiteralPath $VerificationTempRoot -Recurse -Force -ErrorAction Stop
    } catch {
        Write-Warning "Khong the xoa release verification temp root: $VerificationTempRoot"
    }

    if ($failures.Count -gt 0) {
        Write-Host ""
        Write-Host ("KET QUA (release): FAIL - {0}: {1}" -f $failures.Count, ($failures -join ', ')) -ForegroundColor Red
        exit 1
    }
    Write-Host ""
    Write-Host "KET QUA (release): TAT CA PASS." -ForegroundColor Green
    exit 0
}

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
$out = & $Python -m pytest -q -p no:cacheprovider @existing --basetemp=$FocusedBaseTemp -o "cache_dir=$FocusedCacheDir" 2>&1 | Out-String
$focusedLine = ($out -split "`n" | Where-Object { $_ -match "\d+ passed|\d+ failed|error" } | Select-Object -Last 1).Trim()
Record "focused_tests" ($LASTEXITCODE -eq 0) $focusedLine

# ---------------------------------------------------------------------------
if (-not $Focused) {
    Write-Section "3. Full repository suite (khong --ignore)"
    $out = & $Python -m pytest -q -p no:cacheprovider --basetemp=$FullBaseTemp -o "cache_dir=$FullCacheDir" 2>&1 | Out-String
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

try {
    Remove-Item -LiteralPath $VerificationTempRoot -Recurse -Force -ErrorAction Stop
} catch {
    Write-Warning "Khong the xoa external verification temp root: $VerificationTempRoot"
}

if ($failures.Count -gt 0) {
    Write-Host ""
    Write-Host ("KET QUA: FAIL - {0} hang muc: {1}" -f $failures.Count, ($failures -join ', ')) -ForegroundColor Red
    exit 1
}
Write-Host ""
Write-Host "KET QUA: TAT CA PASS - san sang gui audit." -ForegroundColor Green
exit 0
