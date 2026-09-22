#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Run every Pester suite under a tests directory and exit on its verdict.

.DESCRIPTION
    check.ps1 calls this script as a child process so Invoke-Tool reads a
    process exit code the way it does for ruff, mypy and pytest. Pester is a
    cmdlet and leaves $LASTEXITCODE alone, so running it in-process would
    report every suite as passing.

    A missing Pester module exits non-zero. A gate that cannot run its check
    has not passed it, and a skip here would leave the suites reporting
    nothing while the tree reads as covered.

.PARAMETER TestsRoot
    Directory holding the *.Tests.ps1 suites.

.OUTPUTS
    Pester's own detailed output. Exit code 0 when every suite passes.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$TestsRoot
)

$ErrorActionPreference = 'Stop'

if (-not (Get-Module -ListAvailable -Name Pester)) {
    Write-Error "Pester is not installed, so the suites under $TestsRoot cannot run."
    exit 1
}

Import-Module Pester -MinimumVersion 5.0

$suiteConfiguration = New-PesterConfiguration
$suiteConfiguration.Run.Path = $TestsRoot
$suiteConfiguration.Run.Exit = $true
$suiteConfiguration.Output.Verbosity = 'Detailed'

Invoke-Pester -Configuration $suiteConfiguration
