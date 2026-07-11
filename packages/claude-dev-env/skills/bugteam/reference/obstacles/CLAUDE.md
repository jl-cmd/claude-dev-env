# bugteam/reference/obstacles

Per-step obstacle guides for the `bugteam` skill. Each file addresses a specific failure point that can occur during an audit-fix loop. Load the matching file when a step fails rather than improvising a fix.

## Files

| File | Obstacle it addresses |
|---|---|
| `audit-assign-ids.md` | Assigning stable finding IDs in the audit output. |
| `audit-capture-excerpts.md` | Capturing code excerpts for each finding. |
| `audit-walk-categories.md` | Walking all A–P categories without skipping. |
| `audit-write-xml.md` | Writing the outcome XML from an audit pass. |
| `fix-append-summary.md` | Appending the fix summary to the outcome XML. |
| `fix-apply-fixes.md` | Applying code fixes from the finding list. |
| `fix-git-add-commit.md` | Staging and committing the fixed files. |
| `fix-git-push.md` | Pushing the fix commit to the remote branch. |
| `fix-post-reply.md` | Posting inline replies to finding threads on the PR. |
| `fix-publish-summary.md` | Publishing the loop summary to the PR. |
| `fix-py-compile.md` | Verifying Python syntax after fixes. |
| `fix-read-files.md` | Reading the files referenced in a finding. |
| `fix-resolve-thread.md` | Resolving a finding's review thread on GitHub. |
| `fix-test-suite.md` | Running the test suite and interpreting failures. |
| `fix-violation-count.md` | Counting open violations after a fix pass. |
| `fix-write-xml.md` | Writing the per-fix XML record. |
