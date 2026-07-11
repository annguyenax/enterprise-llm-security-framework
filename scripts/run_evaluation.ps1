param(
    [switch]$Comparison
)

$paramBlock = @()
if ($Comparison) {
    $paramBlock += "--comparison"
}

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $RepoRoot
try {
    python scripts/run_evaluation.py @paramBlock
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}
