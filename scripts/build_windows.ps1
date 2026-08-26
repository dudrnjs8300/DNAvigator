# Build the Windows onedir executable locally and run the packaged smoke tests.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

Push-Location $repoRoot
try {
    & $venvPython -m pip show pyinstaller *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing PyInstaller..."
        & $venvPython -m pip install pyinstaller
    }

    Write-Host "==> PyInstaller onedir build"
    & $venvPython -m PyInstaller scripts\genome_workbench.spec --distpath dist --workpath build --noconfirm
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

    $exePath = Join-Path $repoRoot "dist\GenomeWorkbench\GenomeWorkbench.exe"

    Write-Host "==> packaged --self-test"
    & $exePath --self-test
    if ($LASTEXITCODE -ne 0) { throw "packaged self-test failed" }

    Write-Host "==> packaged --smoke-test"
    $smokeOut = Join-Path $repoRoot "build\smoke_out"
    New-Item -ItemType Directory -Force -Path $smokeOut | Out-Null
    & $exePath --smoke-test (Join-Path $repoRoot "tests\fixtures") $smokeOut
    if ($LASTEXITCODE -ne 0) { throw "packaged smoke-test failed" }

    Write-Host "Build and packaging smoke tests passed: $exePath"
}
finally {
    Pop-Location
}
