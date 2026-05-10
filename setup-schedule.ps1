# Windows Scheduled Task Setup Script (PowerShell)
# Run as administrator to create a daily task at 7:00 AM

param(
    [string]$ProjectPath = $PSScriptRoot,
    [string]$TaskName = "WeChatDailyBrief",
    [string]$TaskTime = "07:00"
)

# Get Python path
$PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonPath) {
    Write-Host "ERROR: Python not found. Please install Python and add to PATH." -ForegroundColor Red
    exit 1
}

# Build script paths
$SchedulerScript = Join-Path $ProjectPath "scheduler.py"
$ConfigFile = Join-Path $ProjectPath "config.yaml"

# Check files exist
if (-not (Test-Path $SchedulerScript)) {
    Write-Host "ERROR: scheduler.py not found: $SchedulerScript" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $ConfigFile)) {
    Write-Host "WARNING: config.yaml not found: $ConfigFile" -ForegroundColor Yellow
}

# Create task action
$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$SchedulerScript`" --config `"$ConfigFile`"" `
    -WorkingDirectory $ProjectPath

# Create trigger (daily at 7:00 AM)
$Trigger = New-ScheduledTaskTrigger -Daily -At $TaskTime

# Create task settings
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

# Create task principal
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

# Register scheduled task
try {
    # Remove existing task first
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    
    # Register new task
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -Description "WeChat Daily Brief - Auto generate daily report at $TaskTime"
    
    Write-Host "SUCCESS: Scheduled task created!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Task Name: $TaskName"
    Write-Host "Run Time: Daily at $TaskTime"
    Write-Host "Project Path: $ProjectPath"
    Write-Host "Python: $PythonPath"
    Write-Host ""
    Write-Host "Tips:" -ForegroundColor Cyan
    Write-Host "   - Open Task Scheduler to view/manage this task"
    Write-Host "   - Run 'Get-ScheduledTask -TaskName $TaskName' for details"
    Write-Host "   - Run 'Unregister-ScheduledTask -TaskName $TaskName' to remove"
    
} catch {
    Write-Host "ERROR: Failed to create scheduled task: $_" -ForegroundColor Red
    Write-Host "TIP: Please run this script as administrator" -ForegroundColor Yellow
    exit 1
}
