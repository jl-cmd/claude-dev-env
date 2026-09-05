# GitHub post input rules

## When this applies

Use this rule for a GitHub issue, pull request, comment, or review created
through `gh` or a GitHub MCP post tool.

## Rule

A post remains after the job ends. Job scratch directories, worktrees, and
system temp folders do not. Do not put a path from one of those directories in
a post.

Handle text and binary content differently:

- **Text data** such as logs, tables, diffs, and stack traces belongs inline in
  the post body. Do not link a scratch file that holds text data.
- **Binary artifacts** such as images, screenshots, and archives belong in the
  repository's durable `artifacts` release. Use the helper:

  ```
  python3 ~/.claude/scripts/gh_artifact_upload.py <file-path> <owner/repo>
  ```

  The helper creates the `artifacts` prerelease when needed, uploads the file
  under a `YYYYMMDD_HHMMSS_<name>` asset name, and prints a permanent download
  URL. Put that URL in the post.

## Volatile paths that must not appear in a post body

- A job scratch directory: `.claude-profile-a/jobs/`
- A worktree: `.claude/worktrees/`
- A system temp location: `AppData\\Local\\Temp`, `%TEMP%`, `$env:TEMP`, or
  `/tmp/`
- The job scratch environment variable: `$CLAUDE_JOB_DIR`

Both slash directions count. The path rule applies when a slash or backslash
precedes a marker, or when a path segment follows it. A standalone directory
name does not form a path.

## Validation

Run `scripts/durable_post_lint.py` before the server write. Pass the matching
action and body file. Use `pr-create`, `pr-edit`, `pr-comment`, `pr-review`,
`issue-create`, `issue-edit`, `issue-comment`, or `github-mcp-post`.

The linter reads the body file and reports a volatile local path without
printing the body. Fix the body and rerun the linter before posting.
