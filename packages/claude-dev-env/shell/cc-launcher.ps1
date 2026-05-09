<#
.SYNOPSIS
    Shell profile: Claude Code and GitHub CLI wrappers for interactive use.

.DESCRIPTION
    This file is dot-sourced by Documents\PowerShell\Microsoft.PowerShell_profile.ps1.

    Invoke-ClaudeCodeSession (alias: cc)
        Runs: claude --dangerously-skip-permissions [your arguments].
        If you pass -w or --worktree with no name, it scans .claude/worktrees and .worktrees
        under the current Git repo, shows a numbered menu (or prompts to create one), then
        cd into the chosen folder and starts Claude.

    Invoke-GitHubCliWithDraftPullRequestGuard (alias: gh)
        Runs the real gh.exe. Blocks "gh pr create" unless --draft is in the command line
        so new PRs are created as drafts by policy.

    Optional: loads Antigravity sandbox-guard when TERM_PROGRAM is vscode.
#>

# #region agent log
$logPath = "y:\Craft a Tale\Behavioral App\Project\debug-53b979.log"
$ts = [DateTimeOffset]::Now.ToUnixTimeMilliseconds()
$line = "{`"sessionId`":`"53b979`",`"id`":`"log_${ts}_ps`",`"timestamp`":$ts,`"location`":`"PowerShell_profile.ps1`",`"message`":`"PowerShell session started`",`"data`":{`"runId`":`"run1`",`"hypothesisId`":`"H1_ps_start`"}}"
Add-Content -LiteralPath $logPath -Value $line -ErrorAction SilentlyContinue
# #endregion agent log

$script:CcLauncherScriptRoot = $PSScriptRoot

function ClaudeShell_FindIndexOfWorktreeCliFlag {
    param([object[]]$CommandLineArguments)

    for ($i = 0; $i -lt $CommandLineArguments.Count; $i++) {
        $token = $CommandLineArguments[$i]
        if ($token -eq '-w' -or $token -eq '--worktree') {
            return $i
        }
    }
    return -1
}

function ClaudeShell_ReadArgumentAfterFlag {
    param(
        [object[]]$CommandLineArguments,
        [int]$FlagIndex
    )

    $argumentIndex = $FlagIndex + 1
    if ($argumentIndex -ge $CommandLineArguments.Count) {
        return $null
    }
    $possibleArgument = $CommandLineArguments[$argumentIndex]
    if ($possibleArgument -like '-*') {
        return $null
    }
    return $possibleArgument
}

function ClaudeShell_GetGitRepositoryRootFromCurrentDirectory {
    git rev-parse --show-toplevel 2>$null
}

function ClaudeShell_BuildWorktreeCatalogForRepository {
    param([string]$RepositoryRoot)

    $catalog = @()
    foreach ($relativeWorktreeRoot in @('.claude/worktrees', '.worktrees')) {
        $absoluteWorktreeRoot = Join-Path $RepositoryRoot $relativeWorktreeRoot
        if (-not (Test-Path $absoluteWorktreeRoot)) {
            continue
        }
        Get-ChildItem -Directory $absoluteWorktreeRoot | ForEach-Object {
            $branchName = git -C $_.FullName branch --show-current 2>$null
            if (-not $branchName) {
                $branchName = '(detached)'
            }
            $catalog += [PSCustomObject]@{
                Name   = $_.Name
                Branch = $branchName
                Path   = $_.FullName
                Source = $relativeWorktreeRoot
            }
        }
    }
    return $catalog
}

function ClaudeShell_StartClaudeSession {
    param([object[]]$CommandLineArguments)

    $allowedToolsForNativeMcpRouting = @(
        'mcp__zoekt__search',
        'mcp__zoekt__search_symbols',
        'mcp__zoekt__find_references',
        'mcp__zoekt__file_content',
        'mcp__zoekt__search_files',
        'mcp__obsidian__read_note',
        'mcp__obsidian__read_multiple_notes',
        'mcp__obsidian__search_notes',
        'mcp__obsidian__list_directory',
        'mcp__obsidian__get_frontmatter',
        'mcp__serena__read_file',
        'mcp__serena__find_symbol',
        'mcp__serena__find_referencing_symbols',
        'mcp__serena__get_symbols_overview',
        'mcp__serena__search_for_pattern',
        'mcp__serena__list_dir',
        'mcp__serena__find_file'
    )
    $allowedToolsArgument = $allowedToolsForNativeMcpRouting -join ' '
    claude --permission-mode auto --allowedTools $allowedToolsArgument @CommandLineArguments
}

function ClaudeShell_FindIndexOfDebugFileFlag {
    param([object[]]$CommandLineArguments)

    for ($i = 0; $i -lt $CommandLineArguments.Count; $i++) {
        if ($CommandLineArguments[$i] -eq '--debug-file') {
            return $i
        }
    }
    return -1
}

function ClaudeShell_ResolveOrCreateWorktreeInteractively {
    param([string]$RepositoryRoot)

    $catalog = ClaudeShell_BuildWorktreeCatalogForRepository -RepositoryRoot $RepositoryRoot

    if ($catalog.Count -eq 0) {
        Write-Host "No existing worktrees found." -ForegroundColor Yellow
        $newWorktreeName = Read-Host "Worktree name (or Enter to cancel)"
        if ($newWorktreeName) {
            ClaudeShell_StartClaudeSession -CommandLineArguments @('-w', $newWorktreeName)
        }
        return
    }

    Write-Host ""
    $repositoryFolderName = Split-Path $RepositoryRoot -Leaf
    Write-Host "Worktrees for ${repositoryFolderName}:" -ForegroundColor Cyan
    Write-Host ""
    for ($row = 0; $row -lt $catalog.Count; $row++) {
        $rowEntry = $catalog[$row]
        $menuNumber = $row + 1
        Write-Host "  [$menuNumber] $($rowEntry.Name)  ($($rowEntry.Branch))" -ForegroundColor White
    }
    Write-Host ""
    Write-Host "  [+] Create new worktree" -ForegroundColor Green
    Write-Host ""

    $menuChoice = Read-Host "Select"

    if ($menuChoice -eq '+') {
        $newWorktreeName = Read-Host "Worktree name"
        if ($newWorktreeName) {
            ClaudeShell_StartClaudeSession -CommandLineArguments @('-w', $newWorktreeName)
        }
        return
    }

    $chosenMenuNumber = 0
    $parsedMenuChoice = [int]::TryParse($menuChoice, [ref]$chosenMenuNumber)
    if (-not $parsedMenuChoice) {
        return
    }
    if ($chosenMenuNumber -lt 1 -or $chosenMenuNumber -gt $catalog.Count) {
        return
    }

    $selectedEntry = $catalog[$chosenMenuNumber - 1]
    Write-Host "Resuming: $($selectedEntry.Name) ($($selectedEntry.Branch))" -ForegroundColor Cyan
    Set-Location $selectedEntry.Path
    ClaudeShell_StartClaudeSession -CommandLineArguments @()
}

function Invoke-ClaudeCodeSession {
    $isDeepseek = $false
    $allArguments = $args
    if ($allArguments.Count -gt 0 -and $allArguments[0] -eq 'deepseek') {
        $isDeepseek = $true
        if ($allArguments.Count -gt 1) {
            $allArguments = $allArguments[1..($allArguments.Count - 1)]
        } else {
            $allArguments = @()
        }
    }

    $debugFilePath = $null
    $debugFileFlagIndex = ClaudeShell_FindIndexOfDebugFileFlag -CommandLineArguments $allArguments
    if ($debugFileFlagIndex -ne -1) {
        $explicitDebugFilePath = ClaudeShell_ReadArgumentAfterFlag -CommandLineArguments $allArguments -FlagIndex $debugFileFlagIndex
        if ($null -ne $explicitDebugFilePath) {
            $debugFilePath = $explicitDebugFilePath
            $argumentCountToRemove = 2
        } else {
            $debugFilePath = & (Join-Path $script:CcLauncherScriptRoot 'Get-DebugLogPath.ps1')
            $argumentCountToRemove = 1
        }

        $allCleanArguments = @()
        $removedCount = 0
        for ($i = 0; $i -lt $allArguments.Count; $i++) {
            if ($i -ge $debugFileFlagIndex -and $removedCount -lt $argumentCountToRemove) {
                $removedCount++
                continue
            }
            $allCleanArguments += $allArguments[$i]
        }
        $allArguments = $allCleanArguments

        if (-not $debugFilePath) {
            Write-Error "Cannot enable --debug-file: unable to determine a valid debug log path"
            return
        }
    }

    $previous_env_value_by_name = @{}
    $env_var_value_by_name = @{}
    $deepseekApiKey = $env:DEEPSEEK_API_KEY
    if ($isDeepseek) {
        if (-not $deepseekApiKey) {
            Write-Error "DEEPSEEK_API_KEY environment variable is not set. Set it in your PowerShell profile before using 'cc deepseek'."
            return
        }
        $env_var_value_by_name = @{
            'ANTHROPIC_BASE_URL' = "https://api.deepseek.com/anthropic"
            'ANTHROPIC_AUTH_TOKEN' = $deepseekApiKey
            'ANTHROPIC_MODEL' = "deepseek-v4-pro[1m]"
            'ANTHROPIC_DEFAULT_OPUS_MODEL' = "deepseek-v4-pro[1m]"
            'ANTHROPIC_DEFAULT_SONNET_MODEL' = "deepseek-v4-pro[1m]"
            'ANTHROPIC_DEFAULT_HAIKU_MODEL' = "deepseek-v4-flash"
            'CLAUDE_CODE_SUBAGENT_MODEL' = "deepseek-v4-flash"
            'CLAUDE_CODE_EFFORT_LEVEL' = "max"
        }
    }

    if ($debugFilePath) {
        $env_var_value_by_name['CLAUDE_CODE_DEBUG_FILE'] = $debugFilePath
    }

    try {
        foreach ($each_env_var_name in $env_var_value_by_name.Keys) {
            $previous_env_value_by_name[$each_env_var_name] = [System.Environment]::GetEnvironmentVariable($each_env_var_name, 'Process')
        }
        foreach ($each_env_var_name in $env_var_value_by_name.Keys) {
            Set-Item -Path "env:$each_env_var_name" -Value $env_var_value_by_name[$each_env_var_name]
        }

        $worktreeFlagIndex = ClaudeShell_FindIndexOfWorktreeCliFlag -CommandLineArguments $allArguments
        if ($worktreeFlagIndex -eq -1) {
            ClaudeShell_StartClaudeSession -CommandLineArguments $allArguments
            return
        }

        $worktreeNameAfterFlag = ClaudeShell_ReadArgumentAfterFlag -CommandLineArguments $allArguments -FlagIndex $worktreeFlagIndex
        if ($worktreeNameAfterFlag) {
            ClaudeShell_StartClaudeSession -CommandLineArguments $allArguments
            return
        }

        $repositoryRoot = ClaudeShell_GetGitRepositoryRootFromCurrentDirectory
        if (-not $repositoryRoot) {
            Write-Error "Not in a git repository"
            return
        }

        ClaudeShell_ResolveOrCreateWorktreeInteractively -RepositoryRoot $repositoryRoot
    } finally {
        foreach ($each_env_var_name in $previous_env_value_by_name.Keys) {
            if ($null -eq $previous_env_value_by_name[$each_env_var_name]) {
                if (Test-Path "env:$each_env_var_name") {
                    Remove-Item -Path "env:$each_env_var_name"
                }
            } else {
                Set-Item -Path "env:$each_env_var_name" -Value $previous_env_value_by_name[$each_env_var_name]
            }
        }
    }
}

Set-Alias -Name cc -Value Invoke-ClaudeCodeSession -Scope Global -Force

function Test-GitHubCliArgumentsAllowPullRequestCreate {
    param([string[]]$GitHubCliArguments)

    if ($GitHubCliArguments.Length -lt 2) {
        return $true
    }
    if ($GitHubCliArguments[0] -ne 'pr' -or $GitHubCliArguments[1] -ne 'create') {
        return $true
    }
    return ($GitHubCliArguments -contains '--draft')
}

function Invoke-GitHubCliWithDraftPullRequestGuard {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GitHubCliArguments)

    if (-not (Test-GitHubCliArgumentsAllowPullRequestCreate -GitHubCliArguments $GitHubCliArguments)) {
        Write-Error "Blocked: use --draft. Example: gh pr create --draft ..."
        return
    }

    $gitHubExecutablePath = (Get-Command gh.exe -ErrorAction Stop).Source
    & $gitHubExecutablePath @GitHubCliArguments
}

Set-Alias -Name gh -Value Invoke-GitHubCliWithDraftPullRequestGuard -Scope Global -Force
