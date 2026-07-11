#!/usr/bin/env pwsh
[CmdletBinding()]
param(
    [switch]$AsJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$noiseEmailPatterns = @(
    'example',
    'sentry\.io',
    '@anthropic',
    '^Claude@\d'
)

function Test-NoiseEmail {
    param([string]$Email)
    foreach ($pattern in $noiseEmailPatterns) {
        if ($Email -imatch $pattern) { return $true }
    }
    return $false
}

function Get-EmailCandidatesFromProfile {
    param([string]$ProfileDirectory)
    $scanDirectories = @('sentry', 'IndexedDB', 'Session Storage', 'WebStorage') |
        ForEach-Object { Join-Path $ProfileDirectory $_ } |
        Where-Object { Test-Path -LiteralPath $_ }
    $emailPattern = '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+'
    $maximumFileBytes = 50MB
    $foundEmails = [System.Collections.Generic.HashSet[string]]::new()

    foreach ($scanDirectory in $scanDirectories) {
        $candidateFiles = Get-ChildItem -LiteralPath $scanDirectory -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Length -lt $maximumFileBytes }
        foreach ($candidateFile in $candidateFiles) {
            try {
                $fileText = Get-Content -LiteralPath $candidateFile.FullName -Raw -Encoding Ascii -ErrorAction Stop
            }
            catch {
                continue
            }
            if ([string]::IsNullOrEmpty($fileText)) { continue }
            foreach ($match in [regex]::Matches($fileText, $emailPattern)) {
                $candidateEmail = $match.Value
                if (-not (Test-NoiseEmail -Email $candidateEmail)) {
                    [void]$foundEmails.Add($candidateEmail)
                }
            }
        }
    }
    return $foundEmails
}

function Write-AccountResult {
    param(
        [string]$Email,
        [string]$AccountUuid,
        [string]$Source,
        [string]$CliEmail,
        [string]$CliAccountUuid
    )
    if ($AsJson) {
        [pscustomobject]@{
            account        = $Email
            accountUuid    = $AccountUuid
            source         = $Source
            cliAccount     = $CliEmail
            cliAccountUuid = $CliAccountUuid
        } | ConvertTo-Json
        return
    }
    Write-Output "Account: $Email"
    Write-Output "AccountUuid: $AccountUuid"
    Write-Output "Source: $Source"
    if ($CliEmail) {
        Write-Output "CliAccount: $CliEmail"
        Write-Output "CliAccountUuid: $CliAccountUuid"
    }
}

$cliConfigPath = Join-Path $HOME '.claude.json'
if (-not (Test-Path -LiteralPath $cliConfigPath)) {
    Write-Error "CLI config not found: $cliConfigPath"
    exit 2
}

try {
    $cliConfig = Get-Content -LiteralPath $cliConfigPath -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
}
catch {
    Write-Error "Failed to parse CLI config as JSON: $cliConfigPath"
    exit 2
}

$cliEmail = $cliConfig.oauthAccount.emailAddress
$cliAccountUuid = $cliConfig.oauthAccount.accountUuid
if (-not $cliEmail -or -not $cliAccountUuid) {
    Write-Error "CLI config is missing oauthAccount.emailAddress or oauthAccount.accountUuid: $cliConfigPath"
    exit 2
}

$profileDirectory = $env:CLAUDE_USER_DATA_DIR
if (-not $profileDirectory -or -not (Test-Path -LiteralPath $profileDirectory)) {
    Write-AccountResult -Email $cliEmail -AccountUuid $cliAccountUuid -Source 'cli-config'
    exit 0
}

$profileConfigPath = Join-Path $profileDirectory 'config.json'
if (-not (Test-Path -LiteralPath $profileConfigPath)) {
    Write-Error "Desktop profile config not found: $profileConfigPath"
    exit 2
}

try {
    $profileConfig = Get-Content -LiteralPath $profileConfigPath -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
}
catch {
    Write-Error "Failed to parse desktop profile config as JSON: $profileConfigPath"
    exit 2
}

$profileAccountUuid = $profileConfig.lastKnownAccountUuid
if (-not $profileAccountUuid) {
    Write-Error "Desktop profile config is missing lastKnownAccountUuid: $profileConfigPath"
    exit 2
}

if ($profileAccountUuid -eq $cliAccountUuid) {
    Write-AccountResult -Email $cliEmail -AccountUuid $cliAccountUuid -Source 'desktop-profile (matches cli-config)'
    exit 0
}

$candidateEmails = @(Get-EmailCandidatesFromProfile -ProfileDirectory $profileDirectory)
if ($candidateEmails.Count -eq 1) {
    Write-AccountResult -Email $candidateEmails[0] -AccountUuid $profileAccountUuid -Source 'desktop-profile (differs from cli-config)' -CliEmail $cliEmail -CliAccountUuid $cliAccountUuid
    exit 0
}

if ($candidateEmails.Count -eq 0) {
    Write-Error "Desktop profile account ($profileAccountUuid) differs from CLI config, but no candidate email was recovered from profile storage: $profileDirectory"
    exit 1
}

Write-Error "Desktop profile account ($profileAccountUuid) differs from CLI config, and multiple candidate emails were found in profile storage: $($candidateEmails -join ', ')"
exit 1
