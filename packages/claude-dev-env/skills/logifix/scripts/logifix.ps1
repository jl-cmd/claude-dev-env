<#
.SYNOPSIS
Restores the Logitech Gaming Software (LCore) tray icon when it is missing on Windows.

.DESCRIPTION
Reproduces the verified recovery procedure from
sessions/System Support/2. Logitech Tray Icon Fix Recurrence.md (2026-04-25):
  1. Stops LCore in user context.
  2. Single elevated UAC step:
       - Starts LogiRegistryService (handles the case where it is Stopped).
       - Stops explorer.exe and lets Windows shell auto-respawn rebuild it.
     Deliberately omits Start-Process explorer from the elevated block to
     avoid the duplicate admin-context explorer that blocked tray registration
     during Session 2.
  3. Waits for shell auto-respawn.
  4. Verifies a single user-session explorer.
  5. Performs LCoreRelaunchAttemptCount full stop-then-launch cycles of
     LCore /minimized. Always runs the full count: a responsive LCore on the
     first attempt does NOT imply Shell_NotifyIcon registered, per Session 2
     gotcha #2 (responsive process, no tray icon).

.PARAMETER ExplorerAutoRespawnWaitSeconds
Seconds to wait after the elevated explorer kill before verifying respawn.

.PARAMETER LCoreInitializationWaitSeconds
Seconds to wait after each LCore relaunch before checking responsiveness.

.PARAMETER LCoreRelaunchAttemptCount
Total number of LCore relaunch cycles to perform (default 2). The full count
always runs, because the documented failure mode is a responsive LCore that
never registered a tray icon -- only a second stop+launch reliably triggers
Shell_NotifyIcon registration.
#>

[CmdletBinding()]
param(
    [int] $ExplorerAutoRespawnWaitSeconds = 5,
    [int] $LCoreInitializationWaitSeconds = 5,
    [int] $LCoreRelaunchAttemptCount = 2
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:LCoreExecutablePath = 'C:\Program Files\Logitech Gaming Software\LCore.exe'
$script:LCoreProcessName = 'LCore'

function Get-CurrentInteractiveSessionId {
    [OutputType([int])]
    param()
    return (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").SessionId
}

function Get-ExplorerProcessesInSession {
    [OutputType([object[]])]
    param([Parameter(Mandatory)] [int] $TargetSessionId)
    $allExplorers = Get-CimInstance Win32_Process -Filter "Name='explorer.exe'"
    $matchingExplorers = @()
    foreach ($eachExplorer in $allExplorers) {
        if ($eachExplorer.SessionId -ne $TargetSessionId) { continue }
        $ownerInfo = Invoke-CimMethod -InputObject $eachExplorer -MethodName GetOwner -ErrorAction SilentlyContinue
        $matchingExplorers += [PSCustomObject]@{
            ProcessId    = $eachExplorer.ProcessId
            SessionId    = $eachExplorer.SessionId
            OwnerUser    = if ($ownerInfo) { $ownerInfo.User } else { $null }
            CreationDate = $eachExplorer.CreationDate
        }
    }
    return ,$matchingExplorers
}

function Stop-LCoreIfRunning {
    [OutputType([void])]
    param()
    $stopSettleMilliseconds = 500
    Stop-Process -Name $script:LCoreProcessName -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds $stopSettleMilliseconds
}

function Invoke-ElevatedExplorerRebuild {
    [OutputType([bool])]
    param()
    $elevatedScriptBlockText = @'
Start-Service -Name LogiRegistryService -ErrorAction SilentlyContinue
Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue
'@
    $encodedElevatedCommand = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($elevatedScriptBlockText))
    try {
        Start-Process -FilePath 'pwsh' `
            -ArgumentList '-NoProfile', '-EncodedCommand', $encodedElevatedCommand `
            -Verb RunAs `
            -Wait `
            -ErrorAction Stop
        return $true
    } catch {
        Write-Warning "Elevated step did not run: $($_.Exception.Message)"
        return $false
    }
}

function Start-LCoreMinimized {
    [OutputType([void])]
    param()
    $launchArguments = '/minimized'
    Start-Process -FilePath $script:LCoreExecutablePath -ArgumentList $launchArguments
}

function Test-LCoreIsResponding {
    [OutputType([bool])]
    param([Parameter(Mandatory)] [int] $WaitSeconds)
    Start-Sleep -Seconds $WaitSeconds
    $lcoreProcesses = Get-Process -Name $script:LCoreProcessName -ErrorAction SilentlyContinue
    if (-not $lcoreProcesses) { return $false }
    foreach ($eachLCore in @($lcoreProcesses)) {
        if (-not $eachLCore.Responding) { return $false }
    }
    return $true
}

function Write-StateSnapshot {
    [OutputType([void])]
    param([Parameter(Mandatory)] [string] $Label)
    $logitechServiceNamesToVerify = @('LogiRegistryService', 'logi_lamparray_service')
    Write-Host ""
    Write-Host "=== $Label ==="
    $sessionId = Get-CurrentInteractiveSessionId
    $explorersInSession = Get-ExplorerProcessesInSession -TargetSessionId $sessionId
    Write-Host "Explorer instances in session ${sessionId}: $($explorersInSession.Count)"
    if ($explorersInSession.Count -gt 0) {
        $explorersInSession | Format-Table ProcessId, OwnerUser, CreationDate -AutoSize | Out-String | Write-Host
    }
    $servicesObserved = Get-Service -Name $logitechServiceNamesToVerify -ErrorAction SilentlyContinue
    if ($servicesObserved) {
        $servicesObserved | Format-Table Name, Status -AutoSize | Out-String | Write-Host
    }
    $lcoreProcessesObserved = Get-Process -Name $script:LCoreProcessName -ErrorAction SilentlyContinue
    if ($lcoreProcessesObserved) {
        $lcoreProcessesObserved | Select-Object Id, Responding | Format-Table -AutoSize | Out-String | Write-Host
    } else {
        Write-Host "LCore not running."
    }
}

function Invoke-LogifixRecovery {
    [OutputType([void])]
    param()

    Write-StateSnapshot -Label 'Before'

    if (-not (Test-Path -Path $script:LCoreExecutablePath)) {
        Write-Error "LCore.exe not found at expected path: $script:LCoreExecutablePath"
        return
    }

    Stop-LCoreIfRunning

    $elevatedSucceeded = Invoke-ElevatedExplorerRebuild
    if (-not $elevatedSucceeded) {
        Write-Warning "UAC was canceled or the elevated step failed."
        Write-Warning "Fallback: open Task Manager (Ctrl+Shift+Esc), find 'Windows Explorer', right-click, Restart. Then re-run /logifix."
        return
    }

    Start-Sleep -Seconds $ExplorerAutoRespawnWaitSeconds

    $sessionId = Get-CurrentInteractiveSessionId
    $explorersAfterRespawn = Get-ExplorerProcessesInSession -TargetSessionId $sessionId
    $explorerCountAfterRespawn = @($explorersAfterRespawn).Count
    if ($explorerCountAfterRespawn -ne 1) {
        if ($explorerCountAfterRespawn -eq 0) {
            Write-Warning "No explorer.exe found in session $sessionId after $ExplorerAutoRespawnWaitSeconds-second wait."
        } else {
            Write-Warning "Expected exactly 1 explorer.exe in session $sessionId after shell auto-respawn, but found $explorerCountAfterRespawn."
            Write-Warning "Multiple explorer.exe processes in the same session reproduce the Session 2 duplicate-explorer failure mode that blocks tray icon registration."
            $explorersAfterRespawn | Format-Table ProcessId, OwnerUser, CreationDate -AutoSize | Out-String | Write-Host
        }
        Write-Warning "Restart Explorer manually via Task Manager (Ctrl+Shift+Esc, Windows Explorer, Restart), then re-run /logifix."
        return
    }

    $lastAttemptResponded = $false
    for ($attemptIndex = 1; $attemptIndex -le $LCoreRelaunchAttemptCount; $attemptIndex++) {
        Stop-LCoreIfRunning
        Start-LCoreMinimized
        $lastAttemptResponded = Test-LCoreIsResponding -WaitSeconds $LCoreInitializationWaitSeconds
        if ($lastAttemptResponded) {
            Write-Host "LCore relaunch attempt ${attemptIndex}: process is responding."
        } else {
            Write-Warning "LCore relaunch attempt ${attemptIndex}: process not responding."
        }
    }

    Write-StateSnapshot -Label 'After'

    if (-not $lastAttemptResponded) {
        Write-Warning "LCore did not respond after $LCoreRelaunchAttemptCount attempts."
        Write-Warning "Use Task Manager to Restart Windows Explorer, then re-run /logifix."
        return
    }

    Write-Host ""
    Write-Host "Recovery complete ($LCoreRelaunchAttemptCount stop+launch cycles performed). If the tray icon is still not visible, use Task Manager to Restart Windows Explorer (guaranteed correct session/elevation), then re-run /logifix."
}

Invoke-LogifixRecovery
