Set-StrictMode -Version Latest

$scriptUnderTest = Join-Path (Split-Path -Parent $PSScriptRoot) 'Get-SessionAccount.ps1'
. $scriptUnderTest

function New-Utf16StorageFile {
    param(
        [string]$ProfileDirectory,
        [string]$StoreName,
        [string]$FileName,
        [string]$EmailText
    )
    $storeDirectory = Join-Path $ProfileDirectory $StoreName
    New-Item -ItemType Directory -Path $storeDirectory -Force | Out-Null
    $emailBytes = [System.Text.Encoding]::Unicode.GetBytes("`0`0$EmailText`0`0")
    $filePath = Join-Path $storeDirectory $FileName
    [System.IO.File]::WriteAllBytes($filePath, $emailBytes)
}

function New-Utf8StorageFile {
    param(
        [string]$ProfileDirectory,
        [string]$StoreName,
        [string]$FileName,
        [string]$JsonText
    )
    $storeDirectory = Join-Path $ProfileDirectory $StoreName
    New-Item -ItemType Directory -Path $storeDirectory -Force | Out-Null
    $filePath = Join-Path $storeDirectory $FileName
    [System.IO.File]::WriteAllText($filePath, $JsonText, [System.Text.Encoding]::UTF8)
}

Describe 'Test-NoiseEmail' {
    It 'rejects the placeholder example domain' {
        (Test-NoiseEmail -Email 'noreply@example.com') | Should Be $true
    }

    It 'keeps a legitimate local part that contains the substring example' {
        (Test-NoiseEmail -Email 'sam.exampleson@company.com') | Should Be $false
    }

    It 'keeps a legitimate domain that merely contains the substring example' {
        (Test-NoiseEmail -Email 'person@example-labs.io') | Should Be $false
    }

    It 'still rejects sentry and anthropic noise addresses' {
        (Test-NoiseEmail -Email 'someone@sentry.io') | Should Be $true
        (Test-NoiseEmail -Email 'billing@anthropic.com') | Should Be $true
    }
}

Describe 'Get-EmailCandidatesFromProfile' {
    It 'recovers an email persisted as UTF-16 in Session Storage' {
        $profileDirectory = Join-Path $TestDrive 'utf16-profile'
        New-Utf16StorageFile -ProfileDirectory $profileDirectory -StoreName 'Session Storage' -FileName '000003.ldb' -EmailText 'user@host.com'

        $candidateEmails = @(Get-EmailCandidatesFromProfile -ProfileDirectory $profileDirectory)

        ($candidateEmails -contains 'user@host.com') | Should Be $true
    }

    It 'recovers an email stored as UTF-8 JSON in the sentry store' {
        $profileDirectory = Join-Path $TestDrive 'utf8-profile'
        New-Utf8StorageFile -ProfileDirectory $profileDirectory -StoreName 'sentry' -FileName 'events.json' -JsonText '{"user":{"email":"person@company.com"}}'

        $candidateEmails = @(Get-EmailCandidatesFromProfile -ProfileDirectory $profileDirectory)

        ($candidateEmails -contains 'person@company.com') | Should Be $true
    }

    It 'keeps a single UTF-16 email whose local part contains the substring example' {
        $profileDirectory = Join-Path $TestDrive 'example-profile'
        New-Utf16StorageFile -ProfileDirectory $profileDirectory -StoreName 'Session Storage' -FileName '000004.ldb' -EmailText 'sam.exampleson@company.com'

        $candidateEmails = @(Get-EmailCandidatesFromProfile -ProfileDirectory $profileDirectory)

        $candidateEmails.Count | Should Be 1
        $candidateEmails[0] | Should Be 'sam.exampleson@company.com'
    }
}
