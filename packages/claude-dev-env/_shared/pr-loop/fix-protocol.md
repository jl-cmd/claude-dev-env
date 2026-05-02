# Fix protocol

## Sequence

1. **Read each referenced file:line** before editing. The repo enforces read-before-edit at the tool layer.
2. **Capture pre-fix SHA:** `git rev-parse HEAD`. Store as `pre_fix_sha`.
3. **Capture pre-fix file contents** for every file this fix will touch. Used in step 8 for the post-fix self-audit diff.
4. **TDD where applicable:** when the finding has behavior to test, write a failing test first; for pure doc, comment, or naming nits with no behavior, fix directly.
5. **Apply each fix:**
   - Preserve existing comments on lines left unchanged
   - Add complete type hints on every signature touched
   - Use positive framing in any new prose (no banned negatives)
6. **Validate each modified Python file:** `python -m py_compile <path>`. Halt on syntax error; fix and re-run.
7. **Compute fix diff:** the diff between pre-fix and post-fix file contents for every modified file.
8. **Post-fix self-audit:** follow [`audit-contract.md`](audit-contract.md) post-fix self-audit sequence. Internal iteration cap: 3. Three rounds with fresh findings → exit `stuck: post-fix audit not converging`. Only when `gate_findings` empty AND `post_fix_findings` empty → proceed to git add.
9. **Stage by explicit path:** `git add <path>` for each modified file. Avoid `git add -A` and `git add .`.
10. **Create one commit** summarizing the fixed findings. Let every git hook run. When a hook blocks the commit, capture stderr, mark every finding in this loop `status=hook_blocked`, and move to the next iteration without retrying this loop.
11. **Push fast-forward:** `git push origin <branch>`. Verify `git fetch origin <branch> && git rev-parse origin/<branch>` matches `HEAD`.
12. **Reply inline** on each finding's comment thread using the [`gh-payloads.md`](gh-payloads.md) reply shape. Reply body is one of:
    - `Fixed in <short_sha>`
    - `Could not address this loop: <one-line reason>`
    - `Hook blocked the fix commit: <one-line summary>`
13. **Re-trigger reviewer** when the calling workflow specifies. Workflow-specific:
    - `pr-converge`: post `bugbot run` issue comment after every push (Cursor Bugbot)
    - `monitor-many`: post `bugbot run` issue comment AND call `requested_reviewers` API for Copilot
    - `bugteam` / `qbug`: skip — Claude itself is the reviewer; the next loop iteration audits

## Stuck detection

After step 11, when `git rev-parse HEAD` is unchanged from `pre_fix_sha`, the fix produced no commit. Exit reason: `stuck — could not address findings`. Record unresolved findings as `{file, line, severity, title, reason}` quadruples.

## Constraints

- Edit only files reachable from the PR diff's scope.
- Append commits; the branch stays linear (one commit per fix loop, fast-forward push only).
- No comment deletion on lines left unchanged.
- No `--no-verify`. Hook rejections flag real underlying issues worth investigating.
