#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Rewrites legacy shell-invocation rules in Claude Code settings*.json files
    to the pwsh-only canonical form.

.DESCRIPTION
    Walks the configured project roots, finds every settings.json,
    settings.local.json, and settings.local.json.template, and rewrites permission
    rule strings that invoke powershell / powershell.exe / bash -c / cmd /c
    into their pwsh equivalents per the migration mapping in
    rules/shell-invocation-policy.md. Defaults to dry-run; pass -Apply to write
    changes. Prints exactly one summary line.

.PARAMETER Roots
    One or more directories to scan recursively. Defaults to the user's known
    Claude Code project parents.

.PARAMETER Apply
    Write changes back to disk. Without this switch, runs in dry-run mode and
    reports what would change without modifying any files.

.OUTPUTS
    One line on stdout:
        DRY RUN: would migrate <count> rules IN=<n> FILES UNPARSEABLE=<m> FILES
        MIGRATED: <count> rules IN=<n> FILES UNPARSEABLE=<m> FILES
        MIGRATED: 0 rules SCANNED=<n> FILES UNPARSEABLE=<m> FILES (already compliant)
        MIGRATED: NO FILES SCANNED UNPARSEABLE=<m> FILES

.EXAMPLE
    pwsh -NoProfile -File Migrate-ShellPolicy.ps1
    pwsh -NoProfile -File Migrate-ShellPolicy.ps1 -Apply
    pwsh -NoProfile -File Migrate-ShellPolicy.ps1 -Apply -Verbose

.NOTES
    Files are written as UTF-8 without BOM to preserve cross-platform
    compatibility and avoid corrupting first-line JSON parsing.
#>
[CmdletBinding()]
param(
    [string[]]$Roots = @(
        (Join-Path $env:USERPROFILE '.claude'),
        'Y:\Projects',
        'Y:\Information Technology\Scripts',
        'Y:\Python',
        'Y:\claude-settings'
    ),
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$caseInsensitiveOptions = [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
$ruleRewrites = @(
    @{ Pattern = [regex]::new('^Bash\(powershell\.exe:\*\)$', $caseInsensitiveOptions);                                       Replacement = 'Bash(pwsh:*)' }
    @{ Pattern = [regex]::new('^Bash\(powershell:\*\)$', $caseInsensitiveOptions);                                            Replacement = 'Bash(pwsh:*)' }
    @{ Pattern = [regex]::new('^Bash\((?:powershell|pwsh)(?:\.exe)?\s+(?:-NoProfile\s+)?-Command\s+"&\s+''([^'']+)''(.*?)"\)$', $caseInsensitiveOptions); Replacement = 'Bash(pwsh -NoProfile -File ''$1''$2)' }
    @{ Pattern = [regex]::new('^Bash\((?:powershell|pwsh)(?:\.exe)?\s+(?:-NoProfile\s+)?-Command\s+''&\s+"([^"]+)"(.*?)''\)$', $caseInsensitiveOptions); Replacement = 'Bash(pwsh -NoProfile -File "$1"$2)' }
    @{ Pattern = [regex]::new('^Bash\(powershell\.exe\s+-Command\s+(.*)\)$', $caseInsensitiveOptions);                        Replacement = 'Bash(pwsh -NoProfile -Command $1)' }
    @{ Pattern = [regex]::new('^Bash\(powershell\s+-Command\s+(.*)\)$', $caseInsensitiveOptions);                             Replacement = 'Bash(pwsh -NoProfile -Command $1)' }
    @{ Pattern = [regex]::new('^Bash\(powershell\.exe\s+-NoProfile\s+-Command\s+(.*)\)$', $caseInsensitiveOptions);           Replacement = 'Bash(pwsh -NoProfile -Command $1)' }
    @{ Pattern = [regex]::new('^Bash\(powershell\s+-NoProfile\s+-Command\s+(.*)\)$', $caseInsensitiveOptions);                Replacement = 'Bash(pwsh -NoProfile -Command $1)' }
    @{ Pattern = [regex]::new('^Bash\(powershell\.exe\s+-NoProfile\s+-File\s+(.*)\)$', $caseInsensitiveOptions);              Replacement = 'Bash(pwsh -NoProfile -File $1)' }
    @{ Pattern = [regex]::new('^Bash\(powershell\s+-NoProfile\s+-File\s+(.*)\)$', $caseInsensitiveOptions);                   Replacement = 'Bash(pwsh -NoProfile -File $1)' }
    @{ Pattern = [regex]::new('^Bash\(powershell\.exe\s+-File\s+(.*)\)$', $caseInsensitiveOptions);                           Replacement = 'Bash(pwsh -NoProfile -File $1)' }
    @{ Pattern = [regex]::new('^Bash\(powershell\s+-File\s+(.*)\)$', $caseInsensitiveOptions);                                Replacement = 'Bash(pwsh -NoProfile -File $1)' }
    @{ Pattern = [regex]::new('^Bash\(bash\s+-c\s+(.*)\)$', $caseInsensitiveOptions);                                         Replacement = 'Bash(pwsh -NoProfile -Command $1)' }
    @{ Pattern = [regex]::new('^Bash\(cmd\.exe\s+/c\s+(.*)\)$', $caseInsensitiveOptions);                                     Replacement = 'Bash(pwsh -NoProfile -Command $1)' }
    @{ Pattern = [regex]::new('^Bash\(cmd\s+/c\s+(.*)\)$', $caseInsensitiveOptions);                                          Replacement = 'Bash(pwsh -NoProfile -Command $1)' }
    @{ Pattern = [regex]::new('^Bash\(bash\s+--login\b.*\)$', $caseInsensitiveOptions);                                       Replacement = 'Bash(pwsh -NoProfile -Command ''Write-Error "manual conversion needed for bash --login rule"; exit 1'')' }
    @{ Pattern = [regex]::new('^Bash\(bash\s+--rcfile\b.*\)$', $caseInsensitiveOptions);                                      Replacement = 'Bash(pwsh -NoProfile -Command ''Write-Error "manual conversion needed for bash --rcfile rule"; exit 1'')' }
    @{ Pattern = [regex]::new('^Bash\(bash\s+--init-file\b.*\)$', $caseInsensitiveOptions);                                   Replacement = 'Bash(pwsh -NoProfile -Command ''Write-Error "manual conversion needed for bash --init-file rule"; exit 1'')' }
)

$settingsFileNames = @(
    'settings.json',
    'settings.local.json',
    'settings.local.json.template'
)

function Get-MigratedRule {
    param([string]$Rule)
    foreach ($rewrite in $ruleRewrites) {
        if ($rewrite.Pattern.IsMatch($Rule)) {
            return $rewrite.Pattern.Replace($Rule, $rewrite.Replacement)
        }
    }
    return $Rule
}

function Test-HasProperty {
    param($Target, [string]$Name)
    if ($null -eq $Target) { return $false }
    if ($Target -isnot [psobject]) { return $false }
    return ($Target.PSObject.Properties.Name -contains $Name)
}

function Convert-PermissionsArrays {
    param($SettingsObject)
    $rewriteCount = 0
    if (-not (Test-HasProperty -Target $SettingsObject -Name 'permissions')) { return $rewriteCount }
    $permissions = $SettingsObject.permissions
    foreach ($key in @('allow', 'ask')) {
        if (-not (Test-HasProperty -Target $permissions -Name $key)) { continue }
        $existingArray = $permissions.$key
        if ($null -eq $existingArray) { continue }
        $newArray = @()
        $seenMigratedStrings = [System.Collections.Generic.HashSet[string]]::new()
        foreach ($rule in $existingArray) {
            if ($rule -is [string]) {
                $migrated = Get-MigratedRule -Rule $rule
                $isRewrite = ($migrated -ne $rule)
                if ($seenMigratedStrings.Contains($migrated)) {
                    if ($isRewrite) {
                        Write-Verbose "  dedupe-collapsed: '$rule' -> '$migrated' (duplicate of earlier rewrite)"
                        $rewriteCount++
                    }
                    continue
                }
                [void]$seenMigratedStrings.Add($migrated)
                if ($isRewrite) {
                    Write-Verbose "  rewrite: '$rule' -> '$migrated'"
                    $rewriteCount++
                }
                $newArray += $migrated
            } else {
                $newArray += $rule
            }
        }
        $permissions.$key = $newArray
    }
    return $rewriteCount
}

$totalRewrites = 0
$filesChanged = 0
$scannedFileCount = 0
$unparseableFileCount = 0
$existingRoots = $Roots | Where-Object { Test-Path $_ }

foreach ($root in $existingRoots) {
    $candidateFiles = Get-ChildItem -Path $root -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $settingsFileNames -contains $_.Name }
    foreach ($file in $candidateFiles) {
        $rawContent = Get-Content -Path $file.FullName -Raw -ErrorAction SilentlyContinue
        if ([string]::IsNullOrWhiteSpace($rawContent)) { continue }
        try {
            $parsed = $rawContent | ConvertFrom-Json -ErrorAction Stop
        } catch {
            $unparseableFileCount++
            Write-Warning "Skipped (invalid JSON): $($file.FullName)"
            continue
        }
        $scannedFileCount++
        Write-Verbose "Scanning: $($file.FullName)"
        $rewriteCount = Convert-PermissionsArrays -SettingsObject $parsed
        if ($rewriteCount -gt 0) {
            $totalRewrites += $rewriteCount
            $filesChanged++
            if ($Apply) {
                $newJson = $parsed | ConvertTo-Json -Depth 100
                [IO.File]::WriteAllText($file.FullName, $newJson, [Text.UTF8Encoding]::new($false))
            }
        }
    }
}

if ($scannedFileCount -eq 0 -and $unparseableFileCount -eq 0) {
    Write-Warning 'No settings files found in any of the configured roots — migration is vacuous.'
    Write-Output 'MIGRATED: NO FILES SCANNED UNPARSEABLE=0 FILES'
    exit 1
}

if ($scannedFileCount -eq 0 -and $unparseableFileCount -gt 0) {
    Write-Output ('MIGRATED: NO FILES SCANNED UNPARSEABLE={0} FILES (migration unsound)' -f $unparseableFileCount)
    exit 1
}

if ($totalRewrites -eq 0) {
    Write-Output ('MIGRATED: 0 rules SCANNED={0} FILES UNPARSEABLE={1} FILES (already compliant)' -f $scannedFileCount, $unparseableFileCount)
    if ($unparseableFileCount -gt 0) { exit 1 }
    exit 0
}

if ($Apply) {
    Write-Output ('MIGRATED: {0} rules IN={1} FILES SCANNED={2} FILES UNPARSEABLE={3} FILES' -f $totalRewrites, $filesChanged, $scannedFileCount, $unparseableFileCount)
} else {
    Write-Output ('DRY RUN: would migrate {0} rules IN={1} FILES SCANNED={2} FILES UNPARSEABLE={3} FILES' -f $totalRewrites, $filesChanged, $scannedFileCount, $unparseableFileCount)
}
if ($unparseableFileCount -gt 0) { exit 1 }
exit 0
