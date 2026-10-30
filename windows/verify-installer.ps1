$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))
$installer = Join-Path (Get-Location) 'release\VibeCodeQAMaster-Setup.exe'
if (-not (Test-Path $installer)) { throw "Installer missing: $installer" }

# The installer is exercised only in the dedicated temporary test directory.
# Do not use an existing user installation or uninstall anything outside it.
$testFolder = Join-Path $env:TEMP ("VibeQASmoke-" + [guid]::NewGuid().ToString('N'))
$logPath = Join-Path $env:TEMP ("VibeQASmoke-" + [guid]::NewGuid().ToString('N') + '.log')
$arguments = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR="' + $testFolder + '" /LOG="' + $logPath + '"'
$installProcess = Start-Process -FilePath $installer -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
if ($installProcess.ExitCode -ne 0) { throw "Installer exit code: $($installProcess.ExitCode). See $logPath" }
$installedExe = Join-Path $testFolder 'VibeQAMaster.exe'
if (-not (Test-Path $installedExe)) { throw "Installed EXE missing: $installedExe" }
$check = Start-Process -FilePath $installedExe -ArgumentList '--self-check' -WindowStyle Hidden -Wait -PassThru
if ($check.ExitCode -ne 0) { throw "Installed API self-check failed: $($check.ExitCode)" }
$installedProcess = Start-Process -FilePath $installedExe -WindowStyle Hidden -PassThru
try {
    Start-Sleep -Seconds 6
    $installedProcess.Refresh()
    if ($installedProcess.HasExited) { throw "Installed app exited unexpectedly: $($installedProcess.ExitCode)" }
    Write-Host 'PASS: silent installation and installed GUI process startup.'
} finally {
    if (-not $installedProcess.HasExited) {
        Stop-Process -Id $installedProcess.Id -Force -ErrorAction SilentlyContinue
    }
}

$checksum = (Get-FileHash -Algorithm SHA256 $installer).Hash.ToLowerInvariant()
$record = "$checksum  VibeCodeQAMaster-Setup.exe"
Set-Content -LiteralPath (Join-Path (Get-Location) 'release\SHA256SUMS.txt') -Value $record -Encoding ascii
Write-Host "SHA256: $checksum"

