# pr-converge scripts

Thin Python wrappers around the gh CLI calls the skill makes per tick. Centralizing them lets the skill body reference one script path per action and keeps the gh-paginate and gh-body-file rules enforced in one place.

Scripts that target a specific repository are invoked as `python "${CLAUDE_SKILL_DIR}/scripts/<name>.py" --owner OWNER --repo REPO --number NUMBER ...`. `view_pr_context.py` relies on `gh`'s default repository context and takes no `--owner` / `--repo` / `--number` flags. Scripts return non-zero on subprocess failure and surface gh's stderr through `subprocess.CalledProcessError`.

## Scripts

### `view_pr_context.py`

Returns the per-tick PR context as JSON.

```bash
python "${CLAUDE_SKILL_DIR}/scripts/view_pr_context.py"
```

Output: `{"number", "url", "headRefOid", "baseRefName", "headRefName", "isDraft"}`. Wraps `gh pr view --json number,url,headRefOid,baseRefName,headRefName,isDraft`.

### `fetch_bugbot_reviews.py`

Fetches every Cursor Bugbot review on the PR newest-first, classified per body content.

```bash
python "${CLAUDE_SKILL_DIR}/scripts/fetch_bugbot_reviews.py" \
  --owner <OWNER> --repo <REPO> --number <NUMBER>
```

Output: JSON array of `{review_id, commit_id, submitted_at, body, classification}` where `classification` is `"dirty"` (body matches `Cursor Bugbot has reviewed your changes and found <N> potential issue`) or `"clean"`. Uses `--paginate --slurp` and flattens pages in Python — required by `../../../rules/gh-paginate.md` because `gh --paginate --jq` runs the filter per-page (gh CLI #10459).

### `fetch_bugbot_inline_comments.py`

Fetches unaddressed Cursor Bugbot inline comments for the **newest submitted Bugbot review** on the requested ``--commit`` SHA (matches ``pull_request_review_id`` to the review returned by ``fetch_bugbot_reviews.py`` so stale inline threads from an older Bugbot review on the same SHA are ignored).

```bash
python "${CLAUDE_SKILL_DIR}/scripts/fetch_bugbot_inline_comments.py" \
  --owner <OWNER> --repo <REPO> --number <NUMBER> --commit <CURRENT_HEAD>
```

Output: JSON array of `{comment_id, commit_id, path, line, body}`. Uses the same `--paginate --slurp` pattern as `fetch_bugbot_reviews.py`.

### `resolve_pr_head.py`

Returns the current HEAD SHA of the PR. Wraps the single-object endpoint `repos/<owner>/<repo>/pulls/<number>` which is not paginated, so `gh`'s built-in `--jq .head.sha` is safe here (see "Single-object endpoints" in `../../../rules/gh-paginate.md`).

```bash
python "${CLAUDE_SKILL_DIR}/scripts/resolve_pr_head.py" \
  --owner <OWNER> --repo <REPO> --number <NUMBER>
```

Output: the SHA on stdout, trailing newline.

### `trigger_bugbot.py`

Posts the literal `bugbot run` re-trigger comment via `gh pr comment --body-file` (per `../../../rules/gh-body-file.md` — passing the body inline can corrupt backticks). Writes and removes the temp body file internally.

```bash
python "${CLAUDE_SKILL_DIR}/scripts/trigger_bugbot.py" \
  --owner <OWNER> --repo <REPO> --number <NUMBER>
```

Output: the comment URL from gh on stdout.

### `mark_pr_ready.py`

Marks a draft PR as ready for review. Convergence action invoked when both bugbot and bugteam are clean against the same HEAD.

```bash
python "${CLAUDE_SKILL_DIR}/scripts/mark_pr_ready.py" \
  --owner <OWNER> --repo <REPO> --number <NUMBER>
```

### `reply_to_inline_comment.py`

Posts an inline reply to a PR review comment. Reply body is sourced from a caller-supplied file via `gh api ... -F body=@<path>` (per `../../../rules/gh-body-file.md`).

```bash
python "${CLAUDE_SKILL_DIR}/scripts/reply_to_inline_comment.py" \
  --owner <OWNER> --repo <REPO> --number <NUMBER> \
  --comment-id <COMMENT_ID> --body-file <PATH_TO_REPLY_MD>
```

Output: the new reply id from gh's JSON response, on stdout.

## Tests

Each script has a sibling `test_<name>.py`. Run them all with:

```bash
python -m pytest packages/claude-dev-env/skills/pr-converge/scripts/ -v
```
