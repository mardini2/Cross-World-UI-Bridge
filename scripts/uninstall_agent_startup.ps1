<#
Goal: Remove the per-user Scheduled Task that auto-starts the UIBridge agent.
Why: Let users easily undo auto-start behavior.
#>

$ErrorActionPreference = 'Stop'

$taskName = 'UIBridgeAgent'

# try to get the task (no error if missing)
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

if ($null -eq $task) {
  Write-Host "No scheduled task named '$taskName' found. Nothing to do."
  exit 0
}

# unregister without confirmation prompt
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false

Write-Host "Removed scheduled task '$taskName'."
