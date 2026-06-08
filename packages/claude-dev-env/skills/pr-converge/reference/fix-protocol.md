# Fix protocol

Single-PR (no `state.json`): production edits run in main session via
`Agent` (`subagent_type: "clean-coder"`). Multi-PR (`state.json`):
clean-coder teammate; orchestrator never edits inline. Hook handling
per [ground-rules.md](ground-rules.md).

**Multi-PR (`state.json`) teammate obligations** (plus TDD, commit, push):

- Replies inline on each addressed finding via
  `python scripts/post_fix_reply.py --owner <O> --repo <R> --pr-number <N> --in-reply-to <COMMENT_ID> --body <text>`
  (what changed + commit identifier), matching §Audit result → fix worker step 4 — **before** writing
  `state.json` and going idle.
- Writes `last_action: "fix_pushed"`, `current_head: <new SHA>`,
  `bugbot_clean_at: null`, `bugbot_down: false`, `phase: "BUGBOT"`,
  `status: "awaiting_bugbot"`, `last_updated` (ISO-8601 UTC) to
  `state.json` (per §Concurrency).
- Goes idle. Orchestrator spawns follow-up `general-purpose` agent for
  bugbot trigger and monitoring.

Orchestrator does not reply inline, trigger bugbot, or read repo source
files during fix phase in multi-PR mode.

### Single-PR fix workflow

**Single-PR (no `state.json`) — same gates, main session executor:**

Run every command below in the PR worktree (the working directory routed in
[per-tick.md § Step 1.5](per-tick.md)). The `git add`, `git commit`, and
`git push` act on the repo of the current working directory, so a cross-repo
PR's fix lands in the PR's repo only when the cwd is its worktree. A spawned
`clean-coder` does not inherit the lead's working directory — name the PR
worktree path in its prompt and direct it to edit, stage, and commit there,
matching the worktree-path handoff bugteam embeds in its fix worker's spawn
prompt.

- Read each referenced file:line.
- Write failing test first when finding has behavior to test. Pure doc /
  comment / naming nits with no behavior → straight to fix.
- **Implement** via `Agent` (`subagent_type: "clean-coder"`).
  Full-stop if `Agent` is unavailable.
- Stage affected files and create one new commit on existing branch:
  ```bash
git add <files> && git commit -m "fix(review): <brief summary>"
  ```
**Pre-commit gate:** honor hooks; full-stop on bypass.
- Push the new commit:
  ```bash
git push origin <BRANCH>
  ```
**Pre-push gate:** honor hooks; full-stop on bypass. Capture new HEAD
only after both gates pass; set `current_head`, `bugbot_clean_at = null`.
- Reply inline on each addressed comment thread using `python scripts/post_fix_reply.py`:

  ```
  python scripts/post_fix_reply.py --owner <O> --repo <R> --pr-number <N> --in-reply-to <COMMENT_ID> --body "Fixed in <SHA> — <what changed>"
  ```
- **After pushing a fix, always run Step 3 (`bugbot run`) in the same
  tick** regardless of phase. New commit **resets full convergence cycle**:
  prior bugbot clean and prior bugteam clean on older SHA do **not**
  count toward convergence on new `HEAD`. Must re-obtain bugbot CLEAN on
  `current_head`, then bugteam CLEAN on same `HEAD` with no
  intervening push. Re-triggering in same tick saves a wakeup cycle vs
  deferring Step 3.
