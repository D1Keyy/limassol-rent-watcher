# Registers a Windows Task Scheduler task that runs the watcher every 15 minutes,
# without a console window, while you are logged in. No admin rights needed.
#   Install:  powershell -ExecutionPolicy Bypass -File install_task.ps1
#   Remove:   Unregister-ScheduledTask -TaskName LimassolRentWatcher -Confirm:$false

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$pythonw = Join-Path (Split-Path (Get-Command python).Source) 'pythonw.exe'
if (-not (Test-Path $pythonw)) { throw "pythonw.exe not found next to python.exe" }
if (-not (Test-Path (Join-Path $root '.env'))) {
    throw "No .env yet: run 'python -m watcher.setup_bot' first"
}

$action = New-ScheduledTaskAction -Execute $pythonw `
    -Argument '-m watcher.main --log-file logs\watch.log' -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 15)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName 'LimassolRentWatcher' -Action $action -Trigger $trigger `
    -Settings $settings -Description 'New Limassol rentals to Telegram every 15 min' -Force | Out-Null
Write-Host "Task 'LimassolRentWatcher' installed: every 15 minutes, log in $root\logs\watch.log"
