---
name: fixbugs
description: >-
  Fixes the bugs surfaced by the most recent /findbugs invocation by handing
  the findings to /agent-prompt, which authors a structured XML prompt and
  spawns a background sonnet implementer (via /agent-prompt) to apply every fix in one
  commit on the existing branch. Default scope: all severities. Optional
  argument filters by severity (e.g. /fixbugs P0, /fixbugs P0+P1).
  Triggers: '/fixbugs', 'fix all the bugs', 'apply the audit fixes',
  'implement the findbugs results'.
---

# Fixbugs

**Core principle:** A thin bridge between `/findbugs` (read-only audit) and `/agent-prompt` (structured prompt authoring + spawn). /fixbugs recovers the prior findings, packages them as a goal, and hands off. It does not author prompts itself, does not spawn agents directly, and does not run audits.

## When this skill applies

Right after `/findbugs` returned findings on the current branch and the user wants the bugs fixed without further triage. Bare `/fixbugs` defaults to all severities (P0 + P1 + P2). Argument-filtered invocations (e.g. `/fixbugs P0`, `/fixbugs P0+P1`, `/fixbugs P0 P1`) narrow the target set.

Refusal cases:

- **No findings in session.** Respond exactly: `No findings in this session. Run /findbugs first.` and stop.
- **Most recent /findbugs returned zero bugs.** Respond exactly: `No bugs to fix.` and stop.
- **Filter excludes every finding.** Respond: `No bugs match the filter <args>.` and stop.
- **Agent-prompt skill not installed.** Before Step 1, verify the `agent-prompt` skill is in the available skills list. If missing, respond: `agent-prompt skill not installed. /fixbugs hands off to it; install it first.` and stop.

## The Process

### Step 1: Recover the findings

Locate the most recent `/findbugs` output in the current conversation. For each finding, capture:

- Severity (`P0` / `P1` / `P2`)
- `file:line`
- Category (the A–J letter or category name `/findbugs` reported)
- One-sentence description as `/findbugs` wrote it

Apply the severity filter from `$ARGUMENTS` if present:

- `P0` → P0 only
- `P0+P1` or `P0 P1` → P0 and P1
- `P1` → P1 only
- absent → all severities

If the filtered set is empty, refuse per the refusal cases above.

### Step 2: Re-resolve PR scope

Re-establish the same PR target `/findbugs` used:

1. `gh pr view --json number,baseRefName,headRefName,url` from the working directory.
2. Fall back to `git merge-base HEAD origin/<default>` then `git diff <merge-base>...HEAD`.
3. Neither → respond `No PR or upstream diff. Cannot scope fixes.` and stop.

Capture: `<owner>/<repo>`, head branch, base branch, PR number, PR URL.

### Step 3: Hand off to /agent-prompt

Invoke the `agent-prompt` skill with a goal string of this exact shape:

```
Fix the following bugs surfaced by /findbugs on
<owner>/<repo> @ <head_branch> (PR #<number>, base <base_branch>):

[for each filtered finding, one bullet:]
- [<severity>] <file:line> (<category>): <description>

Deploy a background implementer (model: sonnet) to implement all fixes
in one commit on the existing branch and push. The implementer must **Read** the clean-coder agent file first (`~/.claude/agents/clean-coder.md`; Windows `%USERPROFILE%\.claude\agents\clean-coder.md`) and treat it as binding; on Cursor use `Task` + `generalPurpose` with that Read in the prompt when `clean-coder` is not a valid `Task` subtype. Constraints:
- Modify only the files referenced in the bug list above.
- Do NOT change the PR base, do NOT rebase, do NOT amend, do NOT --force.
- Do NOT skip git hooks (no --no-verify, no --no-gpg-sign).
- Use git add by explicit path; never `git add .` or `git add -A`.
- Preserve existing comments on lines you do not modify.
- Type hints on every signature you touch.

After push, report: commit SHA, per-file lines added/removed, hook output
summary, and confirmation that each bug above was addressed.
```

`/agent-prompt` then runs its own workflow end-to-end: prompt-generator authoring, Outcome preview, AskUserQuestion confirmation gate, background spawn. The confirmation gate is preserved — fixes are write operations and the user must approve the final XML before the agent runs.

### Step 4: Hand-off complete

`/fixbugs` produces no further output. `/agent-prompt` owns the visible chat from this point: the XML fence, the Outcome digest, the AskUserQuestion, and the spawn confirmation. Do not duplicate any of those, do not summarize them, do not add commentary.

## Output Format

When `/fixbugs` proceeds, the visible output is `/agent-prompt`'s output — nothing from `/fixbugs` itself.

When `/fixbugs` short-circuits (no findings, no PR, empty filter, zero bugs), the visible output is the single-line refusal message and nothing else.

## Constraints

- **Sequencing.** `/fixbugs` runs AFTER `/findbugs`. It does not perform audits.
- **Scope inheritance.** Fixes target only files referenced in the prior `/findbugs` findings — the PR diff scope. Do not expand to unrelated files.
- **No silent spawn.** `/agent-prompt`'s confirmation gate is preserved on every run.
- **One commit per `/fixbugs` run.** All filtered fixes batch into a single commit.
- **No `--force`, no `--amend`, no rebase, no base change.** Standard git workflow applies to the spawned agent.
- **Sonnet for the implementer.** Always pass `model: sonnet` to the spawn — keeps cost predictable and matches the agent's training fit for code edits.
- **Background spawn.** The user typed `/fixbugs` to delegate, not to wait. The agent runs in the background and notifies on completion.

## Examples

<example>
User: `/findbugs` → returns `1 P0 / 2 P1 / 0 P2`
User: `/fixbugs`
Claude: [recovers all 3 findings, resolves PR scope, invokes /agent-prompt with a goal targeting all 3 bugs; /agent-prompt presents the XML + Outcome digest + AskUserQuestion; on Launch it, the background sonnet implementer spawns]
</example>

<example>
User: `/findbugs` → returns `1 P0 / 2 P1 / 1 P2`
User: `/fixbugs P0+P1`
Claude: [filters to 3 findings (the P2 is dropped), hands the filtered set to /agent-prompt]
</example>

<example>
User: `/fixbugs` (no prior /findbugs in session)
Claude: `No findings in this session. Run /findbugs first.`
</example>

<example>
User: `/findbugs` → returns `0 P0 / 0 P1 / 0 P2`
User: `/fixbugs`
Claude: `No bugs to fix.`
</example>

<example>
User: `/findbugs` → returns `0 P0 / 0 P1 / 1 P2`
User: `/fixbugs P0`
Claude: `No bugs match the filter P0.`
</example>

## Why this design

Three skills, three responsibilities:

- `/findbugs` audits in a clean room, returns findings.
- `/fixbugs` packages findings as a goal, delegates.
- `/agent-prompt` authors the XML and spawns the agent (with confirmation).

Each skill stays small and reuses what already exists. `/fixbugs` adds value by recovering findings from chat, filtering by severity, and writing the goal in `/agent-prompt`'s expected shape — not by reimplementing prompt authoring or spawn logic. The `/agent-prompt` confirmation gate is non-negotiable because fixes write code, push to a PR, and are visible to reviewers; the friction is the safety.
