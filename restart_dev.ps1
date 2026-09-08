[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path $PSScriptRoot).Path
$backendRoot = Join-Path $projectRoot "backend"
$frontendRoot = Join-Path $projectRoot "frontend"
$logsRoot = Join-Path $projectRoot "logs"

function Get-ListenerIds([int]$Port) {
    @(
        Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
    )
}

function Stop-ProjectListeners([int]$Port, [string[]]$Markers) {
    foreach ($processId in @(Get-ListenerIds $Port)) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId"
        $commandLine = [string]$process.CommandLine
        $isProjectProcess = $false
        foreach ($marker in $Markers) {
            if ($commandLine -like "*$marker*") {
                $isProjectProcess = $true
                break
            }
        }

        if (-not $isProjectProcess) {
            throw "Port $Port is already used by another process (PID $processId). Stop it or choose another port before running this script."
        }

        Write-Host "Stopping project process $processId on port $Port..."
        Stop-Process -Id $processId -Force
    }
}

function Wait-PortFree([int]$Port) {
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        if (-not (Get-ListenerIds $Port)) {
            return
        }
        Start-Sleep -Milliseconds 250
    }
    throw "Port $Port did not become available after stopping the old process."
}

function Wait-Http([string]$Url, [string]$Name) {
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
            if ([int]$response.StatusCode -ge 200 -and [int]$response.StatusCode -lt 400) {
                return
            }
        }
        catch {
            # The service may still be starting.
        }
        Start-Sleep -Milliseconds 500
    }
    throw "$Name did not become ready at $Url. Check the logs under $logsRoot."
}

$pythonCandidates = @(
    (Join-Path $backendRoot "venv\Scripts\python.exe"),
    (Join-Path $backendRoot ".venv\Scripts\python.exe")
)
$pythonExe = $pythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $pythonExe) {
    throw "Backend virtual environment was not found. Create backend\venv first and install requirements.txt."
}

$npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npmCommand) {
    $npmCommand = Get-Command npm -ErrorAction SilentlyContinue
}
if (-not $npmCommand) {
    throw "npm was not found. Install Node.js before starting the frontend."
}
if (-not (Test-Path (Join-Path $frontendRoot "node_modules"))) {
    throw "frontend\node_modules was not found. Run npm ci in the frontend directory first."
}

New-Item -ItemType Directory -Path $logsRoot -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backendOut = Join-Path $logsRoot "backend-$stamp.out.log"
$backendErr = Join-Path $logsRoot "backend-$stamp.err.log"
$frontendOut = Join-Path $logsRoot "frontend-$stamp.out.log"
$frontendErr = Join-Path $logsRoot "frontend-$stamp.err.log"

Stop-ProjectListeners 8000 @("$backendRoot", "uvicorn", "app.main:app")
Stop-ProjectListeners 5173 @("$frontendRoot", "vite")
Wait-PortFree 8000
Wait-PortFree 5173

Write-Host "Starting backend..."
$backendProcess = Start-Process `
    -FilePath $pythonExe `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $backendRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $backendOut `
    -RedirectStandardError $backendErr `
    -PassThru

Write-Host "Starting frontend..."
$frontendProcess = Start-Process `
    -FilePath $npmCommand.Source `
    -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "5173") `
    -WorkingDirectory $frontendRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $frontendOut `
    -RedirectStandardError $frontendErr `
    -PassThru

try {
    Wait-Http "http://127.0.0.1:8000/api/health" "Backend"
    Wait-Http "http://127.0.0.1:5173/" "Frontend"
}
catch {
    Write-Host "Backend output: $backendOut"
    Write-Host "Backend errors: $backendErr"
    Write-Host "Frontend output: $frontendOut"
    Write-Host "Frontend errors: $frontendErr"
    throw
}

Write-Host "Backend started (PID $($backendProcess.Id)): http://127.0.0.1:8000"
Write-Host "Frontend started (PID $($frontendProcess.Id)): http://127.0.0.1:5173"
Write-Host "ZLMediaKit is not restarted by this script."
Write-Host "Logs: $logsRoot"
