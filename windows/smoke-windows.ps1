$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))
$exe = Join-Path (Get-Location) 'dist\VibeQAMaster\VibeQAMaster.exe'
if (-not (Test-Path $exe)) { throw "Executable missing: $exe" }

# Exercise the bundled API, frontend assets and SQLite in a throwaway folder.
$check = Start-Process -FilePath $exe -ArgumentList '--self-check' -WindowStyle Hidden -Wait -PassThru
if ($check.ExitCode -ne 0) { throw "Packaged API self-check failed: $($check.ExitCode)" }

# A GUI launch is not an end-to-end functional test. It only proves that the
# packaged process opens on Windows without immediately exiting.
$process = Start-Process -FilePath $exe -WindowStyle Hidden -PassThru
try {
    Start-Sleep -Seconds 6
    $process.Refresh()
    if ($process.HasExited) { throw "Desktop launcher exited unexpectedly: $($process.ExitCode)" }
    Write-Host 'PASS: packaged API self-check and desktop launcher startup.'
} finally {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
}

