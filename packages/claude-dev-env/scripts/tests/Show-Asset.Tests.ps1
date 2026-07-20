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

    function Start-SleeperParent {
        param(
            [int]$SleepSeconds
        )
        $allArguments = @(
            '-NoProfile'
            '-WindowStyle'
            'Hidden'
            '-Command'
            "Start-Sleep -Seconds $SleepSeconds"
        )
        return Start-Process -FilePath 'pwsh' -ArgumentList $allArguments -PassThru -WindowStyle Hidden
    }

    function Stop-TestProcessIfRunning {
        param(
            [System.Diagnostics.Process]$Process
        )
        if (-not $Process.HasExited) {
            Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}

Describe 'Show-Asset.ps1 parent-death and max-lifetime exit' {
    BeforeEach {
        $testImageDirectory = Join-Path $TestDrive ("show-asset-" + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $testImageDirectory -Force | Out-Null
        $script:testImagePath = New-TestPngFile -DirectoryPath $testImageDirectory
    }

    It 'exits within 5s after the watched parent process dies' {
        # Keep the parent alive until the viewer has resolved GetProcessById;
        # a 2s sleeper can exit before the viewer attaches and silently disable
        # parent-death watch (MaxLifetimeSeconds would then keep the viewer open).
        $watchedParent = Start-SleeperParent -SleepSeconds 120

        $viewerProcess = Start-ShowAssetProcess `
            -ImagePath $script:testImagePath `
            -ParentProcessId $watchedParent.Id `
            -MaxLifetimeSeconds 120 `
            -ParentPollIntervalMilliseconds 500

        try {
            Start-Sleep -Milliseconds 1500
            $viewerProcess.HasExited | Should -BeFalse -Because 'viewer must still be running before parent kill'

            Stop-Process -Id $watchedParent.Id -Force
            $parentExitTime = Get-Date
            $null = $watchedParent.WaitForExit(5000)
            $didViewerExit = $viewerProcess.WaitForExit(5000)
            $secondsAfterParentDeath = ((Get-Date) - $parentExitTime).TotalSeconds

            $didViewerExit | Should -BeTrue -Because 'Show-Asset must exit after the watched parent dies'
            $secondsAfterParentDeath | Should -BeLessOrEqual 5 -Because 'parent-death exit must complete within 5 seconds'
            $viewerProcess.HasExited | Should -BeTrue
        }
        finally {
            Stop-TestProcessIfRunning -Process $viewerProcess
            Stop-TestProcessIfRunning -Process $watchedParent
        }
    }

    It 'exits when max lifetime elapses while a window is still open' {
        $longLivedParent = Start-SleeperParent -SleepSeconds 120

        $viewerProcess = Start-ShowAssetProcess `
            -ImagePath $script:testImagePath `
            -ParentProcessId $longLivedParent.Id `
            -MaxLifetimeSeconds 2 `
            -ParentPollIntervalMilliseconds 500

        try {
            $didViewerExit = $viewerProcess.WaitForExit(10000)
            $didViewerExit | Should -BeTrue -Because 'Show-Asset must exit when max lifetime elapses'
            $viewerProcess.HasExited | Should -BeTrue
        }
        finally {
            Stop-TestProcessIfRunning -Process $viewerProcess
            Stop-TestProcessIfRunning -Process $longLivedParent
        }
    }
}
