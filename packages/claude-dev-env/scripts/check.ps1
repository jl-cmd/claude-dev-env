#!/usr/bin/env pwsh
<#
.SYNOPSIS
    One-shot quality gate for the hooks package — runs ruff, mypy, and the
    blocking pytest suite from a single entry point.

.DESCRIPTION
    Resolves paths relative to $PSScriptRoot so the script works from any CWD
    and from both the worktree (packages/claude-dev-env/scripts/check.ps1)
    and the installed runtime (~/.claude/scripts/check.ps1, after install.mjs
    propagates this file). Each tool runs sequentially; the first non-zero
    exit code is preserved as the script's exit code so CI/pre-commit can
    short-circuit on the first failure.

.PARAMETER SkipTests
    Skip the pytest run. Useful during local iteration when you want only the
    static-analysis gates.

.PARAMETER SkipMypy
    Skip the mypy run.

.PARAMETER SkipRuff
    Skip the ruff run.

.OUTPUTS
    Per-tool status lines on stdout. Final summary line:
        CHECK: OK
        CHECK: FAILED tools=ruff,mypy,pytest
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

$failedTools = @()

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
}

if (-not $SkipTests) {
    Invoke-Tool -Label 'pytest' -Action {
        Push-Location $blockingRoot
        try {
            python -m pytest test_code_rules_enforcer*.py
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
    exit 1
}
