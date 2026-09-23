# --fix

Runs after any level's review, once its findings are reported.

1. Take the findings the review just reported, most severe first.
2. Apply each one to the working tree. Keep each edit to the finding's own lines.
3. Make no commit and no push. The edits stay uncommitted for the user.
4. When a finding cannot be fixed, or the fix would change behavior the finding did not name, leave the code and mark it `skipped`.
5. Report the same findings again, each with an `outcome`: `fixed`, `no_change_needed` (the finding was wrong or already handled), or `skipped`.
