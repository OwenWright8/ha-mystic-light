# Installs the Mystic Light bridge: a logon task (elevated) plus a LAN-only firewall rule.
# Run from an elevated PowerShell:  powershell -ExecutionPolicy Bypass -File C:\Users\owenw\MysticLightBridge\install.ps1
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script from an elevated (Administrator) PowerShell.'
}
$dll = Join-Path $here 'MysticLight_SDK_x64.dll'
if (-not (Test-Path $dll)) {
    Write-Host 'Downloading MSI Mystic Light SDK...'
    $tmp = Join-Path $env:TEMP "mlsdk_$(Get-Random)"
    New-Item -ItemType Directory $tmp | Out-Null
    Invoke-WebRequest 'https://download.msi.com/uti_exe/Mystic_light_SDK.zip' -OutFile "$tmp\sdk.zip" -UseBasicParsing
    Expand-Archive "$tmp\sdk.zip" "$tmp\x"
    $found = Get-ChildItem "$tmp\x" -Recurse -Filter 'MysticLight_SDK_x64.dll' | Select-Object -First 1
    $sig = Get-AuthenticodeSignature $found.FullName
    if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'MICRO-STAR') { throw 'SDK DLL signature check failed.' }
    Copy-Item $found.FullName $dll
    Remove-Item $tmp -Recurse -Force
}
$configPath = Join-Path $here 'config.json'
if (-not (Test-Path $configPath)) {
    $token = -join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Maximum 256) })
    [IO.File]::WriteAllText($configPath, (@{ port = 8765; token = $token } | ConvertTo-Json))
    Write-Host "Created $configPath with a new token."
}
$config = Get-Content $configPath -Raw | ConvertFrom-Json
$taskName = 'Mystic Light Bridge'

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$here\MysticLightBridge.ps1`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
$taskPrincipal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
    -Principal $taskPrincipal -Force | Out-Null

Get-NetFirewallRule -DisplayName $taskName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName $taskName -Direction Inbound -Action Allow -Protocol TCP `
    -LocalPort $config.port -RemoteAddress LocalSubnet -Profile Any | Out-Null

Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
Start-ScheduledTask -TaskName $taskName
Write-Host "Installed. Bridge listening on port $($config.port); log: $here\bridge.log"
