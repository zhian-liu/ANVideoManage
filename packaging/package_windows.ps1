[CmdletBinding()]
param(
    [string]$OutputDirectory = "",
    [switch]$IncludeBackendVenv
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$frontendRoot = Join-Path $projectRoot "frontend"
$backendRoot = Join-Path $projectRoot "backend"
$zlmSource = Join-Path $backendRoot "ZLMediaKit\release\windows\Debug\Release"

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $projectRoot "release\VideoManage"
}

$outputPath = [System.IO.Path]::GetFullPath($OutputDirectory)
$releaseRoot = [System.IO.Path]::GetFullPath((Join-Path $projectRoot "release"))
$zipPath = "$outputPath.zip"
$releasePrefix = $releaseRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar

if (-not ($outputPath.Equals($releaseRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
        $outputPath.StartsWith($releasePrefix, [System.StringComparison]::OrdinalIgnoreCase))) {
    throw "OutputDirectory must stay under $releaseRoot"
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm was not found. Install Node.js before packaging."
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "python was not found. Install Python 3.11 or newer before packaging."
}

if (-not (Test-Path (Join-Path $zlmSource "MediaServer.exe"))) {
    throw "ZLMediaKit runtime not found at $zlmSource. Build or copy MediaServer.exe there first."
}

Write-Host "Building frontend..."
Push-Location $frontendRoot
try {
    $nodeModules = Join-Path $frontendRoot "node_modules"
    $typescriptBin = Join-Path $nodeModules ".bin\tsc.cmd"
    if (-not (Test-Path $nodeModules)) {
        npm ci
        if ($LASTEXITCODE -ne 0) {
            throw "npm ci failed with exit code $LASTEXITCODE"
        }
    } elseif (-not (Test-Path $typescriptBin)) {
        npm install --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) {
            throw "npm install failed with exit code $LASTEXITCODE"
        }
    }

    npm run build
    if ($LASTEXITCODE -ne 0) {
        throw "npm run build failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

$frontendDist = Join-Path $frontendRoot "dist"
if (-not (Test-Path (Join-Path $frontendDist "index.html"))) {
    throw "Frontend build did not produce frontend/dist/index.html"
}

Write-Host "Preparing package at $outputPath..."
if (Test-Path $outputPath) {
    Remove-Item -LiteralPath $outputPath -Recurse -Force
}
if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

$null = New-Item -ItemType Directory -Path $outputPath -Force
$null = New-Item -ItemType Directory -Path (Join-Path $outputPath "backend") -Force
$null = New-Item -ItemType Directory -Path (Join-Path $outputPath "frontend") -Force
$null = New-Item -ItemType Directory -Path (Join-Path $outputPath "zlm\www\record") -Force
$null = New-Item -ItemType Directory -Path (Join-Path $outputPath "zlm\www\hls") -Force
$null = New-Item -ItemType Directory -Path (Join-Path $outputPath "zlm\www\snap") -Force
$null = New-Item -ItemType Directory -Path (Join-Path $outputPath "logs") -Force

Copy-Item -LiteralPath (Join-Path $projectRoot "README.md") -Destination $outputPath
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "start_windows.bat") -Destination $outputPath
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "stop_windows.bat") -Destination $outputPath
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "PACKAGE_README.txt") -Destination $outputPath

Copy-Item -LiteralPath (Join-Path $backendRoot "app") -Destination (Join-Path $outputPath "backend") -Recurse
Copy-Item -LiteralPath (Join-Path $backendRoot "run.py") -Destination (Join-Path $outputPath "backend")
Copy-Item -LiteralPath (Join-Path $backendRoot "requirements.txt") -Destination (Join-Path $outputPath "backend")
Copy-Item -LiteralPath (Join-Path $backendRoot ".env.example") -Destination (Join-Path $outputPath "backend")
Get-ChildItem -LiteralPath (Join-Path $outputPath "backend") -Directory -Filter "__pycache__" -Recurse |
    Remove-Item -Recurse -Force
if ($IncludeBackendVenv -and (Test-Path (Join-Path $backendRoot "venv"))) {
    Copy-Item -LiteralPath (Join-Path $backendRoot "venv") -Destination (Join-Path $outputPath "backend") -Recurse
}

Copy-Item -LiteralPath $frontendDist -Destination (Join-Path $outputPath "frontend") -Recurse

Copy-Item -LiteralPath (Join-Path $zlmSource "MediaServer.exe") -Destination (Join-Path $outputPath "zlm")
Get-ChildItem -LiteralPath $zlmSource -Filter "*.dll" -File | Copy-Item -Destination (Join-Path $outputPath "zlm")
Copy-Item -LiteralPath (Join-Path $projectRoot "config\zlmediakit.config.ini") -Destination (Join-Path $outputPath "zlm\config.ini")

$runtimeFiles = Get-ChildItem -LiteralPath $outputPath -Recurse -File |
    Where-Object { $_.FullName -notmatch "\\(backend\\venv|zlm\\www)\\" }
$runtimeFiles | ForEach-Object { $_.IsReadOnly = $false }

Write-Host "Creating ZIP archive..."
Compress-Archive -Path (Join-Path $outputPath "*") -DestinationPath $zipPath -CompressionLevel Optimal

Write-Host "Package directory: $outputPath"
Write-Host "ZIP archive:       $zipPath"
