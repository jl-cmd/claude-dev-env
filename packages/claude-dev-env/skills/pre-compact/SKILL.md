---
name: pre-compact
description: >-
  Composes a focus directive for `/compact [instructions]` and copies the full
  `/compact <directive>` string to the operator's clipboard so the next prompt
  is a single paste. The directive pins the session's load-bearing identifiers
  (branch, PR, HEAD, worktree, in-flight work, decisions, blockers, files in
  play, follow-ups) the next steps depend on, so the summarizer keeps them with
  high fidelity. It confirms the operator's intent for the next chat through a
  structured question first, then validates each identifier against its live
  source before stating it. Use when the user says `/pre-compact`, asks to prep for compaction, or
  asks to compose a focus directive for `/compact`.
disable-model-invocation: true
---

# Pre-Compact

`/compact [instructions]` accepts a focus directive that steers the
compaction-summary LLM toward high-signal content. This skill writes that
directive from the live session and copies the full `/compact <directive>`
string to the operator's clipboard.

**Announce at start:** "I'm composing your compact focus directive."

## Step 1 — Confirm the next-session intent

Before composing anything, ask the operator what they intend to work on in
the next chat. Do not infer it silently from the conversation, and do not
ask it raw — use `AskUserQuestion` with two to four options drawn from the
session context (the threads left open, the obvious next actions, the task
the operator last steered toward); the tool's free-text fallback covers
anything unlisted. The selected intent is the directive's forward task:
Step 2 scopes every field to what that intent needs, and the rendered
`In-flight` line states it.

## Step 2 — Read and validate the live session

Validate every identifier directly before stating it. Conversation context
goes stale within a session — a PR merges, HEAD advances, a worktree
advances to a newer commit — so confirm each value against its live source
at compose time rather than carrying it from memory. Run the command in
each field's Source column; for a PR, capture its merge state
(`gh pr view --json state,mergedAt`) and state `merged` or `open` from that
result, never from recollection. A value that cannot be confirmed against a
live source is not dropped silently — surface it to the operator via
`AskUserQuestion` to clarify (offer the candidate values found plus the
free-text fallback) and use the answer. Omit it only when the operator
chooses to skip it.

| Field | What to capture | Source |
|---|---|---|
| `branch` | Active branch name | `git branch --show-current` |
| `pr` | Active PR number and its merge state (open / merged), when one exists | `gh pr view --json number,state,mergedAt` |
| `head` | Short HEAD SHA (whatever `git rev-parse --short` outputs) | `git rev-parse --short HEAD` |
| `worktree` | Absolute path to the working directory | `pwd` |
| `in_flight` | One sentence describing what is being worked on right now | conversation |
| `decisions` | Architectural choices, library picks, tradeoffs settled this session | conversation |
| `blockers` | Failures observed, root causes identified, fixes pending | conversation |
| `files` | Paths the operator is iterating on (edited or read more than once) | conversation |
| `follow_ups` | What the user asked to be remembered or revisited | conversation |

A field whose value cannot be stated as a concrete identifier is omitted
from the directive.

Scope every field to what the Step 1 intent needs next. Compaction carries
forward the slice of session history the remaining work needs: capture a
`decision`, `blocker`, or `in_flight` detail when a next step relies on
it, and leave a detail the next steps do not touch (a settled question, a
resolved blocker, a path not taken) out by simply not listing it. When a
settled decision still constrains the next step, list its outcome as one
line, not the deliberation behind it.

## Step 3 — Render the directive

Render this exact shape, populating only the fields with concrete values:

```
Preserve:
- Branch: <name>
- PR: #<number>
- HEAD: <short-sha>
- Worktree: <path>
- In-flight: <one sentence>
- Decisions: <bullet per decision>
- Blockers: <bullet per blocker>
- Files: <path>, <path>, <path>
- Follow-ups: <bullet per follow-up>
```

The directive lists only what the next steps consume, so the summarizer
preserves that with high fidelity and compresses the rest of the trace on
its own — naming what to keep is a clearer instruction than enumerating
what to cut. Keep the list tight: a `Preserve:` block padded with finished
or out-of-scope context dilutes the summarizer's focus on what happens
next.

Source: [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
— "start by maximizing recall to ensure your compaction prompt captures
every relevant piece of information from the trace, then iterate to improve
precision by eliminating superfluous content."

## Step 4 — Copy `/compact <directive>` to the clipboard

Write the full `/compact <directive>` string to a temporary file via the
Write tool, then copy the file contents to the clipboard with PowerShell:

```
pwsh -NoProfile -Command "Get-Content -LiteralPath '<temp file path>' -Raw | Set-Clipboard"
```

`Get-Content -LiteralPath … -Raw` reads the file as a single string with
no wildcard expansion, and `Set-Clipboard` writes it verbatim. The intermediate file keeps the directive content out
of any shell-parsing path: session text passes through `Get-Content`
unmodified regardless of which characters it contains.

A reasonable temp path under `$env:TEMP` (Windows) or `$TMPDIR` (POSIX)
works; clean it up after the `Set-Clipboard` call returns.

## Step 5 — Hand off

Print this confirmation line to the operator:

> Copied `/compact …` to your clipboard. Paste it as your next prompt to
> compact this conversation with focus.

Then list up to the first three `Preserve:` bullets (or fewer when the
directive omits fields) inline so the operator can spot-check before
pasting.

---

## References

- `/compact [instructions]` — [Claude Code commands](https://code.claude.com/docs/en/commands)
- Compaction strategy — [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

## Folder map

- `SKILL.md` — hub. No companions.
