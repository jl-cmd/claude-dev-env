# Read-only reconciliation preview for managed Claude profile shortcuts.
# Live mutation is refused while policy.liveMutationAuthorized is false.

[CmdletBinding()]
param(
    [string]$ManifestPath = (Join-Path $PSScriptRoot 'shortcut-manifest.json'),
    [string]$DesktopPath = [Environment]::GetFolderPath('Desktop'),
    [string]$StartMenuPath = [Environment]::GetFolderPath('StartMenu'),
    [string]$OutputPath,
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$inventoryScript = Join-Path $PSScriptRoot 'shortcut-inventory.ps1'
if (-not (Test-Path -LiteralPath $inventoryScript)) {
    throw "inventory script missing: $inventoryScript"
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$inventoryJson = & $inventoryScript -ManifestPath $ManifestPath -DesktopPath $DesktopPath -StartMenuPath $StartMenuPath
$inventory = $inventoryJson | ConvertFrom-Json

$allActions = [System.Collections.Generic.List[object]]::new()
foreach ($eachRow in $inventory.shortcuts) {
    $actualPresent = [bool]$eachRow.exists
    $hasSourceIdentity = -not [string]::IsNullOrWhiteSpace([string]$eachRow.source) -and
        -not [string]::IsNullOrWhiteSpace([string]$eachRow.profileId) -and
        -not [string]::IsNullOrWhiteSpace([string]$eachRow.groupingIdentity)
    $status = if (-not $actualPresent) {
        'missing'
    }
    elseif ($hasSourceIdentity) {
        'present-unverified-target'
    }
    else {
        'source-ambiguous'
    }
    $allActions.Add([pscustomobject]@{
        id = $eachRow.id
        visibleName = $eachRow.visibleName
        source = $eachRow.source
        profileId = $eachRow.profileId
        groupingIdentity = $eachRow.groupingIdentity
        desiredPresent = $true
        actualPresent = $actualPresent
        status = $status
        expectedPath = $eachRow.expectedPath
        mutation = 'none'
    })
}

if ($Apply) {
    if (-not [bool]$manifest.policy.liveMutationAuthorized) {
        throw 'live shortcut mutation refused: policy.liveMutationAuthorized is false; owner confirmation required'
    }
    throw 'live shortcut mutation adapter is residual after owner confirmation (N1 apply path)'
}

$preview = [pscustomobject]@{
    mode = 'preview-only'
    policy = $manifest.policy
    actionCount = $allActions.Count
    actions = $allActions
    liveMutationAuthorized = [bool]$manifest.policy.liveMutationAuthorized
}

$json = $preview | ConvertTo-Json -Depth 6
if ($OutputPath) {
    $directory = Split-Path -Parent $OutputPath
    if ($directory -and -not (Test-Path -LiteralPath $directory)) {
        New-Item -ItemType Directory -Path $directory | Out-Null
    }
    [IO.File]::WriteAllText($OutputPath, $json, [Text.UTF8Encoding]::new($false))
}
Write-Output $json
