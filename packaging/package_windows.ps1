[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$frontendRoot = Join-Path $projectRoot "frontend"
$backendRoot = Join-Path $projectRoot "backend"
$releaseRoot = Join-Path $projectRoot "release"
$stagingRoot = Join-Path $releaseRoot "installer-staging"
$pyDistRoot = Join-Path $releaseRoot "pyinstaller-dist"
$pyBuildRoot = Join-Path $releaseRoot "pyinstaller-build"
$setupPath = Join-Path $releaseRoot "VideoManageSetup.exe"
$zlmSource = Join-Path $backendRoot "ZLMediaKit\release\windows\Debug\Release"
$isccCandidates = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)

function Invoke-Checked([string]$FilePath, [string[]]$ArgumentList) {
    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "$FilePath failed with exit code $LASTEXITCODE"
    }
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm was not found. Install Node.js before packaging."
}
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "python was not found. Install Python 3.11 or newer before packaging."
}
if (-not (Test-Path (Join-Path $zlmSource "MediaServer.exe"))) {
    throw "ZLMediaKit runtime not found at $zlmSource."
}

$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    $isccCommand = Get-Command iscc -ErrorAction SilentlyContinue
    if ($isccCommand) { $iscc = $isccCommand.Source }
}
if (-not $iscc) {
    throw "Inno Setup compiler ISCC.exe was not found. Install Inno Setup 6 first."
}

$pythonExe = Join-Path $backendRoot "venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = Join-Path $backendRoot ".venv\Scripts\python.exe"
}
if (-not (Test-Path $pythonExe)) {
    Write-Host "Creating build virtual environment..."
    Invoke-Checked "py" @("-3.11", "-m", "venv", $pythonExe.Replace("\Scripts\python.exe", ""))
}

Write-Host "Building frontend..."
Push-Location $frontendRoot
try {
    if (-not (Test-Path (Join-Path $frontendRoot "node_modules\.bin\tsc.cmd"))) {
        Invoke-Checked "npm" @("ci")
    }
    Invoke-Checked "npm" @("run", "build")
}
finally {
    Pop-Location
}

Write-Host "Installing PyInstaller build dependency..."
Invoke-Checked $pythonExe @(
    "-m", "pip", "install", "-r",
    (Join-Path $PSScriptRoot "requirements-build.txt"),
    "--disable-pip-version-check"
)

Write-Host "Freezing backend executable..."
Invoke-Checked $pythonExe @(
    "-m", "PyInstaller",
    (Join-Path $PSScriptRoot "VideoManage.spec"),
    "--noconfirm",
    "--clean",
    "--distpath", $pyDistRoot,
    "--workpath", $pyBuildRoot
)

$frozenRoot = Join-Path $pyDistRoot "VideoManageBackend"
if (-not (Test-Path (Join-Path $frozenRoot "VideoManageBackend.exe"))) {
    throw "PyInstaller did not produce VideoManageBackend.exe"
}
if (-not (Test-Path (Join-Path $frontendRoot "dist\index.html"))) {
    throw "Frontend build did not produce frontend/dist/index.html"
}

Write-Host "Preparing installer staging directory..."
if (Test-Path $stagingRoot) { Remove-Item -LiteralPath $stagingRoot -Recurse -Force }
if (Test-Path $setupPath) { Remove-Item -LiteralPath $setupPath -Force }

$null = New-Item -ItemType Directory -Path $stagingRoot -Force
$null = New-Item -ItemType Directory -Path (Join-Path $stagingRoot "backend") -Force
$null = New-Item -ItemType Directory -Path (Join-Path $stagingRoot "frontend") -Force
$null = New-Item -ItemType Directory -Path (Join-Path $stagingRoot "zlm\www\record") -Force
$null = New-Item -ItemType Directory -Path (Join-Path $stagingRoot "zlm\www\hls") -Force
$null = New-Item -ItemType Directory -Path (Join-Path $stagingRoot "zlm\www\snap") -Force

Get-ChildItem -LiteralPath $frozenRoot -Force | Copy-Item -Destination (Join-Path $stagingRoot "backend") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $backendRoot ".env.example") -Destination (Join-Path $stagingRoot "backend")
Copy-Item -LiteralPath (Join-Path $frontendRoot "dist") -Destination (Join-Path $stagingRoot "frontend") -Recurse
Copy-Item -LiteralPath (Join-Path $zlmSource "MediaServer.exe") -Destination (Join-Path $stagingRoot "zlm")
Get-ChildItem -LiteralPath $zlmSource -Filter "*.dll" -File | Copy-Item -Destination (Join-Path $stagingRoot "zlm")
Copy-Item -LiteralPath (Join-Path $projectRoot "config\zlmediakit.config.ini") -Destination (Join-Path $stagingRoot "zlm\config.ini")
Copy-Item -LiteralPath (Join-Path $projectRoot "README.md") -Destination $stagingRoot
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "PACKAGE_README.txt") -Destination $stagingRoot
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "start_windows.bat") -Destination $stagingRoot
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "stop_windows.bat") -Destination $stagingRoot

Write-Host "Building Inno Setup installer..."
Invoke-Checked $iscc @("/Q", (Join-Path $PSScriptRoot "VideoManage.iss"))

Write-Host "Installer: $setupPath"
