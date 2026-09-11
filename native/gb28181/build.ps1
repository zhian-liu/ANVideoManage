[CmdletBinding()]
param([ValidateSet('Release', 'Debug')][string]$Configuration = 'Release')
$ErrorActionPreference = 'Stop'
$gbBuildRoot = Join-Path $PSScriptRoot 'build'
& cmake -S $PSScriptRoot -B $gbBuildRoot -G 'Visual Studio 17 2022' -A x64
if ($LASTEXITCODE -ne 0) { throw 'GB28181 CMake configuration failed.' }
& cmake --build $gbBuildRoot --config $Configuration --target gb28181-sip --parallel 4
if ($LASTEXITCODE -ne 0) { throw 'GB28181 build failed.' }
Write-Output (Join-Path $gbBuildRoot "bin/$Configuration/gb28181-sip.exe")
