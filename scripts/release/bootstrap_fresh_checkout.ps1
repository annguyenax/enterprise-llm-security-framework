<#
.SYNOPSIS
    Phase 12G fresh-checkout bootstrap.

.DESCRIPTION
    Prepares a fresh checkout / worktree for review by materializing the
    git-ignored FINAL benchmark artifacts and the governed redteam fixture via
    the EXISTING integrated materializer
    (scripts/materialize_v2_frozen_artifacts.py --include-redteam-prompts).

    It does not duplicate materializer logic, performs no manual file copying,
    never commits or stages ignored artifacts, and never runs holdout,
    validation or analyzer. A temporary .venv junction is created only when
    -CreateVenvJunction is supplied and is always removed in finally. Release
    readiness runs only when -ReleaseReadiness is supplied, with a short external
    basetemp. Output is a single content-free JSON summary.

.PARAMETER SourceRepo
    Governed source repository that already contains the materialized artifacts.

.PARAMETER TargetCheckout
    Fresh checkout / worktree to materialize into.

.PARAMETER ExpectedCommit
    Expected HEAD of the target checkout (40-hex). Verified before any action.

.PARAMETER VenvSource
    Path to an existing .venv to junction into the target (required with
    -CreateVenvJunction or -ReleaseReadiness).

.PARAMETER CreateVenvJunction
    Create a temporary .venv junction in the target (removed in finally).

.PARAMETER ReleaseReadiness
    After materialization, run verify_phase.ps1 -ReleaseReadiness once.

.PARAMETER BaseTemp
    Short external pytest basetemp for release readiness.

.PARAMETER DryRun
    Materialize in --dry-run mode (writes nothing).
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$SourceRepo,
    [Parameter(Mandatory = $true)][string]$TargetCheckout,
    [Parameter(Mandatory = $true)][string]$ExpectedCommit,
    [string]$VenvSource = "",
    [switch]$CreateVenvJunction,
    [switch]$ReleaseReadiness,
    [string]$BaseTemp = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$summary = [ordered]@{
    tool                    = "bootstrap_fresh_checkout"
    ok                      = $false
    expected_commit         = $ExpectedCommit
    commit_verified         = $false
    tree_clean              = $false
    materializer_invoked    = $false
    materializer_dry_run    = [bool]$DryRun
    include_redteam_prompts = $true
    manual_copy_used        = $false
    junction_created        = $false
    junction_removed        = $false
    release_readiness_run   = $false
    holdout_run             = $false
    validation_run          = $false
    analyzer_run            = $false
    steps                   = @()
}
$junctionPath = Join-Path $TargetCheckout ".venv"
$junctionMade = $false
$code = 1

function Stop-Bootstrap($message) {
    $script:summary.steps += $message
    throw "STOP"
}

try {
    # --- Identity + cleanliness ---
    $head = (& git -C $TargetCheckout rev-parse HEAD).Trim()
    if ($head -ne $ExpectedCommit) { Stop-Bootstrap "commit mismatch: $head != $ExpectedCommit" }
    $summary.commit_verified = $true

    $status = (& git -C $TargetCheckout status --porcelain --untracked-files=no)
    if (-not [string]::IsNullOrWhiteSpace($status)) { Stop-Bootstrap "target working tree is not clean" }
    $summary.tree_clean = $true

    # --- Optional temporary venv junction ---
    if ($CreateVenvJunction -or $ReleaseReadiness) {
        if ([string]::IsNullOrWhiteSpace($VenvSource) -or -not (Test-Path $VenvSource)) {
            Stop-Bootstrap "VenvSource is required and must exist for junction/release-readiness"
        }
        if (-not (Test-Path $junctionPath)) {
            New-Item -ItemType Junction -Path $junctionPath -Target $VenvSource -ErrorAction Stop | Out-Null
            $junctionMade = $true
            $summary.junction_created = $true
            $summary.steps += "created temporary .venv junction"
        }
    }

    # --- Materialize via the EXISTING integrated materializer (no manual copy) ---
    $python = Join-Path $SourceRepo ".venv\Scripts\python.exe"
    if (-not (Test-Path $python)) { $python = "python" }
    $materializer = Join-Path $TargetCheckout "scripts\materialize_v2_frozen_artifacts.py"
    $matArgs = @($materializer,
                 "--source-root", $SourceRepo,
                 "--target-root", $TargetCheckout,
                 "--include-redteam-prompts")
    if ($DryRun) { $matArgs += "--dry-run" }
    & $python @matArgs | Out-Null
    if ($LASTEXITCODE -ne 0) { Stop-Bootstrap "materializer failed (exit $LASTEXITCODE)" }
    $summary.materializer_invoked = $true
    $summary.steps += "materializer completed"

    # --- Confirm no ignored artifact was staged ---
    $staged = (& git -C $TargetCheckout diff --cached --name-only)
    if (-not [string]::IsNullOrWhiteSpace($staged)) { Stop-Bootstrap "unexpected staged changes after materialization" }

    # --- Optional release readiness (never holdout/validation/analyzer) ---
    if ($ReleaseReadiness) {
        if ([string]::IsNullOrWhiteSpace($BaseTemp)) { Stop-Bootstrap "BaseTemp is required for release readiness" }
        $verify = Join-Path $TargetCheckout "scripts\verify_phase.ps1"
        & powershell -ExecutionPolicy Bypass -File $verify -ReleaseReadiness -BaseTemp $BaseTemp | Out-Null
        $summary.release_readiness_run = $true
        $summary.release_readiness_exit = $LASTEXITCODE
        $summary.steps += "release readiness completed (exit $LASTEXITCODE)"
    }

    $summary.ok = $true
    $code = 0
}
catch {
    if ($_.Exception.Message -ne "STOP") {
        $summary.steps += ("error: " + $_.Exception.Message)
    }
}
finally {
    if ($junctionMade -and (Test-Path $junctionPath)) {
        try {
            Remove-Item -LiteralPath $junctionPath -Recurse -Force -ErrorAction Stop
            $summary.junction_removed = $true
        } catch {
            Write-Warning ("could not remove temporary junction: " + $junctionPath)
        }
    }
    $summary.steps = @($summary.steps)
    Write-Output ($summary | ConvertTo-Json -Depth 6)
    exit $code
}
