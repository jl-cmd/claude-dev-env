---
name: recurring-queue-team
description: Run a six-seat recurring work queue through ordered size, conflict, and cleanup gates with Slack handoffs and a shared JSON ledger.
---

# Recurring queue team

Use six long-lived seats: `queue-coordinator`, `queue-labeler`, `queue-size-splitter`,
`queue-conflict-fixer`, `queue-cleanup-runner`, and `queue-ops`.

## Shared surface

- Slack channel: `SLACK_CHANNEL_ID`, through the user's configured Slack connector.
- Ledger: `~/.agents/workspaces/recurring-queue/team-ledger.json`.
- Workspace folders: `prompts/`, `worktrees/`, and `results/` beside the ledger.
- Local time: use the human's timezone for ledger timestamps and the daily 07:00–01:00 window.

Set `$env:SLACK_CHANNEL_ID` before using the skill. Use its value for every Slack
post and record its name in `slack_channel_env_var`.

Initialize the folders and copy `templates/team-ledger.json` to the ledger path when
the file is absent. Every seat reads the ledger before acting and updates only its
own keys after a meaningful step. Each item records `id`, `head`, `sizes`, `stage`,
`owner`, `outcome`, and local timestamps.

## TOKEN-LITE

Specialists use their own turns for status checks, lane-scoped ledger writes, short
Slack posts, and handoffs. Put heavy work in a prompt under `prompts/`, spawn the
team's configured executor, and collect its output under `results/`.

## Gates and product rules

Process gates in this order: Size, Conflict, Cleanup. Labeling runs in parallel.

1. Size Splitter sends green children onward after every item meets the size budget.
2. Conflict Fixer restacks a size-clear item on the live parent tip and posts
   `resolved — continue`.
3. Cleanup Runner starts with the stack bottom. A child stays draft until cleanup
   evidence exists for that exact child and it is mergeable and within budget.

The size budget decides routine splits. Merge authority stays with the human.
Ops confirms orphan and side-quest actions in Slack first. A wrongly ready item
returns to draft. Escalations name the lane owner in Slack; a direct agent message
may carry a priority steer or private correction. FYI messages need no reply.

## Slack rhythm

Prefix each post with the seat name. Post queue moves, handoffs, confirmations, and
corrections. Quiet ticks produce no post. Stagger scheduled specialist ticks within
the daily window. Event listeners may trigger on open, push, and settled checks.

A coarse keepalive posts only in the channel named by `$env:SLACK_CHANNEL_ID`:

> `[queue-coordinator] Keepalive — roles: Coordinator, Labeler, Size Splitter, Conflict Fixer, Cleanup Runner, Ops. Gates: Size → Conflict → Cleanup; Labeler runs in parallel. TOKEN-LITE: coordinate here and spawn heavy work.`

At setup, send every specialist the standing rules by direct message and collect a
short bake-in confirmation covering its profile and routine. Record confirmations
in the ledger. The coordinator watches Slack, fixes stale gate calls, directs the
owning seat to the next item, and stays quiet while the queue is aligned.
