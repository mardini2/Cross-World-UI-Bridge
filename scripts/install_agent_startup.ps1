<#
Goal: Register a per-user Scheduled Task that launches the UIBridge agent (UIBridge.exe) at logon.
Why: So the CLI can connect immediately without the user manually starting the agent.
Notes:
- Runs as the CURRENT USER (no admin required).
- Looks for UIBridge.exe relative to this script location: ..\UIBridge\UIBridge.exe
- If a task with the same name exists, it is replaced.
#>

# stop on errors so failures are obvious
$ErrorActionPreference = 'Stop'

# resolve paths relative to this script file
$root  = Split-Path -Parent $MyInvocation.MyCommand.Path        # ...\scripts
$base  = Split-Path -Parent $root                                # project root / extracted zip root
$agent = Join-Path $base 'UIBridge\UIBridge.exe'                 # expected agent location

# verify the agent exists
if (-not (Test-Path -LiteralPath $agent)) {
  Write-Error "Agent not found: $agent`nMake sure this script sits next to the 'UIBridge' folder."
}

# task name shown in Task Scheduler
$taskName = 'UIBridgeAgent'

# build the task pieces
# action: run the agent exe
$action = New-ScheduledTaskAction -Execute $agent

# trigger: at user logon
$trigger = New-ScheduledTaskTrigger -AtLogOn

# principal: run as current user (domain\user)
# 'whoami' returns e.g. DESKTOP-ABC123\alice
$whoami = (whoami)
$principal = New-ScheduledTaskPrincipal -UserId $whoami -RunLevel LeastPrivilege -LogonType InteractiveToken

# settings: allow on battery, start hidden, allow to be replaced
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -Hidden

# compose the task definition
$task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Start UIBridge agent at user logon'

# register (create/replace) the task
Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null

Write-Host "Installed scheduled task '$taskName'."
Write-Host "It will start the agent on your next sign-in."
Write-Host "Tip: You can also start it now via 'Start UIBridge Agent.cmd'."
