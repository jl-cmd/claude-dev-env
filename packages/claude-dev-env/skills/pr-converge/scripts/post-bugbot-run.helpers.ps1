function Resolve-InvocationMode {
    param([string] $PullRequestInput, [string] $RepositoryInput, [int] $NumberInput)

    if ($NumberInput -gt 0) {
        if ([string]::IsNullOrWhiteSpace($RepositoryInput)) {
            throw 'When -Number is set, -Repository must be owner/repo (for example jl-cmd/claude-code-config).'
        }
        return @{ Mode = 'RepoNumber'; Repository = $RepositoryInput; Number = $NumberInput }
    }

    $trimmed = $PullRequestInput.Trim()
    if (-not [string]::IsNullOrWhiteSpace($trimmed)) {
        return @{ Mode = 'Uri'; PullRequest = $trimmed }
    }

    throw 'Provide a pull request URL, owner/repo#number as the first argument, or -Repository with -Number.'
}

function Build-GhArgumentList {
    param([hashtable] $Invocation, [string] $BodyFilePath)

    if ($Invocation.Mode -eq 'RepoNumber') {
        return @(
            'pr', 'comment',
            $Invocation.Number.ToString(),
            '-R', $Invocation.Repository,
            '--body-file', $BodyFilePath
        )
    }

    $trimmed = $Invocation.PullRequest
    if ($trimmed -match '^https://github\.com/[^/]+/[^/]+/pull/\d+$') {
        return @('pr', 'comment', $trimmed, '--body-file', $BodyFilePath)
    }

    if ($trimmed -match '^([^/]+)/([^/#]+)#(\d+)$') {
        $owner = $Matches[1]
        $repository_name = $Matches[2]
        $pull_number = $Matches[3]
        return @(
            'pr', 'comment',
            $pull_number,
            '-R', ('{0}/{1}' -f $owner, $repository_name),
            '--body-file', $BodyFilePath
        )
    }

    throw ('Unrecognized PullRequest "{0}". Use a https://github.com/owner/repo/pull/NN URL or owner/repo#NN.' -f $trimmed)
}
