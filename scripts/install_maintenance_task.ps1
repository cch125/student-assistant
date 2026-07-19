param(
    [string]$TaskName = "JNU Student Assistant Weekly Refresh",
    [string]$StartTime = "03:00"
)

$project = Split-Path -Parent $PSScriptRoot
$python = (Get-Command python).Source
$script = Join-Path $project "scripts\update_pipeline.py"
$action = New-ScheduledTaskAction -Execute $python -Argument "`"$script`" --max-pages 200 --depth 1 --max-pages-per-seed 12 --sync-ragflow" -WorkingDirectory $project
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At $StartTime
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "Refreshes public JNU student-service data and synchronizes RAGFlow." -Force
Write-Host "Installed scheduled task: $TaskName"
