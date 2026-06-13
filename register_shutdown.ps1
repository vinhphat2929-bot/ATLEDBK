# ATLED_BK Shutdown Event Registration Script
# Run as Administrator to register Windows shutdown event handler

param(
    [string]$AppPath = "C:\Users\AIO Tech\Desktop\ATLEDBK\dist\ATLED_BK.exe"
)

$script:appPath = $AppPath

# Register for Windows shutdown event (Event ID 1074)
$query = New-Object System.Management.EventQuery
$query.QueryString = "SELECT * FROM Win32_ProcessStopTrace WHERE ProcessName = 'ATLED_BK.exe'"

$shdown = Register-WmiEvent -Query $query -SourceIdentifier "ATLED_BKShutdown" -Action {
    Write-Host "[SHUTDOWN_EVENT] App terminated, sending OFFLINE..." -ForegroundColor Yellow
    & $script:appPath --offline-on-shutdown
}

Write-Host "[OK] Shutdown event handler registered for: $AppPath" -ForegroundColor Green
Write-Host "The app will send OFFLINE notification when terminated."
