Set-StrictMode -Version Latest

BeforeAll {
    $scriptUnderTest = Join-Path (Split-Path -Parent $PSScriptRoot) 'Show-Asset.ps1'

    function New-TestPngFile {
        param(
            [string]$DirectoryPath
        )
        Add-Type -AssemblyName System.Drawing
        $pngPath = Join-Path $DirectoryPath 'show-asset-test.png'
        $bitmap = New-Object System.Drawing.Bitmap 8, 8
        try {
            $bitmap.SetPixel(0, 0, [System.Drawing.Color]::Red)
            $bitmap.Save($pngPath, [System.Drawing.Imaging.ImageFormat]::Png)
        }
        finally {
            $bitmap.Dispose()
        }
        return $pngPath
    }

    function Start-ShowAssetProcess {
        param(
            [string]$ImagePath,
            [int]$ParentProcessId,
            [int]$MaxLifetimeSeconds,
            [int]$ParentPollIntervalMilliseconds = 500
        )
        $allArguments = @(
            '-NoProfile'
            '-WindowStyle'
            'Hidden'
            '-File'
            $scriptUnderTest
            '-ParentProcessId'
            "$ParentProcessId"
            '-MaxLifetimeSeconds'
            "$MaxLifetimeSeconds"
            '-ParentPollIntervalMilliseconds'
            "$ParentPollIntervalMilliseconds"
            $ImagePath
        )
        return Start-Process -FilePath 'pwsh' -ArgumentList $allArguments -PassThru -WindowStyle Hidden
    }

    function Wait-ProcessExitWithin {
        param(
            [System.Diagnostics.Process]$Process,
            [int]$TimeoutMilliseconds
        )
        return $Process.WaitForExit($TimeoutMilliseconds)
    }
}

Describe 'Show-Asset.ps1 parent-death and max-lifetime exit' {
    BeforeEach {
        $testImageDirectory = Join-Path $TestDrive ("show-asset-" + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $testImageDirectory -Force | Out-Null
        $script:testImagePath = New-TestPngFile -DirectoryPath $testImageDirectory
    }

    It 'exits within 5s after the watched parent process dies' {
        $shortLivedParent = Start-Process -FilePath 'pwsh' -ArgumentList @(
            '-NoProfile'
            '-WindowStyle'
            'Hidden'
            '-Command'
            'Start-Sleep -Seconds 2'
        ) -PassThru -WindowStyle Hidden

        $viewerProcess = Start-ShowAssetProcess `
            -ImagePath $script:testImagePath `
            -ParentProcessId $shortLivedParent.Id `
            -MaxLifetimeSeconds 120 `
            -ParentPollIntervalMilliseconds 500

        try {
            $null = $shortLivedParent.WaitForExit(15000)
            $parentExitTime = Get-Date
            $didViewerExit = Wait-ProcessExitWithin -Process $viewerProcess -TimeoutMilliseconds 5000
            $secondsAfterParentDeath = ((Get-Date) - $parentExitTime).TotalSeconds

            $didViewerExit | Should -BeTrue -Because 'Show-Asset must exit after the watched parent dies'
            $secondsAfterParentDeath | Should -BeLessOrEqual 5 -Because 'parent-death exit must complete within 5 seconds'
            $viewerProcess.HasExited | Should -BeTrue
        }
        finally {
            if (-not $viewerProcess.HasExited) {
                Stop-Process -Id $viewerProcess.Id -Force -ErrorAction SilentlyContinue
            }
            if (-not $shortLivedParent.HasExited) {
                Stop-Process -Id $shortLivedParent.Id -Force -ErrorAction SilentlyContinue
            }
        }
    }

    It 'exits when max lifetime elapses while a window is still open' {
        $longLivedParent = Start-Process -FilePath 'pwsh' -ArgumentList @(
            '-NoProfile'
            '-WindowStyle'
            'Hidden'
            '-Command'
            'Start-Sleep -Seconds 120'
        ) -PassThru -WindowStyle Hidden

        $viewerProcess = Start-ShowAssetProcess `
            -ImagePath $script:testImagePath `
            -ParentProcessId $longLivedParent.Id `
            -MaxLifetimeSeconds 2 `
            -ParentPollIntervalMilliseconds 500

        try {
            $didViewerExit = Wait-ProcessExitWithin -Process $viewerProcess -TimeoutMilliseconds 10000
            $didViewerExit | Should -BeTrue -Because 'Show-Asset must exit when max lifetime elapses'
            $viewerProcess.HasExited | Should -BeTrue
        }
        finally {
            if (-not $viewerProcess.HasExited) {
                Stop-Process -Id $viewerProcess.Id -Force -ErrorAction SilentlyContinue
            }
            if (-not $longLivedParent.HasExited) {
                Stop-Process -Id $longLivedParent.Id -Force -ErrorAction SilentlyContinue
            }
        }
    }

    It 'still registers Escape as the key that closes a form' {
        $scriptText = Get-Content -LiteralPath $scriptUnderTest -Raw
        $scriptText | Should -Match 'Keys\]::Escape'
        $scriptText | Should -Match '\$sender\.Close\(\)'
        $scriptText | Should -Match 'Add_KeyDown'
    }
}

<#
Manual Escape verification (interactive desktop; automated tests cover parent-death
and max-lifetime only):

  $png = Join-Path $env:TEMP 'show-asset-escape.png'
  Add-Type -AssemblyName System.Drawing
  $bitmap = New-Object System.Drawing.Bitmap 64, 64
  $bitmap.Save($png, [System.Drawing.Imaging.ImageFormat]::Png)
  $bitmap.Dispose()
  pwsh -NoProfile -File packages/claude-dev-env/scripts/Show-Asset.ps1 $png
  # Focus the image window and press Escape — window closes and process exits.
#>
