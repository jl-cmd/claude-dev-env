# Ground rules

- **Append commits.** Each tick adds at most one fix commit.
- **Bugbot findings on current SHA mean fix-then-push-then-`bugbot run`,
  not another naked `bugbot run`.**
- **All `*_clean_at` and `merge_state_status` reset on every push.**
- **`bugbot run` comment is load-bearing.** Literal phrase exactly —
  empirically the only re-trigger Cursor Bugbot recognizes.
- **Honor pre-push and pre-commit hooks.** Read output, fix the cause,
  retry. Full-stop on bypass.
- **Adapt when reality contradicts on-disk state.** If `state.json`,
  `git`, or `gh` disagree with live PR, escalate as hard blocker per
  [stop-conditions.md](stop-conditions.md).
