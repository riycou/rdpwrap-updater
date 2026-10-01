param([string]$Ini = 'C:\Program Files\RDP Wrapper\rdpwrap.ini')
$ErrorActionPreference = 'Stop'
$stateDirectory = Join-Path $env:ProgramData 'RDPWrapUpdater'
New-Item -ItemType Directory -Path $stateDirectory -Force | Out-Null
$executable = Join-Path $PSScriptRoot 'RDPWrapUpdaterSilent.exe'
$logPath = Join-Path $stateDirectory 'shutdown-runs.jsonl'
$cachePath = Join-Path $stateDirectory 'recent-issues.json'
try {
    # The updater bounds network requests to 40 seconds. Wait for completion so
    # shutdown cannot terminate an INI write midway through the operation.
    & $executable --ini $Ini --auto --silent --recent 50 --cache $cachePath --log $logPath
    $runExitCode = $LASTEXITCODE
    if ($runExitCode -ne 0) { exit 0 } # Continue shutdown after a logged refusal.
} catch {
    @{time=(Get-Date).ToString('o'); status='shutdown_hook_error'; error=$_.Exception.Message} |
        ConvertTo-Json -Compress | Add-Content -LiteralPath $logPath
}
exit 0
