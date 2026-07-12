Set-StrictMode -Version Latest

BeforeAll {
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

    function New-CliConfigFile {
        param(
            [string]$Directory,
            [string]$Email,
            [string]$AccountUuid
        )
        New-Item -ItemType Directory -Path $Directory -Force | Out-Null
        $cliConfigPath = Join-Path $Directory '.claude.json'
        $cliConfigJson = [pscustomobject]@{
            oauthAccount = [pscustomobject]@{
                emailAddress = $Email
                accountUuid  = $AccountUuid
            }
        } | ConvertTo-Json
        [System.IO.File]::WriteAllText($cliConfigPath, $cliConfigJson, [System.Text.Encoding]::UTF8)
        return $cliConfigPath
    }

    function New-ProfileConfigFile {
        param(
            [string]$ProfileDirectory,
            [string]$LastKnownAccountUuid
        )
        New-Item -ItemType Directory -Path $ProfileDirectory -Force | Out-Null
        $profileConfigPath = Join-Path $ProfileDirectory 'config.json'
        $profileConfigJson = [pscustomobject]@{
            lastKnownAccountUuid = $LastKnownAccountUuid
        } | ConvertTo-Json
        [System.IO.File]::WriteAllText($profileConfigPath, $profileConfigJson, [System.Text.Encoding]::UTF8)
    }
}

Describe 'Test-NoiseEmail' {
    It 'rejects the placeholder example domain' {
        (Test-NoiseEmail -Email 'noreply@example.com') | Should -Be $true
    }

    It 'keeps a legitimate local part that contains the substring example' {
        (Test-NoiseEmail -Email 'sam.exampleson@company.com') | Should -Be $false
    }

    It 'keeps a legitimate domain that merely contains the substring example' {
        (Test-NoiseEmail -Email 'person@example-labs.io') | Should -Be $false
    }

    It 'still rejects sentry and anthropic noise addresses' {
        (Test-NoiseEmail -Email 'someone@sentry.io') | Should -Be $true
        (Test-NoiseEmail -Email 'billing@anthropic.com') | Should -Be $true
    }

    It 'rejects a sentry ingest subdomain address' {
        (Test-NoiseEmail -Email 'abc@o123.ingest.sentry.io') | Should -Be $true
    }

    It 'keeps an address whose local part merely contains sentry.io' {
        (Test-NoiseEmail -Email 'sentry.io.reports@realcompany.com') | Should -Be $false
    }

    It 'keeps an address whose domain merely starts with anthropic' {
        (Test-NoiseEmail -Email 'user@anthropic-partner.com') | Should -Be $false
    }
}

Describe 'Get-EmailCandidatesFromProfile' {
    It 'recovers an email persisted as UTF-16 in Session Storage' {
        $profileDirectory = Join-Path $TestDrive 'utf16-profile'
        New-Utf16StorageFile -ProfileDirectory $profileDirectory -StoreName 'Session Storage' -FileName '000003.ldb' -EmailText 'user@host.com'

        $candidateEmails = @(Get-EmailCandidatesFromProfile -ProfileDirectory $profileDirectory)

        ($candidateEmails -contains 'user@host.com') | Should -Be $true
    }

    It 'recovers an email stored as UTF-8 JSON in the sentry store' {
        $profileDirectory = Join-Path $TestDrive 'utf8-profile'
        New-Utf8StorageFile -ProfileDirectory $profileDirectory -StoreName 'sentry' -FileName 'events.json' -JsonText '{"user":{"email":"person@company.com"}}'

        $candidateEmails = @(Get-EmailCandidatesFromProfile -ProfileDirectory $profileDirectory)

        ($candidateEmails -contains 'person@company.com') | Should -Be $true
    }

    It 'keeps a single UTF-16 email whose local part contains the substring example' {
        $profileDirectory = Join-Path $TestDrive 'example-profile'
        New-Utf16StorageFile -ProfileDirectory $profileDirectory -StoreName 'Session Storage' -FileName '000004.ldb' -EmailText 'sam.exampleson@company.com'

        $candidateEmails = @(Get-EmailCandidatesFromProfile -ProfileDirectory $profileDirectory)

        $candidateEmails.Count | Should -Be 1
        $candidateEmails[0] | Should -Be 'sam.exampleson@company.com'
    }

    It 'counts the same email recovered with differing casing across stores as one candidate' {
        $profileDirectory = Join-Path $TestDrive 'mixed-case-profile'
        New-Utf16StorageFile -ProfileDirectory $profileDirectory -StoreName 'Session Storage' -FileName '000012.ldb' -EmailText 'Desktop@Company.com'
        New-Utf16StorageFile -ProfileDirectory $profileDirectory -StoreName 'IndexedDB' -FileName '000013.ldb' -EmailText 'desktop@company.com'

        $candidateEmails = @(Get-EmailCandidatesFromProfile -ProfileDirectory $profileDirectory)

        $candidateEmails.Count | Should -Be 1
    }

    It 'refuses to recover an email whose local part is glued to an adjacent boundary byte' {
        $profileDirectory = Join-Path $TestDrive 'prefix-polluted-profile'
        New-Utf16StorageFile -ProfileDirectory $profileDirectory -StoreName 'Session Storage' -FileName '000010.ldb' -EmailText '.desktop@company.com'

        $candidateEmails = @(Get-EmailCandidatesFromProfile -ProfileDirectory $profileDirectory)

        ($candidateEmails -contains '.desktop@company.com') | Should -Be $false
        $candidateEmails.Count | Should -Be 0
    }
}

Describe 'Resolve-SessionAccount' {
    It 'returns exit code 2 when the CLI config file is absent' {
        $cliConfigPath = Join-Path $TestDrive 'absent-cli/.claude.json'

        $sessionAccount = Resolve-SessionAccount -CliConfigPath $cliConfigPath -ProfileDirectory ''

        $sessionAccount.ExitCode | Should -Be 2
        $sessionAccount.ErrorMessage | Should -Match 'CLI config not found'
    }

    It 'returns exit code 2 when the CLI config is not valid JSON' {
        $configDirectory = Join-Path $TestDrive 'unparseable-cli'
        New-Item -ItemType Directory -Path $configDirectory -Force | Out-Null
        $cliConfigPath = Join-Path $configDirectory '.claude.json'
        [System.IO.File]::WriteAllText($cliConfigPath, 'this is not json {', [System.Text.Encoding]::UTF8)

        $sessionAccount = Resolve-SessionAccount -CliConfigPath $cliConfigPath -ProfileDirectory ''

        $sessionAccount.ExitCode | Should -Be 2
        $sessionAccount.ErrorMessage | Should -Match 'Failed to parse CLI config'
    }

    It 'returns exit code 2 when the CLI config top level is a JSON string' {
        $configDirectory = Join-Path $TestDrive 'scalar-cli'
        New-Item -ItemType Directory -Path $configDirectory -Force | Out-Null
        $cliConfigPath = Join-Path $configDirectory '.claude.json'
        [System.IO.File]::WriteAllText($cliConfigPath, '"just a string"', [System.Text.Encoding]::UTF8)

        $sessionAccount = Resolve-SessionAccount -CliConfigPath $cliConfigPath -ProfileDirectory ''

        $sessionAccount.ExitCode | Should -Be 2
        $sessionAccount.ErrorMessage | Should -Match 'not a JSON object'
    }

    It 'returns exit code 2 when the CLI config top level is a JSON array' {
        $configDirectory = Join-Path $TestDrive 'array-cli'
        New-Item -ItemType Directory -Path $configDirectory -Force | Out-Null
        $cliConfigPath = Join-Path $configDirectory '.claude.json'
        [System.IO.File]::WriteAllText($cliConfigPath, '[1, 2, 3]', [System.Text.Encoding]::UTF8)

        $sessionAccount = Resolve-SessionAccount -CliConfigPath $cliConfigPath -ProfileDirectory ''

        $sessionAccount.ExitCode | Should -Be 2
        $sessionAccount.ErrorMessage | Should -Match 'not a JSON object'
    }

    It 'returns exit code 2 when the desktop profile config top level is not a JSON object' {
        $cliConfigPath = New-CliConfigFile -Directory (Join-Path $TestDrive 'scalar-profile-cli') -Email 'cli@company.com' -AccountUuid 'uuid-cli'
        $profileDirectory = Join-Path $TestDrive 'scalar-profile'
        New-Item -ItemType Directory -Path $profileDirectory -Force | Out-Null
        $profileConfigPath = Join-Path $profileDirectory 'config.json'
        [System.IO.File]::WriteAllText($profileConfigPath, '42', [System.Text.Encoding]::UTF8)

        $sessionAccount = Resolve-SessionAccount -CliConfigPath $cliConfigPath -ProfileDirectory $profileDirectory

        $sessionAccount.ExitCode | Should -Be 2
        $sessionAccount.ErrorMessage | Should -Match 'not a JSON object'
    }

    It 'returns exit code 2 when the CLI config lacks oauthAccount fields' {
        $configDirectory = Join-Path $TestDrive 'incomplete-cli'
        New-Item -ItemType Directory -Path $configDirectory -Force | Out-Null
        $cliConfigPath = Join-Path $configDirectory '.claude.json'
        [System.IO.File]::WriteAllText($cliConfigPath, '{"oauthAccount":{"emailAddress":"","accountUuid":""}}', [System.Text.Encoding]::UTF8)

        $sessionAccount = Resolve-SessionAccount -CliConfigPath $cliConfigPath -ProfileDirectory ''

        $sessionAccount.ExitCode | Should -Be 2
        $sessionAccount.ErrorMessage | Should -Match 'missing oauthAccount'
    }

    It 'reports the cli-config account with exit code 0 when no desktop profile is set' {
        $cliConfigPath = New-CliConfigFile -Directory (Join-Path $TestDrive 'cli-only') -Email 'cli@company.com' -AccountUuid 'uuid-cli'

        $sessionAccount = Resolve-SessionAccount -CliConfigPath $cliConfigPath -ProfileDirectory ''

        $sessionAccount.ExitCode | Should -Be 0
        $sessionAccount.Source | Should -Be 'cli-config'
        $sessionAccount.Email | Should -Be 'cli@company.com'
    }

    It 'returns exit code 2 when the desktop profile config is absent' {
        $cliConfigPath = New-CliConfigFile -Directory (Join-Path $TestDrive 'missing-profile-cli') -Email 'cli@company.com' -AccountUuid 'uuid-cli'
        $profileDirectory = Join-Path $TestDrive 'profile-without-config'
        New-Item -ItemType Directory -Path $profileDirectory -Force | Out-Null

        $sessionAccount = Resolve-SessionAccount -CliConfigPath $cliConfigPath -ProfileDirectory $profileDirectory

        $sessionAccount.ExitCode | Should -Be 2
        $sessionAccount.ErrorMessage | Should -Match 'Desktop profile config not found'
    }

    It 'reports the matching desktop-profile account with exit code 0' {
        $cliConfigPath = New-CliConfigFile -Directory (Join-Path $TestDrive 'match-cli') -Email 'cli@company.com' -AccountUuid 'uuid-shared'
        $profileDirectory = Join-Path $TestDrive 'match-profile'
        New-ProfileConfigFile -ProfileDirectory $profileDirectory -LastKnownAccountUuid 'uuid-shared'

        $sessionAccount = Resolve-SessionAccount -CliConfigPath $cliConfigPath -ProfileDirectory $profileDirectory

        $sessionAccount.ExitCode | Should -Be 0
        $sessionAccount.Source | Should -Be 'desktop-profile (matches cli-config)'
        $sessionAccount.Email | Should -Be 'cli@company.com'
    }

    It 'recovers the desktop account email with exit code 0 when exactly one candidate differs from the cli account' {
        $cliConfigPath = New-CliConfigFile -Directory (Join-Path $TestDrive 'differ-cli') -Email 'cli@company.com' -AccountUuid 'uuid-cli'
        $profileDirectory = Join-Path $TestDrive 'differ-profile'
        New-ProfileConfigFile -ProfileDirectory $profileDirectory -LastKnownAccountUuid 'uuid-desktop'
        New-Utf16StorageFile -ProfileDirectory $profileDirectory -StoreName 'Session Storage' -FileName '000005.ldb' -EmailText 'desktop@company.com'

        $sessionAccount = Resolve-SessionAccount -CliConfigPath $cliConfigPath -ProfileDirectory $profileDirectory

        $sessionAccount.ExitCode | Should -Be 0
        $sessionAccount.Email | Should -Be 'desktop@company.com'
        $sessionAccount.AccountUuid | Should -Be 'uuid-desktop'
        $sessionAccount.Source | Should -Be 'desktop-profile (differs from cli-config)'
        $sessionAccount.CliEmail | Should -Be 'cli@company.com'
    }

    It 'recovers the desktop email even when the known cli email also lingers in profile storage' {
        $cliConfigPath = New-CliConfigFile -Directory (Join-Path $TestDrive 'lingering-cli') -Email 'cli@company.com' -AccountUuid 'uuid-cli'
        $profileDirectory = Join-Path $TestDrive 'lingering-profile'
        New-ProfileConfigFile -ProfileDirectory $profileDirectory -LastKnownAccountUuid 'uuid-desktop'
        New-Utf16StorageFile -ProfileDirectory $profileDirectory -StoreName 'Session Storage' -FileName '000008.ldb' -EmailText 'desktop@company.com'
        New-Utf16StorageFile -ProfileDirectory $profileDirectory -StoreName 'IndexedDB' -FileName '000009.ldb' -EmailText 'cli@company.com'

        $sessionAccount = Resolve-SessionAccount -CliConfigPath $cliConfigPath -ProfileDirectory $profileDirectory

        $sessionAccount.ExitCode | Should -Be 0
        $sessionAccount.Email | Should -Be 'desktop@company.com'
        $sessionAccount.AccountUuid | Should -Be 'uuid-desktop'
        $sessionAccount.CliEmail | Should -Be 'cli@company.com'
    }

    It 'fails safe with exit code 1 rather than reporting a prefix-polluted email as the account' {
        $cliConfigPath = New-CliConfigFile -Directory (Join-Path $TestDrive 'polluted-cli') -Email 'cli@company.com' -AccountUuid 'uuid-cli'
        $profileDirectory = Join-Path $TestDrive 'polluted-resolve-profile'
        New-ProfileConfigFile -ProfileDirectory $profileDirectory -LastKnownAccountUuid 'uuid-desktop'
        New-Utf16StorageFile -ProfileDirectory $profileDirectory -StoreName 'Session Storage' -FileName '000011.ldb' -EmailText '.desktop@company.com'

        $sessionAccount = Resolve-SessionAccount -CliConfigPath $cliConfigPath -ProfileDirectory $profileDirectory

        $sessionAccount.ExitCode | Should -Be 1
        $sessionAccount.Email | Should -BeNullOrEmpty
        $sessionAccount.ErrorMessage | Should -Match 'no candidate email was recovered'
    }

    It 'returns exit code 1 when the desktop account differs but no candidate email is recovered' {
        $cliConfigPath = New-CliConfigFile -Directory (Join-Path $TestDrive 'none-cli') -Email 'cli@company.com' -AccountUuid 'uuid-cli'
        $profileDirectory = Join-Path $TestDrive 'none-profile'
        New-ProfileConfigFile -ProfileDirectory $profileDirectory -LastKnownAccountUuid 'uuid-desktop'

        $sessionAccount = Resolve-SessionAccount -CliConfigPath $cliConfigPath -ProfileDirectory $profileDirectory

        $sessionAccount.ExitCode | Should -Be 1
        $sessionAccount.ErrorMessage | Should -Match 'no candidate email was recovered'
    }

    It 'returns exit code 1 when the desktop account differs and multiple candidate emails are found' {
        $cliConfigPath = New-CliConfigFile -Directory (Join-Path $TestDrive 'multi-cli') -Email 'cli@company.com' -AccountUuid 'uuid-cli'
        $profileDirectory = Join-Path $TestDrive 'multi-profile'
        New-ProfileConfigFile -ProfileDirectory $profileDirectory -LastKnownAccountUuid 'uuid-desktop'
        New-Utf16StorageFile -ProfileDirectory $profileDirectory -StoreName 'Session Storage' -FileName '000006.ldb' -EmailText 'first@company.com'
        New-Utf16StorageFile -ProfileDirectory $profileDirectory -StoreName 'IndexedDB' -FileName '000007.ldb' -EmailText 'second@company.com'

        $sessionAccount = Resolve-SessionAccount -CliConfigPath $cliConfigPath -ProfileDirectory $profileDirectory

        $sessionAccount.ExitCode | Should -Be 1
        $sessionAccount.ErrorMessage | Should -Match 'multiple candidate emails'
    }
}

Describe 'Write-AccountResult' {
    It 'writes the account fields as text without cli lines when no CliEmail is given' {
        $AsJson = $false
        $textLines = Write-AccountResult -Email 'a@company.com' -AccountUuid 'uuid-a' -Source 'cli-config'
        $joinedText = $textLines -join "`n"

        $joinedText | Should -Match 'Account: a@company.com'
        $joinedText | Should -Match 'AccountUuid: uuid-a'
        $joinedText | Should -Match 'Source: cli-config'
        $joinedText | Should -Not -Match 'CliAccount:'
    }

    It 'writes the cli account lines as text when a CliEmail is given' {
        $AsJson = $false
        $textLines = Write-AccountResult -Email 'd@company.com' -AccountUuid 'uuid-d' -Source 'desktop-profile (differs from cli-config)' -CliEmail 'c@company.com' -CliAccountUuid 'uuid-c'
        $joinedText = $textLines -join "`n"

        $joinedText | Should -Match 'Account: d@company.com'
        $joinedText | Should -Match 'CliAccount: c@company.com'
        $joinedText | Should -Match 'CliAccountUuid: uuid-c'
    }

    It 'emits a JSON object carrying the account contract fields when AsJson is set' {
        $AsJson = $true
        $jsonOutput = Write-AccountResult -Email 'd@company.com' -AccountUuid 'uuid-d' -Source 'desktop-profile (differs from cli-config)' -CliEmail 'c@company.com' -CliAccountUuid 'uuid-c' -AsJson:$AsJson
        $parsedResult = $jsonOutput | ConvertFrom-Json

        $parsedResult.account | Should -Be 'd@company.com'
        $parsedResult.accountUuid | Should -Be 'uuid-d'
        $parsedResult.source | Should -Be 'desktop-profile (differs from cli-config)'
        $parsedResult.cliAccount | Should -Be 'c@company.com'
        $parsedResult.cliAccountUuid | Should -Be 'uuid-c'
    }
}
