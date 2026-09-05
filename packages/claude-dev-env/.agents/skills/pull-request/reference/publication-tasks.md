# Pull request publication tasks

Register each line as one session task before starting the process. Complete
each task with `PASS`, `FAIL` plus file and line evidence, or `N/A` plus a
reason when the task is conditional. This file is a task seed catalog.

1. Resolve one repository, action, and selected author. For create, resolve the source branch, base, and head. For other actions, resolve one existing pull request target. Create actions publish drafts.
2. Invoke the required `pr-description-writer` for create or full body rewrite, then record its title and body file. Mark `N/A` for comment or review bodies that do not rewrite the pull request description.
3. Validate every title, body, artifact, and local path input. Reject inline body input.
4. Resolve the active managed root and run `<managed-root>/scripts/durable_post_lint.py` for the matching action. Record exit code `0` before credential lookup or network work.
5. Run `privacy-hygiene` before the GitHub post and record its clean result.
6. Upload binary evidence through `scripts/gh_artifact_upload.py`, replace local references with permanent URLs, and rerun the body linter. Mark `N/A` when no binary evidence exists.
7. Resolve the selected author in the child process environment and prove that the parent environment and global `gh` account remain unchanged.
8. Run `.agents/skills/pull-request/scripts/pull_request.py` for exactly one action: `create`, `edit`, `comment`, or `review`.
9. When the user selects a legacy state file, run `recover_legacy_author.py <exact-state-file> --confirm-inactive` for exactly that record. Preserve every other record and delete the selected record only after successful restore. Mark `N/A` otherwise.
10. Read back the remote pull request title, body, head SHA, draft state, and requested comment or review, then record the URL and number without credentials.
11. Mark every session task complete with evidence and report the action, remote URL, readback result, and any remaining blocker.
