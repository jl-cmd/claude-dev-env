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

Output: JSON array of `{review_id, commit_id, submitted_at, state, body, classification}` where `classification` is `"dirty"` (body matches `Cursor Bugbot has reviewed your changes and found <N> potential issue`) or `"clean"`. Uses `--paginate --slurp` and flattens pages in Python — required by `../../../rules/gh-paginate.md` because `gh --paginate --jq` runs the filter per-page (gh CLI issue 10459). Login filter is a case-insensitive substring match on `cursor` (handles login-shape divergence between review-level and inline-comment endpoints).

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

### `check_pr_mergeability.py`

Returns the mergeability state of the current PR as JSON. Wraps `gh pr view --json mergeable,mergeStateStatus,headRefOid` (single-object endpoint — no pagination needed). Used by the convergence gate to detect base-branch conflicts (`mergeStateStatus == "DIRTY"` / `mergeable == "CONFLICTING"`) before flipping the PR ready.

```bash
python "${CLAUDE_SKILL_DIR}/scripts/check_pr_mergeability.py" \
--owner <OWNER> --repo <REPO> --number <NUMBER>
```

Output: `{"mergeable", "mergeStateStatus", "headRefOid"}`.

### `fetch_copilot_reviews.py`

Fetches every Copilot reviewer (`copilot-pull-request-reviewer[bot]`) review on the PR newest-first, classified per the review's `state` field.

```bash
python "${CLAUDE_SKILL_DIR}/scripts/fetch_copilot_reviews.py" \
  --owner <OWNER> --repo <REPO> --number <NUMBER>
```

Output: JSON array of `{review_id, commit_id, submitted_at, state, body, classification}` where `classification` is `"clean"` for `state == "APPROVED"`, `"dirty"` for `state == "CHANGES_REQUESTED"`, and `"dirty"` for `state == "COMMENTED"` with a non-empty body. Uses `--paginate --slurp` and flattens pages in Python — required by `../../../rules/gh-paginate.md`. Login filter is a case-insensitive substring match on `copilot` (handles the divergence where Copilot reviews come from `copilot-pull-request-reviewer[bot]` but its inline comments are authored by `Copilot`).

### `fetch_copilot_inline_comments.py`

Fetches unaddressed Copilot inline comments for the **newest submitted Copilot review** on the requested ``--commit`` SHA (matches ``pull_request_review_id`` to the review returned by ``fetch_copilot_reviews.py`` so stale inline threads from an older Copilot review on the same SHA are ignored).

```bash
python "${CLAUDE_SKILL_DIR}/scripts/fetch_copilot_inline_comments.py" \
  --owner <OWNER> --repo <REPO> --number <NUMBER> --commit <CURRENT_HEAD>
```

Output: JSON array of `{comment_id, commit_id, path, line, body}`. Uses the same `--paginate --slurp` pattern as `fetch_copilot_reviews.py`.

### `request_copilot_review.py`

Requests a Copilot review on the current PR via `gh api -X POST repos/{owner}/{repo}/pulls/{number}/requested_reviewers -f 'reviewers[]=copilot-pull-request-reviewer[bot]'`. The `[bot]` suffix is load-bearing per `../../copilot-review/SKILL.md` — `Copilot`, `copilot`, and `github-copilot` all silently no-op.

```bash
python "${CLAUDE_SKILL_DIR}/scripts/request_copilot_review.py" \
  --owner <OWNER> --repo <REPO> --number <NUMBER>
```

Output: none on success (gh's stdout is suppressed); `subprocess.CalledProcessError` on failure.

### `fetch_claude_reviews.py`

Fetches every Claude reviewer-bot review on the PR newest-first, classified per the review's `state` field. Mirror of `fetch_copilot_reviews.py` for an Anthropic Claude PR review bot (e.g. `claude[bot]`, `claude-code[bot]`, or any login containing `claude`).

```bash
python "${CLAUDE_SKILL_DIR}/scripts/fetch_claude_reviews.py" \
  --owner <OWNER> --repo <REPO> --number <NUMBER>
```

Output: JSON array of `{review_id, commit_id, submitted_at, state, body, classification}` — same shape and same state-based classification rules as `fetch_copilot_reviews.py`. Login filter is a case-insensitive substring match on `claude`.

### `fetch_claude_inline_comments.py`

Fetches unaddressed Claude inline comments for the **newest submitted Claude review** on the requested `--commit` SHA (matches `pull_request_review_id` to the review returned by `fetch_claude_reviews.py` so stale inline threads from an older Claude review on the same SHA are ignored).

```bash
python "${CLAUDE_SKILL_DIR}/scripts/fetch_claude_inline_comments.py" \
  --owner <OWNER> --repo <REPO> --number <NUMBER> --commit <CURRENT_HEAD>
```

Output: JSON array of `{comment_id, commit_id, path, line, body}`. Same `--paginate --slurp` pattern.

## Shared modules

The reviewer fetch scripts share their fetch and classification logic via two internal modules. Entry-point scripts (`fetch_bugbot_reviews.py`, `fetch_copilot_reviews.py`, `fetch_claude_reviews.py` and their inline-comment counterparts) are thin wrappers — they import a per-reviewer spec, call the shared core, and shape argparse / JSON output.

### `reviewer_specs.py`

Defines the `ReviewerSpec` frozen dataclass (two fields: `login_filter_substring` and `classify_review`) plus three module-level instances: `bugbot_spec`, `copilot_spec`, `claude_spec`. The state-based classifier used by Copilot and Claude is built via the shared `_make_state_based_classifier` factory; Bugbot has its own body-regex classifier because Bugbot uses `state == "COMMENTED"` for both clean and dirty reviews and only the body distinguishes them.

Spec instances use lowercase names because they are frozen dataclass values rather than scalar configuration constants — keeps them out of the `UPPER_SNAKE` constants-location rule that requires module-level constants outside `config/` to be hoisted there.

### `reviewer_fetch_core.py`

Exports `fetch_reviewer_reviews(spec, ...)` and `fetch_reviewer_inline_comments(spec, ..., all_reviews=...)`. The inline-comments function takes pre-fetched reviews as an argument rather than fetching them internally, so each entry-point script keeps its own patchable `fetch_X_reviews` function for tests that mock the reviews fetch on the entry-point module.

The core enforces the gh-paginate contract (`--paginate --slurp` + Python JSON flattening, never `gh --jq` for cross-page operations) and the case-insensitive substring login filter in one place.

## Tests

Each script has a sibling `test_<name>.py`. Run them all with:

```bash
python -m pytest packages/claude-dev-env/skills/pr-converge/scripts/ -v
```
