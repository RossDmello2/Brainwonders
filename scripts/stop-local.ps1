$ErrorActionPreference = 'Stop'

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$StatePath = Join-Path $ProjectRoot '.local-run\processes.json'
if (-not (Test-Path -LiteralPath $StatePath)) {
    Write-Output 'No local server state file was found.'
    exit 0
}

$State = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
foreach ($Entry in @(
    @{ id = [int]$State.backendPid; started = [string]$State.backendStartedAt },
    @{ id = [int]$State.frontendPid; started = [string]$State.frontendStartedAt }
)) {
    $Process = Get-Process -Id $Entry.id -ErrorAction SilentlyContinue
    if ($Process -and $Process.StartTime.ToString('o') -eq $Entry.started) {
        Stop-Process -Id $Entry.id
    }
}
Remove-Item -LiteralPath $StatePath -Force
Write-Output 'Local Cloud Legal Stenographer servers stopped.'
