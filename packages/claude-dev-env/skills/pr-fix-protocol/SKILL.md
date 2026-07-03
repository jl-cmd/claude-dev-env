---
name: pr-fix-protocol
description: >-
  Applies reviewer findings to a PR as verified fixes and drives unresolved
  review threads to zero: executor choice (clean-coder spawn or multi-PR
  teammate with a worktree-path handoff), the shared 13-step fix sequence
  (TDD, one commit, fast-forward push), an atomic reply-and-resolve per
  thread, the unresolved-thread sweep hard gate (is_resolved == false is the
  only filter), and post-push state resets. Invoked by PR-loop orchestrators
  (pr-converge, autoconverge, bugteam, qbug, copilot-review) whenever a
  reviewer reports findings or unresolved threads exist; not for ad-hoc "fix
  this bug" requests outside a PR review loop.
---

# PR Fix Protocol

**Core principle:** a finding is addressed only when the fix is pushed, the thread carries a reply, and the thread is resolved — as one unit of work. Anything less leaves a convergence gate stalled.

## How callers invoke this

- **Skill-capable contexts** (a lead session with the `Skill` tool): `Skill({skill: "pr-fix-protocol", args: "--skill <caller> --pr <URL> --worktree <path> [findings payload or 'sweep']"})`.
- **Fallback** (a subagent or teammate without the `Skill` tool): the caller's spawn prompt says "Read `~/.claude/skills/pr-fix-protocol/SKILL.md` and apply it with the parameters below."

The caller passes: its identity, the PR scope, the PR worktree path, this round's findings (or `sweep` for a thread sweep with no fresh findings), and its post-push obligations (which clean-SHA state fields to reset, which reviewers to re-trigger).

## Executor choice

- **Single-PR loops** (no shared `state.json`): the lead spawns `Agent(subagent_type: "clean-coder")` to write the fix. Full-stop if `Agent` is unavailable. A spawned clean-coder does not inherit the lead's working directory — name the PR worktree path in its prompt and direct it to edit, stage, and commit there.
- **Multi-PR orchestration** (shared `state.json`): a per-PR clean-coder teammate owns edits, replies, and state writes; the orchestrator never edits inline. The teammate obligations (reply before writing state, state fields, idle handoff) live in the calling skill's multi-PR reference.

Run every git command in the PR worktree — `git add`, `git commit`, and `git push` act on the repo of the current working directory, so a cross-repo PR's fix lands in the PR's repo only when the cwd is its worktree.

## The fix sequence

Follow the shared 13-step sequence in [`_shared/pr-loop/fix-protocol.md`](../../_shared/pr-loop/fix-protocol.md) exactly: read each file:line, capture the pre-fix SHA and contents, TDD where the finding has behavior, apply narrowly, `py_compile`, post-fix self-audit, stage by explicit path, one commit, fast-forward push, then reply + resolve atomically per thread. Its Constraints section (narrow scope, no `--no-verify`, preserve helpers) binds every executor.

**Reply transport:** the GitHub MCP `add_reply_to_pull_request_comment` is primary. `python "$HOME/.claude/skills/pr-converge/scripts/post_fix_reply.py" --owner <O> --repo <R> --pr-number <N> --in-reply-to <COMMENT_ID> --body "Fixed in <SHA> — <what changed>"` is the fallback for script-only contexts and multi-PR teammates. Both carry the body shape from [`_shared/pr-loop/audit-reply-template.md`](../../_shared/pr-loop/audit-reply-template.md). For body-only findings with no inline thread, post a top-level review reply citing the new HEAD SHA.

**Thread resolution:** `pull_request_review_write(method="resolve_thread", threadId=<PRRT node id>)` right after each reply. Harvest thread node ids (`PRRT_…`) from `get_review_comments` at fetch time.

## The unresolved-thread sweep (hard gate)

No caller advances a phase, records a clean SHA, or marks a PR ready while ANY unresolved review thread exists on the PR.

```
pull_request_read(method="get_review_comments") → filter threads where is_resolved == false
```

- The filter is purely `is_resolved == false`. Author, anchor commit, and `is_outdated` are all irrelevant to the count.
- `is_outdated` is informational, not a skip flag: GitHub marks a thread outdated when its anchor line changed, but the concern can still apply to current HEAD (the fix may have moved, not landed). Verify each outdated thread against current HEAD like any other.
- Per unresolved thread: verify the concern against current HEAD. The concern holds → fix (this protocol) → reply → resolve. The concern does not hold on current HEAD → reply-with-note explaining why → resolve.
- Code changed during the sweep → push and hand control back to the caller's re-entry phase. Only resolutions, no code → re-run the sweep without resetting caller state.

## Post-push obligations

Every push through this protocol:

1. Re-resolve `current_head` (`git rev-parse HEAD` locally; the PR `get` call for API-visible state).
2. Reset the caller-named clean-SHA fields to null (`bugbot_clean_at`, `code_review_clean_at`, `copilot_clean_at` — whichever the caller tracks). A new HEAD invalidates every prior clean.
3. Re-trigger reviewers per the caller's parameter (for Cursor Bugbot, the `reviewer-gates` Bugbot flow; for Copilot, the caller's request step). Audit-family callers (`bugteam`, `qbug`) skip re-triggering — their next loop iteration is the reviewer.

## Gotchas

- **Reply-then-resolve, atomic per thread.** Batching all replies before any resolves, or yielding to the orchestrator between the two, leaves threads half-addressed when a run dies mid-loop.
- **An unchanged HEAD after step 11 means no commit landed** — exit `stuck — could not address findings` rather than reporting the findings as fixed.
- **A resolved thread with no reply reads as dismissed.** Reviewers (and the humans reading the PR) need the one-paragraph explanation the template carries.

## Folder map

- `SKILL.md` — this file. The step sequence, reply template, and payload shapes live in `_shared/pr-loop/` (`fix-protocol.md`, `audit-reply-template.md`, `gh-payloads.md`); the reply fallback script lives in `pr-converge/scripts/`.
