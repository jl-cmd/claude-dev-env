[CmdletBinding()]
param(
    [Parameter(Position = 0, HelpMessage = 'GitHub pull request URL or owner/repo#number.')]
    [string] $PullRequest = '',
    [Parameter(HelpMessage = 'owner/repo when using -Number instead of a URL or owner/repo#number.')]
    [string] $Repository = '',
    [Parameter(HelpMessage = 'Pull request number; requires -Repository.')]
    [int] $Number = 0
)

$helpers_path = Join-Path $PSScriptRoot 'post-bugbot-run.helpers.ps1'
. $helpers_path

$LiteralBugbotRunBody = "bugbot run`n"

$invocation = Resolve-InvocationMode -PullRequestInput $PullRequest -RepositoryInput $Repository -NumberInput $Number
$scratch_temp_path = [System.IO.Path]::GetTempFileName()
$body_file_path = [System.IO.Path]::ChangeExtension($scratch_temp_path, '.md')

try {
    $utf8_without_byte_order_mark = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($body_file_path, $LiteralBugbotRunBody, $utf8_without_byte_order_mark)

    $null = Get-Command gh -ErrorAction Stop
    $argument_list = Build-GhArgumentList -Invocation $invocation -BodyFilePath $body_file_path
    & gh @argument_list
    if ($LASTEXITCODE -ne 0) {
        throw ('gh exited with code {0}.' -f $LASTEXITCODE)
    }
} finally {
    Remove-Item -LiteralPath $body_file_path -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $scratch_temp_path -Force -ErrorAction SilentlyContinue
}
