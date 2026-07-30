# Read-only inventory of managed Claude profile shortcuts.
# Does not mutate Desktop, Start Menu, or taskbar state.

[CmdletBinding()]
param(
    [string]$ManifestPath = (Join-Path $PSScriptRoot 'shortcut-manifest.json'),
    [string]$DesktopPath = [Environment]::GetFolderPath('Desktop'),
    [string]$StartMenuPath = [Environment]::GetFolderPath('StartMenu'),
    [string]$OutputPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $ManifestPath)) {
    throw "shortcut manifest missing: $ManifestPath"
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
if ($manifest.schemaVersion -ne 1) {
    throw "unsupported shortcut manifest schemaVersion: $($manifest.schemaVersion)"
}
if ($null -eq $manifest.allManagedShortcuts) {
    throw 'shortcut manifest allManagedShortcuts is required'
}

$allSeenIds = @{}
$allSeenVisibleNames = @{}
$allSeenGrouping = @{}
foreach ($eachShortcut in $manifest.allManagedShortcuts) {
    foreach ($eachFieldName in @('id', 'visibleName', 'source', 'profileId', 'locationKind', 'groupingIdentity')) {
        $fieldValue = $eachShortcut.$eachFieldName
        if ([string]::IsNullOrWhiteSpace([string]$fieldValue)) {
            throw "shortcut missing required field $eachFieldName"
        }
    }
    if ($allSeenIds.ContainsKey($eachShortcut.id)) {
        throw "duplicate shortcut id: $($eachShortcut.id)"
    }
    if ($allSeenVisibleNames.ContainsKey($eachShortcut.visibleName)) {
        throw "duplicate shortcut visibleName: $($eachShortcut.visibleName)"
    }
    if ($allSeenGrouping.ContainsKey($eachShortcut.groupingIdentity)) {
        throw "duplicate shortcut groupingIdentity: $($eachShortcut.groupingIdentity)"
    }
    $allSeenIds[$eachShortcut.id] = $true
    $allSeenVisibleNames[$eachShortcut.visibleName] = $true
    $allSeenGrouping[$eachShortcut.groupingIdentity] = $true
}

function Get-ShortcutMetadata {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ShortcutPath,
        [Parameter(Mandatory = $true)]
        $Shell
    )
    if (-not (Test-Path -LiteralPath $ShortcutPath)) {
        return $null
    }
    $link = $Shell.CreateShortcut($ShortcutPath)
    return [pscustomobject]@{
        path              = $ShortcutPath
        targetPath        = $link.TargetPath
        arguments         = $link.Arguments
        workingDirectory  = $link.WorkingDirectory
        iconLocation      = $link.IconLocation
        exists            = $true
    }
}

$shell = New-Object -ComObject WScript.Shell
$allRows = [System.Collections.Generic.List[object]]::new()
try {
    foreach ($eachShortcut in $manifest.allManagedShortcuts) {
        if ($eachShortcut.locationKind -eq 'desktop') {
            $baseDirectory = $DesktopPath
        }
        elseif ($eachShortcut.locationKind -eq 'start-menu') {
            $baseDirectory = $StartMenuPath
        }
        else {
            throw "unsupported locationKind for $($eachShortcut.id): $($eachShortcut.locationKind)"
        }
        $shortcutPath = Join-Path $baseDirectory ($eachShortcut.visibleName + '.lnk')
        $metadata = Get-ShortcutMetadata -ShortcutPath $shortcutPath -Shell $shell
        $allRows.Add([pscustomobject]@{
            id                = $eachShortcut.id
            visibleName       = $eachShortcut.visibleName
            source            = $eachShortcut.source
            profileId         = $eachShortcut.profileId
            locationKind      = $eachShortcut.locationKind
            targetKind        = $eachShortcut.targetKind
            launcherName      = $eachShortcut.launcherName
            groupingIdentity  = $eachShortcut.groupingIdentity
            expectedPath      = $shortcutPath
            exists            = [bool]$metadata
            targetPath        = if ($metadata) { $metadata.targetPath } else { $null }
            arguments         = if ($metadata) { $metadata.arguments } else { $null }
            workingDirectory  = if ($metadata) { $metadata.workingDirectory } else { $null }
            iconLocation      = if ($metadata) { $metadata.iconLocation } else { $null }
            liveMutationAuthorized = [bool]$manifest.policy.liveMutationAuthorized
        })
    }
}
finally {
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($shell)
}

$result = [pscustomobject]@{
    mode = 'read-only-inventory'
    policy = $manifest.policy
    scannedAt = (Get-Date).ToString('o')
    desktopPath = $DesktopPath
    startMenuPath = $StartMenuPath
    shortcuts = $allRows
}

$json = $result | ConvertTo-Json -Depth 6
if ($OutputPath) {
    $directory = Split-Path -Parent $OutputPath
    if ($directory -and -not (Test-Path -LiteralPath $directory)) {
        New-Item -ItemType Directory -Path $directory | Out-Null
    }
    [IO.File]::WriteAllText($OutputPath, $json, [Text.UTF8Encoding]::new($false))
}
Write-Output $json
