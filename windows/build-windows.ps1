$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))
if (-not (Test-Path .venv-build)) { py -3.12 -m venv .venv-build }
$python = Join-Path (Get-Location) '.venv-build\Scripts\python.exe'
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt 'pyinstaller>=6,<7'
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
& $python -m PyInstaller --noconfirm --clean windows\VibeQAMaster.spec
if ($LASTEXITCODE -ne 0) { throw 'Executable build failed' }
& powershell -NoProfile -ExecutionPolicy Bypass -File windows\smoke-windows.ps1
if ($LASTEXITCODE -ne 0) { throw 'Executable smoke test failed' }
$inno = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
if (-not (Test-Path $inno)) { throw 'Inno Setup 6 is required for installer. Executable: dist\VibeQAMaster\VibeQAMaster.exe' }
& $inno windows\installer.iss
if ($LASTEXITCODE -ne 0) { throw 'Installer build failed' }
& powershell -NoProfile -ExecutionPolicy Bypass -File windows\verify-installer.ps1
if ($LASTEXITCODE -ne 0) { throw 'Installer verification failed' }
Write-Host 'Installer: release\VibeCodeQAMaster-Setup.exe'
