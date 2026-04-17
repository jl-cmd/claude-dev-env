---
name: bugteam
description: >-
  Runs an autonomous audit-and-fix loop on the current branch's PR using a
  Claude Code agent team — bugfind teammate (code-quality-agent, clean-room
  audit) and bugfix teammate (clean-coder, sonnet fix) — until the audit
  returns zero bugs or a 10-loop safety cap is reached. One up-front
  confirmation authorizes the entire cycle. Each audit teammate is spawned
  fresh per loop to prevent anchoring bias. Wraps the cycle with project
  permission grant/revoke. Requires CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
  and Claude Code v2.1.32+. Triggers: '/bugteam', 'run the bug team',
  'auto-fix the PR until clean', 'loop audit and fix'.
---

# Bugteam

**Core principle:** A Claude Code **agent team** runs the audit-and-fix loop until convergence. The bugfind teammate audits clean-room (own context window, no chat history); the bugfix teammate addresses each audit's findings; both spawn fresh per loop. A 10-loop hard cap prevents runaway cost. Project permissions are granted at session start and revoked at session end.

> **Source:** [Anthropic — Orchestrate teams of Claude Code sessions](https://code.claude.com/docs/en/agent-teams). Direct quote: *"Each teammate has its own context window. When spawned, a teammate loads the same project context as a regular session: CLAUDE.md, MCP servers, and skills. It also receives the spawn prompt from the lead. The lead's conversation history does not carry over."* That isolation is the design's whole point — independent context per teammate enforces the clean-room property automatically.

> **Why agent teams, not parallel subagents:** Subagents return their results into the lead's context, which accumulates across loops. Agent team teammates are independent sessions with their own context windows and do not pollute the lead. The lead can shut down + respawn each loop, guaranteeing every audit starts fresh. Per the docs: *"Use subagents when you need quick, focused workers that report back. Use agent teams when teammates need to share findings, challenge each other, and coordinate on their own."* For this skill, the independent-context property is what we need; parallel subagents fail the clean-room requirement.

## When this skill applies

User wants automated convergence on a clean PR without babysitting each step. Typed `/bugteam` once = full authorization for up to 10 audit cycles and the corresponding fix commits.

Refusal cases:

- **Agent teams not enabled.** Check `claude config get env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` and `~/.claude/settings.json`. If neither sets it to `"1"`, respond: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 not set. /bugteam requires the agent teams feature. See https://code.claude.com/docs/en/agent-teams#enable-agent-teams.` and stop.
- **Claude Code version too old.** Run `claude --version`. If older than v2.1.32, respond: `Claude Code v<version> is older than the v2.1.32 minimum for agent teams. Upgrade first.` and stop.
- **No PR or upstream diff.** Respond exactly: `No PR or upstream diff. /bugteam needs a target.` and stop.
- **Working tree dirty with uncommitted changes the user did not stage.** Respond: `Uncommitted changes detected. Stash, commit, or revert before /bugteam.` and stop. Reason: the fix teammate will commit the working tree, mixing user-uncommitted work into automated fixes.

## The Process

### Step 0: Grant project permissions (mandatory, runs once)

Before spawning any teammates, grant the team session write access to the project's `.claude/**` tree:

```bash
python scripts/grant_project_claude_permissions.py
```

The script reads `Path.cwd()` and writes idempotent allow rules into `~/.claude/settings.json`. Run from the project root. If it fails (non-zero exit), surface the error and stop — do not proceed without the grant.

This is the FIRST action of every `/bugteam` invocation, before any team creation, before any agent spawn. The corresponding revoke runs at Step 5 regardless of how the cycle exits.

### Step 1: Resolve PR scope (once, persisted across loops)

Same resolution path as `/findbugs`:

1. `gh pr view --json number,baseRefName,headRefName,url` from the working directory.
2. Fall back to `git merge-base HEAD origin/<default>` then `git diff <merge-base>...HEAD`.
3. Neither → refuse per the refusal cases above.

Capture: `<owner>/<repo>`, head branch, base branch, PR number, PR URL. This scope persists across every loop — `/bugteam` never re-prompts the user mid-cycle.

### Step 2: Create the agent team

This session is the **team lead**. Create a team using the agent teams feature. Per the docs: *"After enabling agent teams, tell Claude to create an agent team and describe the task and the team structure you want in natural language. Claude creates the team, spawns teammates, and coordinates work based on your prompt."*

Team specification:

- **Team name:** `bugteam-pr-<number>` (or `bugteam-<head-branch>` if no PR)
- **Roles defined up front (spawned per loop, not at team creation):**
  - `bugfind` — uses subagent type `code-quality-agent`, model sonnet
  - `bugfix` — uses subagent type `clean-coder`, model sonnet
- **Display mode:** inherit user's default (`teammateMode` in `~/.claude.json`); do not override.

Reference subagent definitions by name when spawning. Per the docs: *"When spawning a teammate, you can reference a subagent type from any subagent scope: project, user, plugin, or CLI-defined. This lets you define a role once... and reuse it both as a delegated subagent and as an agent team teammate."*

Initialize loop state:

```
loop_count = 0
last_action = "fresh"
last_findings = None
audit_log = []
starting_sha = git rev-parse HEAD
team_name = "bugteam-pr-<number>"
```

### Step 3: The cycle

Repeat until an exit condition fires:

1. Increment `loop_count`. If `loop_count > 10`, exit reason = `cap reached`.
2. Decide the next action:
   - `last_action in {"fresh", "fixed"}` → run **AUDIT**
   - `last_action == "audited"` and `last_findings.total > 0` → run **FIX**
   - `last_action == "audited"` and `last_findings.total == 0` → exit reason = `converged`
3. Execute the chosen action (see action specs below).
4. Update `last_action`, `last_findings`, and append to `audit_log`.
5. Print a one-line progress marker so the user can watch convergence:
   - After audit: `Loop <N> audit: <P0>P0 / <P1>P1 / <P2>P2`
   - After fix: `Loop <N> fix: commit <sha7> (<files_changed> files, +<add>/-<del>)`
6. Loop.

### AUDIT action (clean-room teammate, fresh per loop)

Capture a fresh PR diff for this loop:

```
gh pr diff <number> -R <owner>/<repo> > .bugteam-loop-<N>.patch
```

Spawn a NEW `bugfind` teammate for this loop using the `code-quality-agent` subagent type. The teammate is fresh: no prior loop's findings, no chat history, no inherited audit context. Per the docs: *"The lead's conversation history does not carry over."* — and we further guarantee independence by spawning a new teammate per loop rather than reusing one.

After the audit reports findings, **shut down the bugfind teammate**: `Ask the bugfind teammate to shut down`. Per the docs: *"The lead sends a shutdown request. The teammate can approve, exiting gracefully, or reject with an explanation."* If the teammate rejects shutdown, force-shut by failing the team and starting Step 5 cleanup with exit reason = `error: bugfind teammate refused shutdown`.

The teammate's spawn prompt uses the same clean-room XML pattern `/findbugs` uses:

- `<context>` — repo, branch, base branch, PR URL only
- `<scope>` — diff path + "Audit only lines added or modified in the diff" rule
- `<bug_categories>` — the same 10 categories A–J `/findbugs` uses
- `<constraints>` — read-only, file:line citations required, open questions for ambiguities
- `<output_format>` — P0/P1/P2 with file:line traces + verified-clean coverage

**Forbid all conversation references** in the agent prompt. No "as we discussed," "the earlier issue," "fix from the prior loop," "you previously identified." Each loop's audit agent has no idea other loops happened. This is the design's whole point.

Parse the agent's response into a structured findings record: `{P0: [...], P1: [...], P2: [...], total: N}`.

`last_action = "audited"`. `last_findings = parsed`. Append `(loop=N, action="audit", counts={P0,P1,P2}, sha=current_HEAD)` to `audit_log`.

### FIX action (fresh teammate, only sees latest audit)

Spawn a NEW `bugfix` teammate for this loop using the `clean-coder` subagent type, model sonnet. The teammate sees ONLY the most recent audit's findings — no prior-loop findings, no prior-loop fix history, no chat history.

After the fix completes (commit pushed or no-change reported), **shut down the bugfix teammate** the same way as the bugfind shutdown.

Prompt skeleton:

```xml
<context>
  <repo>owner/repo</repo>
  <branch>head</branch>
  <base_branch>base</base_branch>
  <pr_url>url</pr_url>
</context>

<bugs_to_fix>
  [for each P0/P1/P2 finding from last_findings:]
  <bug priority="P_" file="path:line" category="<letter>">
    <description>...</description>
  </bug>
</bugs_to_fix>

<constraints>
  - Modify only files referenced in bugs_to_fix.
  - One commit on the existing branch, then push.
  - Do NOT rebase, amend, --force, or change the PR base.
  - Do NOT skip git hooks.
  - git add by explicit path; never `git add .` or `git add -A`.
  - Preserve existing comments on lines you do not modify.
  - Type hints on every signature you touch.
</constraints>

<execution>
  Read each referenced file before editing. Apply each fix. Run
  `python -m py_compile` (or language-equivalent) on every modified file.
  git add by path. git commit with a message summarizing the bugs fixed.
  git push. Report commit SHA, per-file lines added/removed.
</execution>
```

Verify the fix actually committed and pushed:

- `git rev-parse HEAD` after fix should differ from before
- The new HEAD should be present on `origin/<branch>` (`git fetch origin <branch> && git rev-parse origin/<branch>` matches HEAD)

If `git rev-parse HEAD` did not change, exit reason = `stuck — bugfix teammate could not address findings`. The fix teammate ran but produced no commit; further loops will not converge.

`last_action = "fixed"`. Append `(loop=N, action="fix", commit_sha=new_HEAD, files_changed, lines_added, lines_removed)` to `audit_log`.

### Step 4: Tear down the team and clean working tree

When the cycle exits (any reason):

1. **Clean up the team as the lead.** Per the docs: *"When you're done, ask the lead to clean up: 'Clean up the team'. This removes the shared team resources. When the lead runs cleanup, it checks for active teammates and fails if any are still running, so shut them down first."* The lead is THIS session — call cleanup directly. If any teammate is still alive (e.g., from an aborted shutdown), shut it down first.
2. Delete every `.bugteam-loop-*.patch` from the working directory.

### Step 5: Revoke project permissions (mandatory, runs always)

After team cleanup completes — including on error, cap-reached, or stuck exits — run:

```bash
python scripts/revoke_project_claude_permissions.py
```

This removes the allow rules and additionalDirectories entry that Step 0 added. Revoke is non-negotiable: leaving the grant in place means future sessions inherit elevated permissions on this project's `.claude/**` tree without the user opting in. Run this even if Step 4 cleanup partially failed; surface the cleanup error separately in the final report.

### Step 6: Print the final report

```
/bugteam exit: <converged | cap reached | stuck | error>
Loops: <loop_count>
Starting commit: <starting_sha7>
Final commit: <current_HEAD_sha7>
Net change: <total_files> files, +<total_add>/-<total_del>

Loop log:
  1 audit: 3P0 2P1 0P2
  1 fix:   commit a1b2c3d (4 files, +12/-3)
  2 audit: 1P0 0P1 0P2
  2 fix:   commit e4f5g6h (1 file, +2/-1)
  3 audit: 0P0 0P1 0P2 → converged
```

If exit = `cap reached`, name the remaining bug count and recommend `/findbugs` for human triage. If exit = `stuck`, name which findings the fix agent could not resolve. If exit = `error`, surface the error and the loop number.

## Constraints

- **Agent teams required, not parallel subagents.** The skill MUST use Claude Code's agent teams feature (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`). Spawning `code-quality-agent` and `clean-coder` as parallel subagents from the lead's context = fail; the clean-room property requires independent teammate sessions.
- **Grant before any spawn, revoke before any return.** Step 0 grants project `.claude/**` permissions; Step 5 revokes. Both are mandatory. Revoke runs on every exit path including error, cap-reached, and stuck.
- **Fresh teammate per loop.** Both bugfind and bugfix are spawned new each loop and shut down after their action. Reusing a teammate across loops accumulates context inside that teammate's window — defeats clean-room.
- **One up-front confirmation = whole cycle.** No mid-loop AskUserQuestion. The `/bugteam` invocation IS the authorization.
- **10-loop hard cap.** Counted as audits performed. Worst case = 10 audits + 10 fixes = 20 teammate spawns + 20 shutdowns.
- **Clean-room audits, every loop.** Never pass conversation context, prior findings, prior commits, or prior loop history into a bugfind teammate's spawn prompt.
- **Targeted fixes.** Each fix teammate sees ONLY the most recent audit's findings. Prior loops are invisible to the fix teammate.
- **Sonnet for both teammates.** Predictable cost, fits-purpose for code work.
- **No clean-room exception for fix.** The fix teammate legitimately needs the findings; that is not anchoring bias, that is the input contract.
- **One commit per fix action.** Loops produce one commit per loop, not one per bug.
- **No `--force`, no `--amend`, no rebase, no base change** at any point.
- **Lead-only cleanup.** Per the docs: *"Always use the lead to clean up. Teammates should not run cleanup because their team context may not resolve correctly, potentially leaving resources in an inconsistent state."* This session is the lead; teammates never call cleanup.
- **Cleanup `.bugteam-loop-*.patch` on exit.** Working directory ends clean.

## Examples

<example>
User: `/bugteam`
Claude: [resolves PR #42, runs loop]

`Loop 1 audit: 1P0 / 2P1 / 0P2`
`Loop 1 fix: commit a1b2c3d (3 files, +18/-7)`
`Loop 2 audit: 0P0 / 1P1 / 0P2`
`Loop 2 fix: commit e4f5g6h (1 file, +5/-2)`
`Loop 3 audit: 0P0 / 0P1 / 0P2 → converged`

`/bugteam exit: converged`
`Loops: 3`
`Starting commit: 9d8c7b6`
`Final commit: e4f5g6h`
`Net change: 4 files, +23/-9`
</example>

<example>
User: `/bugteam`
Claude: [runs 10 loops without convergence]

`Loop 10 audit: 0P0 / 1P1 / 2P2`

`/bugteam exit: cap reached`
`Loops: 10`
`Remaining: 0P0 / 1P1 / 2P2 — run /findbugs for human triage`
</example>

<example>
User: `/bugteam`
Claude: [loop 4 fix produces no commit]

`Loop 4 fix: clean-coder reported no changes (could not address remaining bugs)`
`/bugteam exit: stuck`
`Unresolved findings (3): src/cache.py:88 (P0 race condition); ...`
</example>

<example>
User: `/bugteam` (no PR or upstream diff)
Claude: `No PR or upstream diff. /bugteam needs a target.`
</example>

<example>
User: `/bugteam` (uncommitted changes in working tree)
Claude: `Uncommitted changes detected. Stash, commit, or revert before /bugteam.`
</example>

## Why this design

The three sibling skills compose, but `/bugteam` solves a problem they cannot solve in sequence:

- `/findbugs` audits once and stops.
- `/fixbugs` fixes the findings of one audit and stops.
- A human-driven `/findbugs` → `/fixbugs` → `/findbugs` → `/fixbugs` cycle works but requires the user to drive it.

`/bugteam` automates that cycle. The clean-room property is preserved by spawning a fresh audit agent each loop with no inherited context — every audit is independent of the prior loop's verdict. The 10-loop cap is the safety: pathological cases (audit agent oscillating, fix agent regressing) cannot run away.

The single up-front confirmation is the explicit trade — `/bugteam` is more autonomous than `/findbugs`+`/fixbugs` chained manually. The user accepts that autonomy by typing the command. Stop conditions and the loop log give the user full visibility on exit.
