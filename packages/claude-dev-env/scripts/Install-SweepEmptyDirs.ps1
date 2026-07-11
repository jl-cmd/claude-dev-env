#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Install or remove the scheduled task that sweeps empty directories.

.DESCRIPTION
    Registers a scheduled task that runs sweep_empty_dirs.py --once every N minutes
    against a target directory.  Defaults: every 5 minutes, age threshold 120 seconds.

    Install-SweepEmptyDirs.ps1 -Target "C:\path\to\watch"
    Install-SweepEmptyDirs.ps1 -Target "C:\path\to\watch" -IntervalMinutes 10 -AgeSeconds 300  # custom
    Install-SweepEmptyDirs.ps1 -Remove
    Install-SweepEmptyDirs.ps1 -Status
#>

param(
    [Parameter(ParameterSetName = "install")]
    [string]$Target,

    [Parameter(ParameterSetName = "install")]
    [ValidateRange(1, [int]::MaxValue)]
    [int]$IntervalMinutes = 5,

    [Parameter(ParameterSetName = "install")]
    [ValidateRange(1, [int]::MaxValue)]
    [int]$AgeSeconds = 120,

    [Parameter(ParameterSetName = "install")]
    [DateTime]$StartAt = (Get-Date),

    [Parameter(ParameterSetName = "remove")]
    [switch]$Remove,

    [Parameter(ParameterSetName = "status")]
    [switch]$Status
)

$TaskName = "SweepEmptyDirs"

if ($Status) {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $task) {
        Write-Host "STATUS: $TaskName is not registered."
        return
    }
    Write-Host "STATUS: $TaskName is registered."
    Write-Host "  State: $($task.State)"
    Write-Host "  Actions:"
    foreach ($each_action in $task.Actions) {
        Write-Host "    $($each_action.Execute) $($each_action.Arguments)"
    }
    Write-Host "  Triggers:"
    foreach ($each_trigger in $task.Triggers) {
        Write-Host "    $($each_trigger.Repetition.Interval) (starting $($each_trigger.StartBoundary))"
    }
    return
}

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    if (-not $?) {
        Write-Warning "Failed to unregister scheduled task '$TaskName'."
    } else {
        Write-Host "$TaskName removed."
    }
    return
}

$ScriptDir = Split-Path -Parent $PSCommandPath
$ScriptPath = Join-Path $ScriptDir "sweep_empty_dirs.py"

if (-not (Test-Path $ScriptPath)) {
    Write-Error "sweep_empty_dirs.py not found at: $ScriptPath"
    exit 1
}

if (-not $Target) {
    Write-Error "Parameter -Target is required (the directory to watch)."
    exit 1
}

if (-not (Test-Path -PathType Container $Target)) {
    Write-Error "Target directory does not exist: $Target"
    exit 1
}

$_py = Get-Command py -ErrorAction SilentlyContinue
$PythonPath = if ($_py) { $_py.Source } else { (Get-Command python -ErrorAction SilentlyContinue).Source }
if (-not $PythonPath) {
    Write-Error "Cannot find Python (py or python) on PATH."
    exit 1
}
& $PythonPath --version 2>$null
if (-not $?) {
    Write-Error "Python found at $PythonPath but failed to run."
    exit 1
}

$Target = (Resolve-Path $Target).Path
$Target = [System.IO.Path]::TrimEndingDirectorySeparator($Target)

$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument """$ScriptPath"" --once --age $AgeSeconds ""$Target"""
$Trigger = New-ScheduledTaskTrigger -Once -At $StartAt -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) -RepetitionDuration (New-TimeSpan -Days 31)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

$null = Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Force
if (-not $?) {
    Write-Error "Failed to register scheduled task."
    exit 1
}
Write-Host "$TaskName registered — runs every ${IntervalMinutes}min against '$Target' (age > ${AgeSeconds}s)."
