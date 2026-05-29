# Ground rules

- **Append commits.** Each tick adds at most one fix commit.
- **Bugbot findings on current SHA mean fix-then-push-then-`bugbot run`,
  not another naked `bugbot run`.**
- **All `*_clean_at`, `merge_state_status`, and `bugbot_down` reset on every push.**
- **`bugbot run` comment is load-bearing.** Literal phrase exactly —
  empirically the only re-trigger Cursor Bugbot recognizes.
- **Production edits go through `clean-coder`, except `/code-review --fix`.**
  The lead never hand-edits production files. Every bugbot, bugteam,
  Copilot, or Claude finding spawns `Agent(subagent_type="clean-coder")` to
  implement the fix. The CODE_REVIEW phase is the one exception: `/code-review
  --fix` applies its own findings to the working tree, which the next
  BUGBOT/BUGTEAM cycle re-reviews after the loop resets.
- **Adapt when reality contradicts on-disk state.** If `state.json`,
  `git`, or `gh` disagree with live PR, escalate as hard blocker per
  [stop-conditions.md](stop-conditions.md).
