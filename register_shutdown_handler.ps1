# ATLED_BK Shutdown Handler - Create Local Group Policy Shutdown Script
# Run as Administrator

$scriptContent = @"
@echo off
cd /d C:\Users\AIO Tech\Desktop\ATLEDBK\dist\ATLED_BK_Watcher
start /min ATLED_BK_Watcher.exe --offline-on-shutdown
exit
"@

# Create the script in system32 for shutdown scripts
$scriptPath = "C:\Windows\System32\GroupPolicy\Machine\Scripts\shutdown\atledbk_offline.bat"

# Create directory if not exists
$dir = Split-Path $scriptPath
if (-not (Test-Path $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}

# Write script
Set-Content -Path $scriptPath -Value $scriptContent -Encoding ASCII

# Also copy to a backup location
$backupPath = "C:\Users\AIO Tech\Desktop\ATLEDBK\shutdown.bat"
Set-Content -Path $backupPath -Value $scriptContent -Encoding ASCII

Write-Host "Shutdown script created at: $scriptPath" -ForegroundColor Green
Write-Host "Backup at: $backupPath" -ForegroundColor Green

# Register via schtasks with event trigger instead
$taskName = "ATLED_BK_Shutdown"

# Remove old task
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

# Create action - run the watcher with --offline flag
$action = New-ScheduledTaskAction -Execute "C:\Users\AIO Tech\Desktop\ATLEDBK\dist\ATLED_BK_Watcher\ATLED_BK_Watcher.exe" -Argument "--offline-on-shutdown"

# Create trigger - use daily at a time that won't trigger, but we'll manually call it
# Actually, let's use a different approach - monitor the process from the watcher itself
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 9999)

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable:$false -AllowHardTerminate:$false

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# Register as a hidden task
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "ATLED_BK Shutdown Handler" | Out-Null

# Start the task immediately
Start-ScheduledTask -TaskName $taskName

Write-Host ""
Write-Host "Task registered: $taskName" -ForegroundColor Green
Write-Host "The watcher will detect ATLED_BK.exe termination and send OFFLINE."
