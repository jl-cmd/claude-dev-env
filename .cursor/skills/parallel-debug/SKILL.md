---
name: parallel-debug
description: Runs the pr-converge loop for jl-cmd/claude-code-config using AHK auto-continue pacing. Activate when the user says "parallel-debug" or asks to run the pr-converge convergence loop in Cursor.
---

Run the bugbot + bugteam convergence loop across all open PRs in `jl-cmd/claude-code-config`, paced by an AHK auto-typer instead of `ScheduleWakeup` (which is unavailable in Cursor sessions). End every response with `Awaiting next "continue" tick.`

## Objective

Converge every open PR in `jl-cmd/claude-code-config` to back-to-back clean: bugbot CLEAN + bugteam CLEAN at the same HEAD. Mark each converged PR ready for review with `gh pr ready`. Stop when all open PRs have converged or hit a hard blocker.

## One-Time Setup

Run these two commands at the start of the session before any tick work:

**1. Resolve the Cursor window PID:**
```bash
pwsh -NoProfile -ExecutionPolicy Bypass -File "$HOME\.claude\skills\pr-converge\scripts\caller-window-pid.ps1"
```
Capture the printed integer as `caller_pid`. Verify it is the right window:
```bash
pwsh -NoProfile -Command "Get-Process -Id <caller_pid> | Select-Object Id,ProcessName,MainWindowTitle"
```

**2. Launch the AHK auto-typer:**
```bash
"$HOME\.claude\skills\pr-converge\scripts\cursor-agents-continue.cmd" <caller_pid> --start-on
```
AutoHotkey v2 must be installed at `C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe`. The indicator window (`pr-converge / agents pacer`) confirms the pacer is running. Every 5 minutes it types `continue` into this window to trigger the next tick.

## Step 0: Discover Work Queue

At the start of each session (or after a long pause), assemble the current PR state dynamically. Run all four commands:

**Open PRs:**
```bash
gh api 'repos/jl-cmd/claude-code-config/pulls?state=open&per_page=100' --paginate --slurp \
  | jq '[.[][] | {number, title, headRefName: .head.ref, head_sha: .head.sha, mergeable, isDraft: .draft}] | sort_by(.number)'
```
Use **`head.ref`** and **`draft`** here — the REST list response does not expose GraphQL-style `headRefName` / `isDraft` keys. **`gh pr view --json`** (below) is what emits `headRefName` / `isDraft`.

**Bugbot review status per PR** (run for each `<N>`):
```bash
python "$HOME\.claude\skills\pr-converge\scripts\fetch_bugbot_reviews.py" \
  --owner jl-cmd --repo claude-code-config --number <N>
```
Returns `classification: "clean"` or `classification: "dirty"` plus `commit_id`.

**Bugbot inline findings for dirty PRs** (run for each dirty `<N>` at its `<HEAD_SHA>`):
```bash
python "$HOME\.claude\skills\pr-converge\scripts\fetch_bugbot_inline_comments.py" \
  --owner jl-cmd --repo claude-code-config --number <N> --commit <HEAD_SHA>
```

**Prior bugteam review per PR** (run for each `<N>`):
```bash
gh api 'repos/jl-cmd/claude-code-config/pulls/<N>/reviews?per_page=100' --paginate --slurp \
  | jq '[.[][] | select((.body // "") | startswith("## /bugteam"))] | sort_by(.submitted_at) | last | {commit_id, body}'
```
A review body ending with `-> clean` at the current HEAD means bugteam passed.

Build a decision table from the results:

| PR | Head SHA | Bugbot | Bugteam | Next action |
|----|----------|--------|---------|-------------|
| ... | ... | clean/dirty | clean/dirty/none | ... |

## Multitask Mode — `continue` fan-out

When **Multitask Mode** is active in Cursor and the user types **`continue`** (advance the convergence loop), the **coordinator** MUST **not** run a single-PR tick for one PR by default.

1. List open PR numbers, for example:
   ```bash
   gh pr list -R jl-cmd/claude-code-config --state open --json number -q ".[].number"
   ```
   (Any equivalent that returns the same set of PR numbers is fine.)
2. For **each** open PR number, spawn **one** background subagent:
   ```
   Task(
     subagent_type="generalPurpose",
     run_in_background=true,
     prompt="…scoped to PR #<N> only…"
   )
   ```
3. Each subagent runs **exactly one** parallel-debug tick for **that** PR: Bugbot state vs current HEAD, inline handling, and **at most one** loop advance per **Per-Tick Work** below (no full bugteam protocol duplicated here — follow **Per-Tick Work** and link out to bugteam only where that section already does).

Outside Multitask Mode, `continue` still means one coordinator tick on the active PR context as today.

## Per-Tick Work

Each tick (triggered by `continue` from AHK or from the user **outside Multitask Mode**; in Multitask Mode, coordinator `continue` fans out per **Multitask Mode — `continue` fan-out**) runs these steps:

**Step 1 — Resolve current HEAD and PR context:**
```bash
gh pr view <N> -R jl-cmd/claude-code-config --json "number,url,headRefOid,baseRefName,headRefName,isDraft"
```
On **PowerShell**, quote the **`--json`** field list so commas are not split into separate arguments.

Increment `tick_count`. Read prior state line from the previous response.

**Step 2 — Branch on `phase`:**

*BUGBOT phase:*
- Fetch Bugbot classification (same helper as Step 0 — do **not** re-derive clean/dirty from raw review bodies):
  ```bash
  python "$HOME\.claude\skills\pr-converge\scripts\fetch_bugbot_reviews.py" \
    --owner jl-cmd --repo claude-code-config --number <N>
  ```
  Use the JSON array entries’ `commit_id` and `classification` (`clean` / `dirty`) exactly as Step 0 does.
- Fetch inline findings for current HEAD:
  ```bash
  python "$HOME\.claude\skills\pr-converge\scripts\fetch_bugbot_inline_comments.py" \
    --owner jl-cmd --repo claude-code-config --number <N> --commit <current_head>
  ```
- Decide:
  - No entry with `commit_id == current_head` → set `inline_lag_streak = 0`, re-trigger bugbot (Step 3), schedule next tick
  - Entry at `current_head` with `classification: "clean"` **and** zero inline findings → set `inline_lag_streak = 0`, set `bugbot_clean_at = current_head`, transition to BUGTEAM phase, continue in same tick
  - Non-zero inline findings on `current_head` → set `inline_lag_streak = 0`, apply Fix protocol, re-trigger bugbot, schedule next tick
  - Entry at `current_head` with `classification: "dirty"` **and** zero inline findings → increment `inline_lag_streak`; if `>= 3` hard blocker; else schedule next tick at AHK cadence

*BUGTEAM phase:*
- Read `$HOME\.claude\skills\pr-converge\SKILL.md` and `$HOME\.claude\skills\bugteam\SKILL.md` for full audit protocol
- Run bugteam audit by following the bugteam skill's Step 3 cycle against the current PR
- Re-resolve HEAD after bugteam (it may have pushed commits)
- If bugteam pushed → set `bugbot_clean_at = null`, re-trigger bugbot, transition to BUGBOT, schedule next tick
- If bugteam converged AND `bugbot_clean_at == current_head` → back-to-back clean; mark ready (Step 5)
- If bugteam converged but `bugbot_clean_at != current_head` → transition to BUGBOT, schedule next tick
- If bugteam has findings without committing → apply Fix protocol, re-trigger bugbot, transition to BUGBOT, schedule next tick

**Step 3 — Re-trigger bugbot:**

Prefer the bundled helper (temp body file and `gh pr comment --body-file` in one process, per `pr-converge` Step 3):

```bash
python "$HOME\.claude\skills\pr-converge\scripts\trigger_bugbot.py" \
  --owner jl-cmd --repo claude-code-config --number <N>
```

When the script is unavailable, run **one** `pwsh` invocation so the temp path never crosses process boundaries:

```powershell
pwsh -NoProfile -Command @'
$bodyPath = [System.IO.Path]::ChangeExtension((New-TemporaryFile).FullName, '.md')
[IO.File]::WriteAllText($bodyPath, "bugbot run`n", [Text.UTF8Encoding]::new($false))
gh pr comment <N> --repo jl-cmd/claude-code-config --body-file $bodyPath
Remove-Item -LiteralPath $bodyPath -Force -ErrorAction SilentlyContinue
'@
```

**Step 4 — State line (emit every tick):**
```
State: phase=<BUGBOT|BUGTEAM> bugbot_clean_at=<SHA|null> inline_lag_streak=<N> tick_count=<N>
```
Do NOT call `ScheduleWakeup` — AHK is the pacer.

End every response with: `Awaiting next "continue" tick.`

## Fix Protocol

When findings exist (either phase):

1. Read each referenced `file:line`.
2. Write a failing test first when the finding has behavior to test; skip for doc/naming nits.
3. Implement the fix. For all production or test code edits, spawn a `Task` subagent (same split as **pr-converge** Fix protocol — `packages/claude-dev-env/skills/pr-converge/SKILL.md` §Fix protocol: subagent edits; **this session** runs commit/push in steps 4–5):
   ```
   Task(
     subagent_type="generalPurpose",
     prompt="You are acting as clean-coder. Read $HOME/.claude/agents/clean-coder.md on Unix or %USERPROFILE%\\.claude\\agents\\clean-coder.md on Windows before editing; that file is binding (naming, TDD when behavior changes, scope limited to the listed findings). Implement: <specific fix description with file:line>. Do not run git commit or git push — return when edits are complete so the coordinator runs steps 4–5."
   )
   ```
   Ensure `.cursor/agents/clean-coder.md` exists; copy from `~/.claude/agents/` when missing.
4. Stage and commit:
   ```bash
   git add <files>
   git commit -m "fix(review): <brief summary>"
   ```
5. Push:
   ```bash
   git push origin <branch>
   ```
6. Set `current_head` to new SHA. Set `bugbot_clean_at = null`.
7. Reply to each addressed inline comment thread:
   ```bash
   gh api -X POST repos/jl-cmd/claude-code-config/pulls/<N>/comments/<comment_id>/replies \
     --field body=@<reply_body_file.md>
   ```
8. Re-trigger bugbot (Step 3) immediately after pushing.

Honor pre-commit and pre-push hooks. When a hook rejects, read its output, fix the underlying issue, and retry.

## Step 5: Convergence

When back-to-back clean (bugteam converged AND `bugbot_clean_at == current_head` with no push during this tick):

```bash
gh pr ready <N> --repo jl-cmd/claude-code-config
```

Report: `PR #<N> converged: bugbot CLEAN at <SHA>, bugteam CLEAN at <SHA>; marked ready for review.`

After all open PRs have converged, stop the AHK auto-typer (canonical **scoped** kill — matches `packages/claude-dev-env/skills/pr-converge/workflows/ahk-auto-continue-loop.md` **Convergence cleanup**; command-line match avoids killing unrelated AutoHotkey tools):

```bash
pwsh -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='AutoHotkey64.exe'\" | Where-Object CommandLine -like '*cursor-agents-continue.ahk*' | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
```

Use the **same** one-liner when **Safety Cap** or **Hard Blockers** require stopping the pacer.

Do not emit `Awaiting next "continue" tick.` after a convergence stop — the loop is done.

## Safety Cap

When `tick_count >= 30`, stop the loop and stop the auto-typer (**same scoped `Get-CimInstance` / `Stop-Process` one-liner as Step 5**). Report the cap was hit and which PRs remain open. Something structural requires manual investigation.

## Hard Blockers

Stop immediately (stop AHK with the **Step 5** scoped one-liner, do not schedule next tick) when:
- API auth failure persists across two ticks
- `inline_lag_streak >= 3`
- bugteam reports `stuck` state
- A hook rejection persists through three commits with the same underlying error

Report the specific blocker and diagnosis.

## Success Criteria

- All open PRs in `jl-cmd/claude-code-config` have been marked ready for review via `gh pr ready`
- Each PR reached back-to-back clean: bugbot CLEAN at current HEAD + bugteam CLEAN at current HEAD
- AHK auto-typer stopped via the scoped stopper script
- Final report lists each PR number and its convergence SHA
