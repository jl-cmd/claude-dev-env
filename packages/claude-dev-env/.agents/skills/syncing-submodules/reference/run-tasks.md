# Run task seeds

- Resolve the requested repository path.
- Execute `scripts/sync_parent_pointer.py` for that path.
- Record the exit code and parse the single JSON result.
- Fix any reported failure and rerun until the command exits 0.
- Read back the parent pointer and unrelated staged paths when the status is `updated`.
- Report the result fields.
- Route an open pull request URL to `/pr-title-description` or report the URL when that skill is missing.
