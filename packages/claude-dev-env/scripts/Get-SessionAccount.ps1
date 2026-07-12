#!/usr/bin/env pwsh
[CmdletBinding()]
param(
    [switch]$AsJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$noiseEmailPatterns = @(
    '@example\.(com|org|net)$',
    'sentry\.io',
    '@anthropic',
    '^Claude@\d'
)

$isoLatin1CodePage = 28591

function Test-NoiseEmail {
    param([string]$Email)
    foreach ($pattern in $noiseEmailPatterns) {
        if ($Email -imatch $pattern) { return $true }
    }
    return $false
}

function Get-EncodingAgnosticTextViews {
    param([string]$FilePath)
    try {
        $fileBytes = [System.IO.File]::ReadAllBytes($FilePath)
        if ($fileBytes.Length -eq 0) { return @() }
        $isoLatin1Encoding = [System.Text.Encoding]::GetEncoding($isoLatin1CodePage)
        return @(
            $isoLatin1Encoding.GetString($fileBytes),
            [System.Text.Encoding]::Unicode.GetString($fileBytes)
        )
    }
    catch {
        return @()
    }
}

function Get-EmailCandidatesFromProfile {
    param(
        [string]$ProfileDirectory,
        [string]$ExcludeEmail
    )
    $scanDirectories = @('sentry', 'IndexedDB', 'Session Storage', 'WebStorage') |
        ForEach-Object { Join-Path $ProfileDirectory $_ } |
        Where-Object { Test-Path -LiteralPath $_ }
    $emailPattern = '(?<![a-zA-Z0-9._%+-])[a-zA-Z0-9][a-zA-Z0-9._%+-]*@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+(?![a-zA-Z0-9-])'
    $maximumFileBytes = 50MB
    $foundEmails = [System.Collections.Generic.HashSet[string]]::new()

    foreach ($scanDirectory in $scanDirectories) {
        $candidateFiles = Get-ChildItem -LiteralPath $scanDirectory -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Length -lt $maximumFileBytes }
        foreach ($candidateFile in $candidateFiles) {
            $decodedTextViews = Get-EncodingAgnosticTextViews -FilePath $candidateFile.FullName
            foreach ($decodedText in $decodedTextViews) {
                foreach ($match in [regex]::Matches($decodedText, $emailPattern)) {
                    $candidateEmail = $match.Value
                    $isKnownCliEmail = $ExcludeEmail -and ($candidateEmail -ieq $ExcludeEmail)
                    if (-not (Test-NoiseEmail -Email $candidateEmail) -and -not $isKnownCliEmail) {
                        [void]$foundEmails.Add($candidateEmail)
                    }
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

function New-SessionAccountResult {
    param(
        [int]$ExitCode,
        [string]$Email = $null,
        [string]$AccountUuid = $null,
        [string]$Source = $null,
        [string]$CliEmail = $null,
        [string]$CliAccountUuid = $null,
        [string]$ErrorMessage = $null
    )
    [pscustomobject]@{
        ExitCode       = $ExitCode
        Email          = $Email
        AccountUuid    = $AccountUuid
        Source         = $Source
        CliEmail       = $CliEmail
        CliAccountUuid = $CliAccountUuid
        ErrorMessage   = $ErrorMessage
    }
}

function Resolve-SessionAccount {
    param(
        [string]$CliConfigPath,
        [string]$ProfileDirectory
    )
    if (-not (Test-Path -LiteralPath $CliConfigPath)) {
        return New-SessionAccountResult -ExitCode 2 -ErrorMessage "CLI config not found: $CliConfigPath"
    }

    try {
        $cliConfig = Get-Content -LiteralPath $CliConfigPath -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
    }
    catch {
        return New-SessionAccountResult -ExitCode 2 -ErrorMessage "Failed to parse CLI config as JSON: $CliConfigPath"
    }

    $cliEmail = $cliConfig.oauthAccount.emailAddress
    $cliAccountUuid = $cliConfig.oauthAccount.accountUuid
    if (-not $cliEmail -or -not $cliAccountUuid) {
        return New-SessionAccountResult -ExitCode 2 -ErrorMessage "CLI config is missing oauthAccount.emailAddress or oauthAccount.accountUuid: $CliConfigPath"
    }

    if (-not $ProfileDirectory -or -not (Test-Path -LiteralPath $ProfileDirectory)) {
        return New-SessionAccountResult -ExitCode 0 -Email $cliEmail -AccountUuid $cliAccountUuid -Source 'cli-config'
    }

    $profileConfigPath = Join-Path $ProfileDirectory 'config.json'
    if (-not (Test-Path -LiteralPath $profileConfigPath)) {
        return New-SessionAccountResult -ExitCode 2 -ErrorMessage "Desktop profile config not found: $profileConfigPath"
    }

    try {
        $profileConfig = Get-Content -LiteralPath $profileConfigPath -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
    }
    catch {
        return New-SessionAccountResult -ExitCode 2 -ErrorMessage "Failed to parse desktop profile config as JSON: $profileConfigPath"
    }

    $profileAccountUuid = $profileConfig.lastKnownAccountUuid
    if (-not $profileAccountUuid) {
        return New-SessionAccountResult -ExitCode 2 -ErrorMessage "Desktop profile config is missing lastKnownAccountUuid: $profileConfigPath"
    }

    if ($profileAccountUuid -eq $cliAccountUuid) {
        return New-SessionAccountResult -ExitCode 0 -Email $cliEmail -AccountUuid $cliAccountUuid -Source 'desktop-profile (matches cli-config)'
    }

    $candidateEmails = @(Get-EmailCandidatesFromProfile -ProfileDirectory $ProfileDirectory -ExcludeEmail $cliEmail)
    if ($candidateEmails.Count -eq 1) {
        return New-SessionAccountResult -ExitCode 0 -Email $candidateEmails[0] -AccountUuid $profileAccountUuid -Source 'desktop-profile (differs from cli-config)' -CliEmail $cliEmail -CliAccountUuid $cliAccountUuid
    }

    if ($candidateEmails.Count -eq 0) {
        return New-SessionAccountResult -ExitCode 1 -ErrorMessage "Desktop profile account ($profileAccountUuid) differs from CLI config, but no candidate email was recovered from profile storage: $ProfileDirectory"
    }

    return New-SessionAccountResult -ExitCode 1 -ErrorMessage "Desktop profile account ($profileAccountUuid) differs from CLI config, and multiple candidate emails were found in profile storage: $($candidateEmails -join ', ')"
}

function Invoke-GetSessionAccount {
    $cliConfigPath = Join-Path $HOME '.claude.json'
    $sessionAccount = Resolve-SessionAccount -CliConfigPath $cliConfigPath -ProfileDirectory $env:CLAUDE_USER_DATA_DIR
    if ($sessionAccount.ErrorMessage) {
        Write-Error $sessionAccount.ErrorMessage -ErrorAction Continue
        exit $sessionAccount.ExitCode
    }
    Write-AccountResult -Email $sessionAccount.Email -AccountUuid $sessionAccount.AccountUuid -Source $sessionAccount.Source -CliEmail $sessionAccount.CliEmail -CliAccountUuid $sessionAccount.CliAccountUuid
    exit $sessionAccount.ExitCode
}

if ($MyInvocation.InvocationName -ne '.') {
    Invoke-GetSessionAccount
}
