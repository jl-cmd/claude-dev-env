Set-StrictMode -Version Latest

BeforeAll {
    $scriptUnderTest = Join-Path (Split-Path -Parent $PSScriptRoot) 'Sync-RepoMain.ps1'

    function Invoke-TestGit {
        param(
            [string]$RepoPath,
            [string[]]$Arguments
        )
        $output = & git -C $RepoPath -c user.name=tester -c user.email=tester@example.com -c core.autocrlf=false @Arguments 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "git $($Arguments -join ' ') failed: $output"
        }
        return ($output | Out-String).Trim()
    }

    function Write-TestFile {
        param(
            [string]$RepoPath,
            [string]$RelativePath,
            [string]$Content
        )
        [System.IO.File]::WriteAllText((Join-Path $RepoPath $RelativePath), $Content)
    }

    function New-MirrorBehindRemote {
        <#
          Builds a bare remote plus a mirror clone one commit behind it. The
          remote's newer commit edits tracked.txt and adds added.txt.
        #>
        param([string]$Name)
        $rootPath = Join-Path $TestDrive $Name
        $remotePath = Join-Path $rootPath 'remote.git'
        $authorPath = Join-Path $rootPath 'author'
        $mirrorPath = Join-Path $rootPath 'mirror'
        New-Item -ItemType Directory -Force -Path $remotePath, $authorPath | Out-Null

        Invoke-TestGit -RepoPath $remotePath -Arguments @('init', '-q', '--bare', '-b', 'main') | Out-Null
        Invoke-TestGit -RepoPath $authorPath -Arguments @('init', '-q', '-b', 'main') | Out-Null
        Write-TestFile -RepoPath $authorPath -RelativePath 'tracked.txt' -Content "old`n"
        Invoke-TestGit -RepoPath $authorPath -Arguments @('add', '-A') | Out-Null
        Invoke-TestGit -RepoPath $authorPath -Arguments @('commit', '-q', '-m', 'first') | Out-Null
        Invoke-TestGit -RepoPath $authorPath -Arguments @('remote', 'add', 'origin', $remotePath) | Out-Null
        Invoke-TestGit -RepoPath $authorPath -Arguments @('push', '-q', 'origin', 'main') | Out-Null

        & git -c core.autocrlf=false clone -q $remotePath $mirrorPath 2>&1 | Out-Null
        Invoke-TestGit -RepoPath $mirrorPath -Arguments @('config', 'core.autocrlf', 'false') | Out-Null
        $oldTip = Invoke-TestGit -RepoPath $mirrorPath -Arguments @('rev-parse', 'HEAD')

        Write-TestFile -RepoPath $authorPath -RelativePath 'tracked.txt' -Content "new`n"
        Write-TestFile -RepoPath $authorPath -RelativePath 'added.txt' -Content "added`n"
        Invoke-TestGit -RepoPath $authorPath -Arguments @('add', '-A') | Out-Null
        Invoke-TestGit -RepoPath $authorPath -Arguments @('commit', '-q', '-m', 'second') | Out-Null
        Invoke-TestGit -RepoPath $authorPath -Arguments @('push', '-q', 'origin', 'main') | Out-Null
        $remoteTip = Invoke-TestGit -RepoPath $authorPath -Arguments @('rev-parse', 'HEAD')

        return [pscustomobject]@{
            MirrorPath = $mirrorPath
            LogPath    = Join-Path $rootPath 'sync.log'
            OldTip     = $oldTip
            RemoteTip  = $remoteTip
        }
    }

    function Invoke-SyncScript {
        param([pscustomobject]$Fixture)
        & pwsh -NoProfile -File $scriptUnderTest -RepoPath $Fixture.MirrorPath -StashDirty -LogPath $Fixture.LogPath | Out-Null
        return $LASTEXITCODE
    }
}

Describe 'Sync-RepoMain' {
    It 'fast-forwards a clean mirror that is behind the remote' {
        $fixture = New-MirrorBehindRemote -Name 'clean-behind'

        $exitCode = Invoke-SyncScript -Fixture $fixture

        $exitCode | Should -Be 0
        (Invoke-TestGit -RepoPath $fixture.MirrorPath -Arguments @('rev-parse', 'HEAD')) | Should -Be $fixture.RemoteTip
    }

    It 'adopts the remote tip when copied files already match the remote' {
        $fixture = New-MirrorBehindRemote -Name 'copied-match'
        Write-TestFile -RepoPath $fixture.MirrorPath -RelativePath 'tracked.txt' -Content "new`n"
        Write-TestFile -RepoPath $fixture.MirrorPath -RelativePath 'added.txt' -Content "added`n"

        $exitCode = Invoke-SyncScript -Fixture $fixture

        $exitCode | Should -Be 0
        (Invoke-TestGit -RepoPath $fixture.MirrorPath -Arguments @('rev-parse', 'HEAD')) | Should -Be $fixture.RemoteTip
        (Invoke-TestGit -RepoPath $fixture.MirrorPath -Arguments @('status', '--porcelain')) | Should -BeNullOrEmpty
        (Invoke-TestGit -RepoPath $fixture.MirrorPath -Arguments @('stash', 'list')) | Should -BeNullOrEmpty
    }

    It 'keeps the old tip and the copied file when a copied file differs from the remote' {
        $fixture = New-MirrorBehindRemote -Name 'copied-differs'
        Write-TestFile -RepoPath $fixture.MirrorPath -RelativePath 'tracked.txt' -Content "new`n"
        Write-TestFile -RepoPath $fixture.MirrorPath -RelativePath 'added.txt' -Content "local only`n"

        $exitCode = Invoke-SyncScript -Fixture $fixture

        $exitCode | Should -Be 1
        (Invoke-TestGit -RepoPath $fixture.MirrorPath -Arguments @('rev-parse', 'HEAD')) | Should -Be $fixture.OldTip
        [System.IO.File]::ReadAllText((Join-Path $fixture.MirrorPath 'added.txt')) | Should -Be "local only`n"
        [System.IO.File]::ReadAllText((Join-Path $fixture.MirrorPath 'tracked.txt')) | Should -Be "new`n"
    }
}
