# pre-compact

Composes the `/compact` focus directive for the current session and copies the full `/compact <directive>` string to the clipboard.

**Trigger:** `/pre-compact` or any request to "prep for compaction".

## Purpose

`/compact [instructions]` accepts a directive that steers the compaction summarizer toward high-signal content. This skill builds that directive from live session state — validated against the actual git branch, PR, HEAD SHA, and worktree path — and delivers it ready to paste.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | The complete skill — five steps (confirm intent, validate live state, write directive, copy to clipboard, hand off). No companion files. |

## How the skill runs

1. Asks the operator what they plan to work on next (via `AskUserQuestion`).
2. Reads each identifier live (`git branch --show-current`, `git rev-parse --short HEAD`, `gh pr view`, `pwd`) rather than relying on conversation context.
3. Produces a `Preserve:` block scoped to what the next task actually needs.
4. Writes the full `/compact <directive>` string to a temp file, copies it via `pwsh Set-Clipboard`, then cleans up.

`disable-model-invocation: true` is set — this skill runs without a secondary LLM call; it is pure procedural text assembly.
