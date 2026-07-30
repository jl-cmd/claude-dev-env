# Windows CI adapter for the Node installer lifecycle driver.
#
# The driver already redirects HOME, USERPROFILE, and GIT_CONFIG_GLOBAL into a
# throwaway sandbox. This adapter records that isolation contract, runs the
# 16-check driver, and writes bounded evidence under -EvidenceRoot so a failed
# Windows runner leaves an actionable artifact.
#
# Usage (from packages/claude-dev-env):
#   pwsh -NoProfile -File scripts/ci/windows-installer-lifecycle.ps1 -EvidenceRoot <dir>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$EvidenceRoot
)

$ErrorActionPreference = 'Stop'

$packageRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$driverPath = Join-Path $packageRoot '.claude\skills\run-claude-dev-env\driver.mjs'
$evidenceDirectory = $EvidenceRoot

if (-not (Test-Path -LiteralPath $driverPath)) {
    throw "Lifecycle driver missing at $driverPath"
}

New-Item -ItemType Directory -Force -Path $evidenceDirectory | Out-Null

$preflightPath = Join-Path $evidenceDirectory 'preflight.json'
$driverLogPath = Join-Path $evidenceDirectory 'driver.log'
$summaryPath = Join-Path $evidenceDirectory 'summary.json'

$preflight = [ordered]@{
    packageRoot = $packageRoot
    driverPath = $driverPath
    platform = [System.Environment]::OSVersion.VersionString
    nodeVersion = (& node --version 2>&1 | Out-String).Trim()
    pythonVersion = (& python --version 2>&1 | Out-String).Trim()
    isolationContract = @(
        'HOME',
        'USERPROFILE',
        'GIT_CONFIG_GLOBAL'
    )
    note = 'Driver owns isolation roots; adapter never points at the real user profile.'
}
$preflight | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $preflightPath -Encoding utf8

Write-Host "Evidence root: $evidenceDirectory"
Write-Host "Driver: $driverPath"
Write-Host "Isolation contract: HOME, USERPROFILE, GIT_CONFIG_GLOBAL (driver-owned sandbox)"

$driverOutput = & node $driverPath 2>&1
$driverExitCode = $LASTEXITCODE
$driverOutput | ForEach-Object { Write-Host $_ }
$driverOutputText = ($driverOutput | Out-String)
[System.IO.File]::WriteAllText($driverLogPath, $driverOutputText)

$passedCheckMatch = [regex]::Match($driverOutputText, '(\d+)/(\d+) checks passed')
$summary = [ordered]@{
    exitCode = $driverExitCode
    allChecksPassed = ($driverExitCode -eq 0 -and $driverOutputText -match 'ALL CHECKS PASSED')
    checksLine = if ($passedCheckMatch.Success) { $passedCheckMatch.Value } else { 'unparsed' }
    evidenceFiles = @(
        'preflight.json',
        'driver.log',
        'summary.json'
    )
}
$summary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $summaryPath -Encoding utf8

if ($driverExitCode -ne 0) {
    throw "Lifecycle driver exited $driverExitCode (see $driverLogPath)"
}
if ($driverOutputText -notmatch 'ALL CHECKS PASSED') {
    throw "Lifecycle driver output missing ALL CHECKS PASSED (see $driverLogPath)"
}

Write-Host "Windows installer lifecycle: OK"
exit 0
