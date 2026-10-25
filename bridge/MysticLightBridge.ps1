# Supervisor for the Mystic Light bridge. Must run elevated (the MSI SDK requires admin).
# MSI's SDK can crash the process outright (seen: heap corruption after days of polling),
# which nothing inside the process can catch, so the bridge runs as a child and is
# restarted whenever it exits.
$here = $PSScriptRoot
$log = Join-Path $here 'bridge.log'
$worker = Join-Path $here 'bridge-worker.ps1'

while ($true) {
    $started = Get-Date
    $proc = Start-Process powershell.exe -PassThru -Wait -WindowStyle Hidden `
        -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$worker`""
    $code = '0x{0:X8}' -f $proc.ExitCode
    Add-Content $log "$((Get-Date).ToString('s')) Bridge exited with $code after $([int]((Get-Date) - $started).TotalMinutes) min; restarting"
    # Back off if it is dying immediately (e.g. MSI Center not up yet after logon).
    if (((Get-Date) - $started).TotalSeconds -lt 30) { Start-Sleep 30 } else { Start-Sleep 3 }
}
