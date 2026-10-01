$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Create .venv and install requirements-build.txt first.' }
Push-Location $PSScriptRoot
try {
    & $python -m PyInstaller --noconfirm --onefile --noupx --name RDPWrapUpdater --add-data 'assets;assets' src/updater.py
    if ($LASTEXITCODE -ne 0) { throw 'Console executable build failed.' }
    & $python -m PyInstaller --noconfirm --onefile --windowed --noupx --name RDPWrapUpdaterSilent --add-data 'assets;assets' src/updater.py
    if ($LASTEXITCODE -ne 0) { throw 'Silent executable build failed.' }
} finally { Pop-Location }
