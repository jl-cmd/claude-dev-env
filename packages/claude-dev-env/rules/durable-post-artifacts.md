# Durable Post Artifacts

**When this applies:** Any GitHub post that lives on the server — an issue, a pull request, a comment, or a review — created through `gh` (`gh pr create/comment/edit/review`, `gh issue create/comment/edit`) or a GitHub MCP post tool.

## Rule

A post lives forever. Job scratch directories, worktrees, and system temp folders do not — they are cleaned soon after the run that made them. So a post must never point at a path in that scratch. The moment the directory is cleaned, the reference breaks and the reader is left with a dead path.

Handle the two kinds of content differently:

- **Text data** (logs, tables, diffs, stack traces): paste the actual text inline in the post body. Do not link a scratch file that holds it.
- **Binary artifacts** (images, screenshots, archives): upload the file to the repository's durable `artifacts` release and link the permanent URL. Use the helper:

  ```
  python3 ~/.claude/scripts/gh_artifact_upload.py <file-path> <owner/repo>
  ```

  It ensures the repository has a prerelease tagged `artifacts`, uploads the file under a `YYYYMMDD_HHMMSS_<name>` asset name, and prints the permanent download URL. Put that URL in the post.

## Volatile paths that must not appear in a post body

- A job scratch directory (`.claude-editor/jobs/`)
- A worktree (`.claude/worktrees/`)
- A system temp location (`AppData\Local\Temp`, `%TEMP%`, `$env:TEMP`, `/tmp/`)
- The job scratch environment variable (`$CLAUDE_JOB_DIR`)

Both slash directions count.

The worktree and job-scratch entries count only as part of a machine-local path — a `/` or `\` sits right before them, as in a drive-letter path (`C:\Users\me\.claude\worktrees\wt\f.py`), a home path (`~/.claude/worktrees/wt`), or a POSIX absolute path (`/home/me/.claude-editor/jobs/j/log.txt`). A bare repo-relative mention of the directory name on its own — a quoted config constant or plain prose — reads as text and passes.

## Enforcement

The `volatile_path_in_post_blocker` PreToolUse hook reads the body of each `gh` post command and each GitHub MCP post call, scans it for these markers, and blocks the post when it finds one. For a `--body-file`, the hook reads the file and scans its contents, so writing the body to a temp file and passing it with `--body-file` stays allowed — what the hook rejects is a volatile path inside the text that gets posted.

## Why

A comment that cites an artifact under a job's tmp directory reads fine the moment it is posted and breaks a few minutes later, once the job is cleaned. Embedding text inline and linking binary artifacts to a durable release keeps every post readable for as long as it exists.
