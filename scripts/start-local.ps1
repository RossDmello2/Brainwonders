$ErrorActionPreference = 'Stop'

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RunDirectory = Join-Path $ProjectRoot '.local-run'
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Project virtual environment is missing. Run: python -m venv .venv"
}

$Listeners = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -in 8000, 8080 }
if ($Listeners) {
    throw "Port 8000 or 8080 is already in use. Run scripts\stop-local.ps1 or inspect the listener."
}

New-Item -ItemType Directory -Force -Path $RunDirectory | Out-Null
$env:APP_ENV = 'development'
$env:ALLOWED_ORIGINS = 'http://127.0.0.1:8080'
$env:PYTHONPATH = Join-Path $ProjectRoot 'backend'

$Backend = Start-Process -FilePath $Python `
    -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000', '--no-access-log') `
    -WorkingDirectory (Join-Path $ProjectRoot 'backend') `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $RunDirectory 'backend.out.log') `
    -RedirectStandardError (Join-Path $RunDirectory 'backend.err.log') `
    -PassThru

$Frontend = Start-Process -FilePath $Python `
    -ArgumentList @('-m', 'http.server', '8080', '--bind', '127.0.0.1') `
    -WorkingDirectory (Join-Path $ProjectRoot 'frontend') `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $RunDirectory 'frontend.out.log') `
    -RedirectStandardError (Join-Path $RunDirectory 'frontend.err.log') `
    -PassThru

$Ready = $false
for ($Attempt = 0; $Attempt -lt 40; $Attempt++) {
    try {
        $Health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 1
        $Page = Invoke-WebRequest -Uri 'http://127.0.0.1:8080/' -TimeoutSec 1
        if ($Health.status -eq 'ok' -and $Page.StatusCode -eq 200) {
            $Ready = $true
            break
        }
    } catch {
        Start-Sleep -Milliseconds 250
    }
}

if (-not $Ready) {
    Stop-Process -Id $Backend.Id, $Frontend.Id -Force -ErrorAction SilentlyContinue
    throw "Local servers did not become ready. Inspect .local-run logs."
}

$BackendListener = Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort 8000 -State Listen
$FrontendListener = Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort 8080 -State Listen
$BackendProcess = Get-Process -Id $BackendListener.OwningProcess
$FrontendProcess = Get-Process -Id $FrontendListener.OwningProcess
$State = @{
    backendPid = $BackendProcess.Id
    backendStartedAt = $BackendProcess.StartTime.ToString('o')
    frontendPid = $FrontendProcess.Id
    frontendStartedAt = $FrontendProcess.StartTime.ToString('o')
    projectRoot = $ProjectRoot
}
$State | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $RunDirectory 'processes.json') -Encoding utf8

Write-Output 'APP_URL=http://127.0.0.1:8080/'
Write-Output 'API_HEALTH=http://127.0.0.1:8000/health'
Write-Output "BACKEND_PID=$($BackendProcess.Id)"
Write-Output "FRONTEND_PID=$($FrontendProcess.Id)"
