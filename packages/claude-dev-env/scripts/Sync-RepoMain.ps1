#Requires -Version 5.1
<#
.SYNOPSIS
  Fast-forward a local main-tracking mirror to its remote main.

.DESCRIPTION
  Runs against any working tree that is meant to stay on one branch and follow
  a remote, such as a read-only mirror kept current by a scheduled task.

  Safety rules:
  - Only runs when the checked-out branch is the named branch
  - Only runs when there are no tracked changes (untracked files are fine),
    unless -StashDirty is passed
  - Uses merge --ff-only only (never force, never hard reset, never clean)
  - Logs and exits non-zero on skip, diverge, or failure so a Task Scheduler
    history row can surface a problem instead of a silent no-op

  Exit codes: 0 success, 1 git operation failed, 2 configuration or repo
  problem, 3 skipped by a safety rule, 4 diverged from the remote.

.PARAMETER RepoPath
  Absolute path to the git working tree. Required.

.PARAMETER Remote
  Remote name whose main is the source of truth (default: origin).

.PARAMETER Branch
  Local branch that must be checked out (default: main).

.PARAMETER StashDirty
  Changes the tracked-changes branch from skip to stash. With the switch, a
  tree carrying tracked modifications is stashed with the message
  "pre-sync stash <yyyy-MM-dd>: uncommitted other-stream edits before ff to
  <remote>/<branch>" right before the fast-forward, and the stash is left in
  the stash list for a human to inspect. Untracked files are never stashed.
  The stash runs only when the fast-forward is going to happen, so an
  already-up-to-date or diverged run creates no stash entry.

.PARAMETER LogPath
  Absolute path to the run log (default: $HOME\.claude\logs\sync-repo-main.log).
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$RepoPath,
    [string]$Remote = 'origin',
    [string]$Branch = 'main',
    [switch]$StashDirty,
    [string]$LogPath = (Join-Path $HOME '.claude\logs\sync-repo-main.log')
)

$ErrorActionPreference = 'Stop'

$logDirectory = Split-Path -Parent $LogPath
if (-not (Test-Path -LiteralPath $logDirectory)) {
    New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
}

function Write-SyncLog {
    param(
        [Parameter(Mandatory)]
        [string]$Level,
        [Parameter(Mandatory)]
        [string]$Message
    )
    $line = '{0} [{1}] {2}' -f (Get-Date -Format 'o'), $Level, $Message
    Add-Content -LiteralPath $LogPath -Value $line -Encoding utf8
    Write-Host $line
}

function Get-GitExecutable {
    $command = Get-Command git -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        throw 'git executable not found on PATH'
    }
    return $command.Source
}

function Invoke-Git {
    param(
        [Parameter(Mandatory)]
        [string[]]$Arguments
    )
    $output = & $script:gitPath -C $RepoPath @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    return [pscustomobject]@{
        ExitCode = $exitCode
        Output   = ($output | Out-String).Trim()
    }
}

function Invoke-GitOrExit {
    param(
        [Parameter(Mandatory)]
        [string[]]$Arguments,
        [Parameter(Mandatory)]
        [string]$FailureMessage,
        [Parameter(Mandatory)]
        [int]$FailureExitCode
    )
    $result = Invoke-Git -Arguments $Arguments
    if ($result.ExitCode -ne 0) {
        Write-SyncLog -Level 'ERROR' -Message "${FailureMessage}: $($result.Output)"
        exit $FailureExitCode
    }
    return $result.Output
}

try {
    if (-not (Test-Path -LiteralPath $RepoPath)) {
        Write-SyncLog -Level 'ERROR' -Message "repo path missing: $RepoPath"
        exit 2
    }

    $script:gitPath = Get-GitExecutable

    $currentBranch = Invoke-GitOrExit -Arguments @('branch', '--show-current') `
        -FailureMessage 'cannot read current branch' -FailureExitCode 2
    if ($currentBranch -ne $Branch) {
        Write-SyncLog -Level 'SKIP' -Message "checkout is '$currentBranch', not '$Branch' (remote=$Remote)"
        exit 3
    }

    $statusOutput = Invoke-GitOrExit -Arguments @('status', '--porcelain') `
        -FailureMessage 'status failed' -FailureExitCode 2
    $trackedDirtyLines = @($statusOutput -split "`r?`n" | Where-Object { $_.Trim() -and -not $_.StartsWith('??') })
    if ($trackedDirtyLines.Count -gt 0 -and -not $StashDirty) {
        Write-SyncLog -Level 'SKIP' -Message ("tracked changes present; refusing sync: " + ($trackedDirtyLines -join '; '))
        exit 3
    }

    $null = Invoke-GitOrExit -Arguments @('fetch', $Remote, $Branch) `
        -FailureMessage "fetch $Remote $Branch failed" -FailureExitCode 1

    $tipOutput = Invoke-GitOrExit -Arguments @('rev-parse', $Branch, "$Remote/$Branch") `
        -FailureMessage 'rev-parse of branch tips failed' -FailureExitCode 2
    $tipLines = @($tipOutput -split "`r?`n" | Where-Object { $_.Trim() })
    if ($tipLines.Count -ne 2) {
        Write-SyncLog -Level 'ERROR' -Message "rev-parse returned $($tipLines.Count) tip(s), expected 2: $tipOutput"
        exit 2
    }
    $localTip = $tipLines[0].Trim()
    $remoteTip = $tipLines[1].Trim()

    if ($localTip -eq $remoteTip) {
        $remoteUrl = Invoke-GitOrExit -Arguments @('remote', 'get-url', $Remote) `
            -FailureMessage "remote '$Remote' missing" -FailureExitCode 2
        Write-SyncLog -Level 'OK' -Message "already up to date at $localTip ($Remote/$Branch $remoteUrl)"
        exit 0
    }

    $ancestorResult = Invoke-Git -Arguments @('merge-base', '--is-ancestor', $Branch, "$Remote/$Branch")
    if ($ancestorResult.ExitCode -ne 0) {
        $countResult = Invoke-Git -Arguments @('rev-list', '--left-right', '--count', "${Branch}...${Remote}/${Branch}")
        Write-SyncLog -Level 'ERROR' -Message "diverged from $Remote/$Branch (counts=$($countResult.Output)); fast-forward refused. local=$localTip remote=$remoteTip"
        exit 4
    }

    if ($trackedDirtyLines.Count -gt 0) {
        $stashMessage = 'pre-sync stash {0}: uncommitted other-stream edits before ff to {1}/{2}' -f (Get-Date -Format 'yyyy-MM-dd'), $Remote, $Branch
        $stashResult = Invoke-Git -Arguments @('stash', 'push', '-m', $stashMessage)
        if ($stashResult.ExitCode -ne 0) {
            Write-SyncLog -Level 'ERROR' -Message "stash push failed; fast-forward abandoned: $($stashResult.Output)"
            exit 1
        }
        Write-SyncLog -Level 'STASH' -Message ("stashed tracked changes as '" + $stashMessage + "' (left in stash list): " + ($trackedDirtyLines -join '; '))
    }

    $mergeResult = Invoke-Git -Arguments @('merge', '--ff-only', "$Remote/$Branch")
    if ($mergeResult.ExitCode -ne 0) {
        Write-SyncLog -Level 'ERROR' -Message "merge --ff-only failed: $($mergeResult.Output)"
        exit 1
    }

    $subject = Invoke-GitOrExit -Arguments @('log', '-1', '--format=%h %s') `
        -FailureMessage 'reading the new tip subject failed' -FailureExitCode 1
    $remoteUrl = Invoke-GitOrExit -Arguments @('remote', 'get-url', $Remote) `
        -FailureMessage "remote '$Remote' missing" -FailureExitCode 2
    Write-SyncLog -Level 'OK' -Message "$Branch $localTip -> $remoteTip | $subject | $Remote/$Branch $remoteUrl"
    exit 0
}
catch {
    Write-SyncLog -Level 'ERROR' -Message $_.Exception.Message
    exit 1
}
