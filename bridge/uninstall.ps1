# Removes the Mystic Light bridge task and firewall rule. Run elevated.
$taskName = 'Mystic Light Bridge'
Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
Get-NetFirewallRule -DisplayName $taskName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
Write-Host 'Removed.'
