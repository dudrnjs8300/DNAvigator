# Run the full local quality gate: format check, lint, type check, tests.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\run_checks.ps1

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

Push-Location $repoRoot
try {
    Write-Host "==> ruff format --check"
    & $venvPython -m ruff format --check src tests
    if ($LASTEXITCODE -ne 0) { throw "ruff format check failed" }

    Write-Host "==> ruff check"
    & $venvPython -m ruff check src tests
    if ($LASTEXITCODE -ne 0) { throw "ruff check failed" }

    Write-Host "==> mypy"
    & $venvPython -m mypy src/genome_workbench
    if ($LASTEXITCODE -ne 0) { throw "mypy failed" }

    Write-Host "==> pytest"
    $env:QT_QPA_PLATFORM = "offscreen"
    & $venvPython -m pytest tests -q
    if ($LASTEXITCODE -ne 0) { throw "pytest failed" }

    Write-Host "All checks passed."
}
finally {
    Pop-Location
}
