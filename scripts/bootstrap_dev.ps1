# Bootstrap a local development environment: venv + editable install + dev deps.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\bootstrap_dev.ps1

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $repoRoot
try {
    if (-not (Test-Path ".venv")) {
        Write-Host "Creating virtual environment..."
        python -m venv .venv
    }

    $venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -e ".[dev]"

    Write-Host "Bootstrap complete. Activate with: .venv\Scripts\Activate.ps1"
}
finally {
    Pop-Location
}
