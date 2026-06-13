# ATLED_BK Watcher - Auto-start Registration
# Creates a Windows Task Scheduler task to run the watcher at logon

$watcherPath = "C:\Users\AIO Tech\Desktop\ATLEDBK\dist\ATLED_BK_Watcher\ATLED_BK_Watcher.exe"
$taskName = "ATLED_BK_Watcher"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ATLED_BK Watcher Auto-Start Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Remove existing task
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "[1/3] Removed existing task (if any)" -ForegroundColor Yellow

# Create action
$action = New-ScheduledTaskAction -Execute $watcherPath -WorkingDirectory "C:\Users\AIO Tech\Desktop\ATLEDBK\dist\ATLED_BK_Watcher"

# Create trigger - at logon
$trigger = New-ScheduledTaskTrigger -AtLogOn

# Create settings - run minimized, restart on failure
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -AllowHardTerminate:$true -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

# Create principal
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

# Register task
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "Monitors ATLED_BK.exe and sends OFFLINE notification when terminated" | Out-Null

Write-Host "[2/3] Task registered: $taskName" -ForegroundColor Green

# Start the task now
Start-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

Write-Host "[3/3] Task started" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Done! Watcher will auto-start on login." -ForegroundColor Green
Write-Host ""
Write-Host "How it works:" -ForegroundColor Yellow
Write-Host "  1. Watcher starts when you log in"
Write-Host "  2. When ATLED_BK.exe starts → sends ONLINE"
Write-Host "  3. When ATLED_BK.exe is killed/restarted → sends OFFLINE"
Write-Host "  4. When PC shuts down/restarts → Watcher also restarts → sends OFFLINE"
Write-Host ""
