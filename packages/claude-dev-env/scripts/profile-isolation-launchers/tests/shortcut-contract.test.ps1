# Contract tests for N1 shortcut source semantics (read-only slice).
# Run: pwsh -NoProfile -File tests/shortcut-contract.test.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$packageLaunchersRoot = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $packageLaunchersRoot 'windows\shortcut-manifest.json'
$inventoryScript = Join-Path $packageLaunchersRoot 'windows\shortcut-inventory.ps1'
$reconcileScript = Join-Path $packageLaunchersRoot 'windows\shortcut-reconcile.ps1'

$script:allFailures = @()

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) {
        $script:allFailures += $Message
        Write-Host "FAIL: $Message"
    }
    else {
        Write-Host "PASS: $Message"
    }
}

# Manifest loads with provisional native-Desktop-wins policy.
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
Assert-True ($manifest.schemaVersion -eq 1) 'manifest schemaVersion is 1'
Assert-True ($manifest.policy.liveMutationAuthorized -eq $false) 'live mutation stays unauthorized until owner confirmation'
Assert-True ($manifest.policy.unsuffixedNames -match 'Native Desktop wins') 'provisional unsuffixed policy is native Desktop wins'
Assert-True ($manifest.policy.browserNames -match 'Chrome') 'browser names require explicit Chrome/Web labels'

# Every managed shortcut has one source, profile, and grouping identity.
$allVisibleNames = @{}
$allGrouping = @{}
foreach ($eachShortcut in $manifest.allManagedShortcuts) {
    Assert-True ([string]::IsNullOrWhiteSpace($eachShortcut.id) -eq $false) "shortcut id present"
    Assert-True ([string]::IsNullOrWhiteSpace($eachShortcut.source) -eq $false) "$($eachShortcut.id) has source"
    Assert-True ([string]::IsNullOrWhiteSpace($eachShortcut.profileId) -eq $false) "$($eachShortcut.id) has profileId"
    Assert-True ([string]::IsNullOrWhiteSpace($eachShortcut.groupingIdentity) -eq $false) "$($eachShortcut.id) has groupingIdentity"
    Assert-True ([string]::IsNullOrWhiteSpace($eachShortcut.visibleName) -eq $false) "$($eachShortcut.id) has visibleName"
    if ($allVisibleNames.ContainsKey($eachShortcut.visibleName)) {
        Assert-True $false "duplicate visible name: $($eachShortcut.visibleName)"
    }
    else {
        $allVisibleNames[$eachShortcut.visibleName] = $eachShortcut.id
        Assert-True $true "unique visible name: $($eachShortcut.visibleName)"
    }
    if ($allGrouping.ContainsKey($eachShortcut.groupingIdentity)) {
        Assert-True $false "duplicate grouping identity: $($eachShortcut.groupingIdentity)"
    }
    else {
        $allGrouping[$eachShortcut.groupingIdentity] = $eachShortcut.id
        Assert-True $true "unique grouping identity: $($eachShortcut.groupingIdentity)"
    }
}

# Native and Chrome variants retain distinct grouping identity for editor and mel.
$editorNative = $manifest.allManagedShortcuts | Where-Object { $_.id -eq 'desktop-editor-native' }
$editorChrome = $manifest.allManagedShortcuts | Where-Object { $_.id -eq 'start-editor-chrome' }
Assert-True ($editorNative.groupingIdentity -ne $editorChrome.groupingIdentity) 'editor native/chrome grouping differs'
Assert-True ($editorNative.source -eq 'native-desktop') 'editor desktop source is native-desktop'
Assert-True ($editorChrome.source -eq 'chrome-start-menu') 'editor start-menu source is chrome-start-menu'

# Inventory is read-only against disposable paths.
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("shortcut-contract-" + [guid]::NewGuid().ToString('n'))
$desktop = Join-Path $tempRoot 'Desktop'
$startMenu = Join-Path $tempRoot 'StartMenu'
New-Item -ItemType Directory -Path $desktop, $startMenu | Out-Null
try {
    $inventoryJson = & $inventoryScript -ManifestPath $manifestPath -DesktopPath $desktop -StartMenuPath $startMenu
    $inventory = $inventoryJson | ConvertFrom-Json
    Assert-True ($inventory.mode -eq 'read-only-inventory') 'inventory mode is read-only'
    Assert-True ($inventory.shortcuts.Count -eq $manifest.allManagedShortcuts.Count) 'inventory rows match manifest'
    Assert-True (-not (Get-ChildItem -LiteralPath $desktop -Force | Where-Object { $_.Extension -eq '.lnk' })) 'inventory does not create desktop shortcuts'
    Assert-True (-not (Get-ChildItem -LiteralPath $startMenu -Force | Where-Object { $_.Extension -eq '.lnk' })) 'inventory does not create start-menu shortcuts'

    $previewJson = & $reconcileScript -ManifestPath $manifestPath -DesktopPath $desktop -StartMenuPath $startMenu
    $preview = $previewJson | ConvertFrom-Json
    Assert-True ($preview.mode -eq 'preview-only') 'reconcile defaults to preview-only'
    Assert-True ($preview.liveMutationAuthorized -eq $false) 'preview reports mutation unauthorized'
    Assert-True ($preview.actions.Count -eq $manifest.allManagedShortcuts.Count) 'preview lists every managed shortcut'

    $applyFailed = $false
    try {
        & $reconcileScript -ManifestPath $manifestPath -DesktopPath $desktop -StartMenuPath $startMenu -Apply | Out-Null
    }
    catch {
        $applyFailed = $true
        Assert-True ($_.Exception.Message -match 'live shortcut mutation refused') 'apply refuses without owner authorization'
    }
    Assert-True $applyFailed 'apply path must throw while unauthorized'
}
finally {
    Remove-Item -Recurse -Force -Confirm:$false -LiteralPath $tempRoot
}

if ($script:allFailures.Count -gt 0) {
    Write-Host ("FAILED {0} assertion(s)" -f $script:allFailures.Count)
    exit 1
}
Write-Host 'shortcut-contract: all assertions passed'
exit 0
