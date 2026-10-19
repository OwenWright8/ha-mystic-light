# Runs the Mystic Light HTTP bridge. Must run elevated (the MSI SDK requires admin).
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$config = Get-Content (Join-Path $here 'config.json') -Raw | ConvertFrom-Json
$log = Join-Path $here 'bridge.log'
if ((Test-Path $log) -and (Get-Item $log).Length -gt 1MB) { Move-Item $log "$log.old" -Force }

$source = (Get-Content (Join-Path $here 'Bridge.cs') -Raw).Replace('__DLL__', (Join-Path $here 'MysticLight_SDK_x64.dll'))
Add-Type -TypeDefinition $source -ReferencedAssemblies System.Web.Extensions
[Bridge]::Run([int]$config.port, [string]$config.token, $log)
