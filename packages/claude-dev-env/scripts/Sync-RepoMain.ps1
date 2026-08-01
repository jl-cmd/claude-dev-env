#Requires -Version 5.1
<#
.SYNOPSIS
  Fast-forward a local main checkout to origin/main when the tree is clean.

.DESCRIPTION
  Designed for the always-main mirror at:
    C:\dev\Projects\LLM Plugins\claude-code-config

  Remote origin for that path is:
    https://github.com/jl-cmd/claude-dev-env.git

  Safety rules:
  - Only runs when the checked-out branch is main
  - Only runs when there are no tracked changes (untracked files are fine),
    unless -StashDirty is passed
  - Uses merge --ff-only only (never force, never hard reset, never clean)
  - Logs and exits non-zero on skip, diverge, or failure so a Task Scheduler
    history row can surface a problem instead of a silent no-op

.PARAMETER RepoPath
  Absolute path to the git working tree.

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
    [string]$RepoPath = 'C:\dev\Projects\LLM Plugins\claude-code-config',
    [string]$Remote = 'origin',
    [string]$Branch = 'main',
    [switch]$StashDirty,
    [string]$LogPath = (Join-Path $HOME '.claude\logs\sync-repo-main.log')
)

$ErrorActionPreference = 'Stop'

$logPath = $LogPath
$logDirectory = Split-Path -Parent $logPath
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
    Add-Content -LiteralPath $logPath -Value $line -Encoding utf8
    Write-Host $line
}

function Get-GitExecutable {
    $command = Get-Command git -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }
    $candidates = @(
        'C:\Program Files\Git\cmd\git.exe',
        'C:\Program Files\Git\bin\git.exe'
    )
    foreach ($each_path in $candidates) {
        if (Test-Path -LiteralPath $each_path) {
            return $each_path
        }
    }
    throw 'git executable not found on PATH or under Program Files\Git'
}

function Invoke-Git {
    param(
        [Parameter(Mandatory)]
        [string]$GitPath,
        [Parameter(Mandatory)]
        [string[]]$Arguments
    )
    $output = & $GitPath -C $RepoPath @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    return [pscustomobject]@{
        ExitCode = $exitCode
        Output   = ($output | Out-String).Trim()
    }
}

try {
    if (-not (Test-Path -LiteralPath $RepoPath)) {
        Write-SyncLog -Level 'ERROR' -Message "repo path missing: $RepoPath"
        exit 2
    }

    $gitPath = Get-GitExecutable
    $remoteUrlResult = Invoke-Git -GitPath $gitPath -Arguments @('remote', 'get-url', $Remote)
    if ($remoteUrlResult.ExitCode -ne 0) {
        Write-SyncLog -Level 'ERROR' -Message "remote '$Remote' missing: $($remoteUrlResult.Output)"
        exit 2
    }
    $remoteUrl = $remoteUrlResult.Output

    $currentBranchResult = Invoke-Git -GitPath $gitPath -Arguments @('branch', '--show-current')
    if ($currentBranchResult.ExitCode -ne 0) {
        Write-SyncLog -Level 'ERROR' -Message "cannot read current branch: $($currentBranchResult.Output)"
        exit 2
    }
    $currentBranch = $currentBranchResult.Output
    if ($currentBranch -ne $Branch) {
        Write-SyncLog -Level 'SKIP' -Message "checkout is '$currentBranch', not '$Branch' (remote=$Remote url=$remoteUrl)"
        exit 3
    }

    $statusResult = Invoke-Git -GitPath $gitPath -Arguments @('status', '--porcelain')
    if ($statusResult.ExitCode -ne 0) {
        Write-SyncLog -Level 'ERROR' -Message "status failed: $($statusResult.Output)"
        exit 2
    }
    $trackedDirtyLines = @()
    if ($statusResult.Output) {
        foreach ($each_line in ($statusResult.Output -split "`r?`n")) {
            if ([string]::IsNullOrWhiteSpace($each_line)) {
                continue
            }
            if ($each_line.StartsWith('??')) {
                continue
            }
            $trackedDirtyLines += $each_line
        }
    }
    if ($trackedDirtyLines.Count -gt 0 -and -not $StashDirty) {
        Write-SyncLog -Level 'SKIP' -Message ("tracked changes present; refusing sync: " + ($trackedDirtyLines -join '; '))
        exit 3
    }

    $fetchResult = Invoke-Git -GitPath $gitPath -Arguments @('fetch', $Remote, $Branch)
    if ($fetchResult.ExitCode -ne 0) {
        Write-SyncLog -Level 'ERROR' -Message "fetch $Remote $Branch failed: $($fetchResult.Output)"
        exit 1
    }

    $localTipResult = Invoke-Git -GitPath $gitPath -Arguments @('rev-parse', $Branch)
    $remoteTipResult = Invoke-Git -GitPath $gitPath -Arguments @('rev-parse', "$Remote/$Branch")
    if ($localTipResult.ExitCode -ne 0 -or $remoteTipResult.ExitCode -ne 0) {
        Write-SyncLog -Level 'ERROR' -Message "rev-parse failed local=$($localTipResult.Output) remote=$($remoteTipResult.Output)"
        exit 2
    }
    $localTip = $localTipResult.Output
    $remoteTip = $remoteTipResult.Output

    if ($localTip -eq $remoteTip) {
        Write-SyncLog -Level 'OK' -Message "already up to date at $localTip ($Remote/$Branch $remoteUrl)"
        exit 0
    }

    $ancestorResult = Invoke-Git -GitPath $gitPath -Arguments @('merge-base', '--is-ancestor', $Branch, "$Remote/$Branch")
    if ($ancestorResult.ExitCode -ne 0) {
        $countResult = Invoke-Git -GitPath $gitPath -Arguments @('rev-list', '--left-right', '--count', "${Branch}...${Remote}/${Branch}")
        Write-SyncLog -Level 'ERROR' -Message "diverged from $Remote/$Branch (counts=$($countResult.Output)); fast-forward refused. local=$localTip remote=$remoteTip"
        exit 4
    }

    if ($trackedDirtyLines.Count -gt 0) {
        $stashMessage = 'pre-sync stash {0}: uncommitted other-stream edits before ff to {1}/{2}' -f (Get-Date -Format 'yyyy-MM-dd'), $Remote, $Branch
        $stashResult = Invoke-Git -GitPath $gitPath -Arguments @('stash', 'push', '-m', $stashMessage)
        if ($stashResult.ExitCode -ne 0) {
            Write-SyncLog -Level 'ERROR' -Message "stash push failed; fast-forward abandoned: $($stashResult.Output)"
            exit 1
        }
        Write-SyncLog -Level 'STASH' -Message ("stashed tracked changes as '" + $stashMessage + "' (left in stash list): " + ($trackedDirtyLines -join '; '))
    }

    $mergeResult = Invoke-Git -GitPath $gitPath -Arguments @('merge', '--ff-only', "$Remote/$Branch")
    if ($mergeResult.ExitCode -ne 0) {
        Write-SyncLog -Level 'ERROR' -Message "merge --ff-only failed: $($mergeResult.Output)"
        exit 1
    }

    $newTipResult = Invoke-Git -GitPath $gitPath -Arguments @('rev-parse', 'HEAD')
    $subjectResult = Invoke-Git -GitPath $gitPath -Arguments @('log', '--oneline', '-1')
    Write-SyncLog -Level 'OK' -Message "main $localTip -> $($newTipResult.Output) | $($subjectResult.Output) | $Remote/$Branch $remoteUrl"
    exit 0
}
catch {
    Write-SyncLog -Level 'ERROR' -Message $_.Exception.Message
    exit 1
}
