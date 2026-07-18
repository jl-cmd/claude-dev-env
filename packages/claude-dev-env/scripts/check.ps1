#!/usr/bin/env pwsh
<#
.SYNOPSIS
    One-shot quality gate — runs ruff, hooks mypy, pr-loop mypy, and the
    blocking pytest suite from a single entry point.

.DESCRIPTION
    Resolves paths relative to $PSScriptRoot so the script works from any CWD
    and from both the worktree (packages/claude-dev-env/scripts/check.ps1)
    and the installed runtime (~/.claude/scripts/check.ps1, after install.mjs
    propagates this file). Tools: ruff over hooks/, mypy over hooks blocking
    and validators, mypy-pr-loop over _shared/pr-loop/scripts production
    modules, and optional pytest over the blocking enforcer suite. Each tool
    runs sequentially; the first non-zero exit code is preserved as the
    script's exit code so CI/pre-commit can short-circuit on the first failure.

.PARAMETER SkipTests
    Skip the pytest run. Useful during local iteration when you want only the
    static-analysis gates.

.PARAMETER SkipMypy
    Skip both mypy runs (hooks mypy and mypy-pr-loop).

.PARAMETER SkipRuff
    Skip the ruff run.

.OUTPUTS
    Per-tool status lines on stdout. Final summary line:
        CHECK: OK
        CHECK: FAILED tools=ruff,mypy,mypy-pr-loop,pytest
#>
[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$SkipMypy,
    [switch]$SkipRuff
)

$ErrorActionPreference = 'Stop'

$hooksRoot = Resolve-Path (Join-Path $PSScriptRoot '..' 'hooks')
$blockingRoot = Join-Path $hooksRoot 'blocking'
$prLoopScriptsRoot = Resolve-Path (Join-Path $PSScriptRoot '..' '_shared' 'pr-loop' 'scripts')

$failedTools = @()
$firstNonZeroExitCode = 0

function Invoke-Tool {
    param(
        [string]$Label,
        [scriptblock]$Action
    )
    Write-Host ""
    Write-Host "==> $Label" -ForegroundColor Cyan
    & $Action
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        $script:failedTools += $Label
        if ($script:firstNonZeroExitCode -eq 0) {
            $script:firstNonZeroExitCode = $exitCode
        }
        Write-Host "$Label FAILED (exit $exitCode)" -ForegroundColor Red
    } else {
        Write-Host "$Label OK" -ForegroundColor Green
    }
}

if (-not $SkipRuff) {
    Invoke-Tool -Label 'ruff' -Action {
        Push-Location $hooksRoot
        try {
            ruff check .
        } finally {
            Pop-Location
        }
    }
}

if (-not $SkipMypy) {
    Invoke-Tool -Label 'mypy' -Action {
        Push-Location $hooksRoot
        try {
            mypy --config-file (Join-Path $hooksRoot 'pyproject.toml') blocking validators
        } finally {
            Pop-Location
        }
    }

    Invoke-Tool -Label 'mypy-pr-loop' -Action {
        Push-Location $prLoopScriptsRoot
        try {
            mypy --config-file (Join-Path $prLoopScriptsRoot 'pyproject.toml') `
                _claude_permissions_common.py `
                code_rules_gate.py `
                copilot_quota.py `
                fix_hookspath.py `
                grant_project_claude_permissions.py `
                post_audit_thread.py `
                preflight_self_heal.py `
                preflight.py `
                reviewer_availability.py `
                reviews_disabled.py `
                revoke_project_claude_permissions.py `
                terminology_sweep.py `
                code_rules_gate_parts `
                pr_loop_shared_constants
        } finally {
            Pop-Location
        }
    }
}

if (-not $SkipTests) {
    Invoke-Tool -Label 'pytest' -Action {
        Push-Location $blockingRoot
        try {
            python -m pytest (Get-ChildItem test_code_rules_enforcer*.py)
        } finally {
            Pop-Location
        }
    }
}

Write-Host ""
if ($failedTools.Count -eq 0) {
    Write-Host "CHECK: OK" -ForegroundColor Green
    exit 0
} else {
    $joined = ($failedTools -join ',')
    Write-Host "CHECK: FAILED tools=$joined" -ForegroundColor Red
    exit $firstNonZeroExitCode
}
