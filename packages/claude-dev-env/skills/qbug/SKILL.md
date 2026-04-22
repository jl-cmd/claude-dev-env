---
name: qbug
description: >-
  Required baseline review for every new PR. Runs the /bugteam audit → fix →
  commit → push cycle via one clean-coder subagent (not a full team), looping
  until convergence or stuck. Uses the same CODE_RULES gate, A–J category
  rubric, and per-loop PR review shape as /bugteam — without TeamCreate,
  teammates, per-loop clean-room, or a loop cap. Invoke /bugteam instead for
  larger PRs that need per-loop bias isolation or a hard loop cap. Triggers:
  '/qbug', 'quick bug audit', 'solo bug audit', 'baseline PR review',
  'bugteam without a team'.
---

# qbug

**Core principle:** One `clean-coder` subagent loops audit → fix → commit → push until converged or stuck. The subagent's context persists across loops (no per-loop clean-room) — that is the explicit trade vs /bugteam.

**When to reach for /qbug vs /bugteam:** `/qbug` is the required baseline review for every new PR (fastest path from "ready" to "merged-safe"). Escalate to `/bugteam` when the PR is large enough that anchoring-bias across loops becomes a convergence risk, or when a hard loop cap is required for cost control.

Shared artifacts with /bugteam are referenced below by path, using the `${CLAUDE_SKILL_DIR}` host-substitution convention (both skills land under `~/.claude/skills/` after install):

- Pre-flight script: `${CLAUDE_SKILL_DIR}/../bugteam/scripts/bugteam_preflight.py`
- Code-rules gate script: `${CLAUDE_SKILL_DIR}/../bugteam/scripts/bugteam_code_rules_gate.py`
- Bug category rubric A–J: [`bugteam/PROMPTS.md`](../bugteam/PROMPTS.md#audit-spawn-prompt-xml-bugfind-teammate)
- **Audit contract** (finding schema, proof-of-absence, adversarial pass, Haiku secondary, post-fix self-audit, diagnostics JSON): [`bugteam/reference/audit-contract.md`](../bugteam/reference/audit-contract.md)
- PR comment lifecycle shape: [`bugteam/SKILL.md`](../bugteam/SKILL.md#step-25-pr-comments-one-review-per-loop)

## When this skill applies

`/qbug` once authorizes the full cycle (no loop cap — runs until `converged` or `stuck`; user can interrupt at any time).

Refusals — first match wins; respond with the quoted line exactly and stop:

- **No PR or upstream diff.** `No PR or upstream diff. /qbug needs a target.`
- **Dirty tree.** `Uncommitted changes detected. Stash, commit, or revert before /qbug.`
- **Missing subagent.** Before Step 2, confirm `clean-coder` exists. Else: `Required subagent type clean-coder not installed. /qbug needs clean-coder available.`

## Progress checklist

```
[ ] Step 0: pre-flight clean
[ ] Step 1: PR scope resolved
[ ] Step 2: subagent cycle complete (converged | stuck | error)
[ ] Step 3: PR description refreshed
[ ] Step 4: final report printed
```

## Step 0: Pre-flight

```bash
python "${CLAUDE_SKILL_DIR}/../bugteam/scripts/bugteam_preflight.py"
```

`${CLAUDE_SKILL_DIR}` is host-substituted before the shell runs. Non-zero → fix before continuing. `BUGTEAM_PREFLIGHT_SKIP=1` is emergency only. Add `--pre-commit` when `.pre-commit-config.yaml` exists.

Pre-flight checks (in order):

1. **Git hooks path** — verifies `git -C <repository_root> config --get core.hooksPath` resolves to a path ending in `hooks/git-hooks`. Queries the repository-effective config so repo-level overrides (Husky, lefthook) are detected. If unset or pointing elsewhere, exits non-zero:
   ```
   Git-side CODE_RULES enforcement is not active on this host.
   Run: npx claude-dev-env .
   Or:  git config --global core.hooksPath ~/.claude/hooks/git-hooks
   ```
2. **pytest** — runs the test suite when `pytest.ini` or `[tool.pytest]` is present.
3. **pre-commit** — runs when `--pre-commit` flag is passed and `.pre-commit-config.yaml` exists.

## Step 1: Resolve PR scope (lead)

1. `gh pr view --json number,baseRefName,headRefName,url`
2. Else `git merge-base HEAD origin/<default>` then `git diff <merge-base>...HEAD`
3. Else refuse per § When this skill applies.

Capture: `owner/repo`, `baseRefName`, `headRefName`, PR `number`, `url`, `starting_sha = git rev-parse HEAD`.

Resolve the scoped temp directory once, lead-side, before spawning the subagent. Use Python's `tempfile.gettempdir()` so the path is correct on macOS, Linux, Windows cmd.exe, and PowerShell — do not hardcode `/tmp/` because Windows runners do not honor it. Capture the resolved absolute path as `<qbug_temp_dir>` and pass that literal path to the subagent:

```python
import json
import subprocess
import tempfile
from pathlib import Path

pr_view: dict = json.loads(subprocess.check_output(
    ["gh", "pr", "view", "--json", "number,baseRefName,headRefName,url"]
))
pr_number: int = pr_view["number"]
qbug_temp_dir: Path = Path(tempfile.gettempdir()) / f"qbug-pr-{pr_number}"
qbug_temp_dir.mkdir(parents=True, exist_ok=True)
```

## Step 2: Spawn the primary and secondary audit agents

Before calling `Agent`, the lead resolves the three absolute paths the subagent needs and substitutes them into the prompt template (the `<gate_script>`, `<categories_file>`, and `<qbug_temp_dir>` placeholders in § Subagent cycle prompt):

```python
import os
from pathlib import Path

skill_dir = Path(os.environ["CLAUDE_SKILL_DIR"])
gate_script_path = (skill_dir / ".." / "bugteam" / "scripts" / "bugteam_code_rules_gate.py").resolve()
categories_file_path = (skill_dir / ".." / "bugteam" / "PROMPTS.md").resolve()
```

Then call `Agent` twice in the same message — the primary clean-coder and the Haiku secondary run in parallel per the audit contract. The Haiku secondary receives an **audit-only** prompt (no FIX step, no git operations) and returns findings to the lead only. The lead merges their findings before the FIX step:

```
Agent(
  subagent_type="clean-coder",
  model="sonnet",
  description="qbug primary audit/fix cycle for PR <number>",
  prompt="<filled cycle XML; see § Subagent cycle prompt>",
  run_in_background=False
)

Agent(
  subagent_type="code-quality-agent",
  model="haiku",
  description="qbug Haiku secondary audit for PR <number>",
  prompt="<audit-only prompt: read the PR diff, apply A-J categories from <categories_file>, return structured findings. No FIX, no git add, no git commit, no git push.>",
  run_in_background=False
)
```

The Haiku secondary is a read-only auditor per `audit-contract.md` — it returns findings to the lead and never modifies the working tree. The lead merges primary and Haiku secondary findings per the de-dup rules in the audit contract before proceeding. No `TeamCreate`, no `team_name`, no teammate shutdown protocol. The primary subagent returns when it has exited the cycle (`converged`, `stuck`, or `error`).

## Subagent cycle prompt

The subagent receives this prompt and loops internally — the lead does not re-invoke between loops. The prompt is self-contained: it restates the bug-category rubric by path rather than assuming prior context, and it states its full scope upfront. Before passing the prompt to `Agent()`, the lead substitutes every `{{UPPER_SNAKE}}` slot: `{{OWNER_REPO}}`, `{{HEAD_REF}}`, `{{BASE_REF}}`, `{{PR_URL}}`, `{{STARTING_SHA}}` (from Step 1) and `{{QBUG_TEMP_DIR}}`, `{{GATE_SCRIPT}}`, `{{CATEGORIES_FILE}}` (resolved in Step 2).

```xml
<role>
  You are the lone audit-fix worker for this pull request. Run the full
  audit → fix → commit → push cycle in this one subagent session. The
  lead has already resolved scope and pre-flight; your job is to take
  the cycle to an exit state and report back.
</role>

<context>
  <repo>{{OWNER_REPO}}</repo>
  <branch>{{HEAD_REF}}</branch>
  <base_branch>{{BASE_REF}}</base_branch>
  <pr_url>{{PR_URL}}</pr_url>
  <starting_sha>{{STARTING_SHA}}</starting_sha>
  <qbug_temp_dir>{{QBUG_TEMP_DIR}}</qbug_temp_dir>
  <gate_script>{{GATE_SCRIPT}}</gate_script>
  <categories_file>{{CATEGORIES_FILE}}</categories_file>
</context>

<exit_conditions>
  The cycle stops when ONE of these is true. Check on every iteration:
    - converged: most recent AUDIT returned zero findings AND
      post_fix_audit_clean is true for the committing loop.
    - stuck: most recent FIX left `git rev-parse HEAD` unchanged.
    - error: three consecutive pre-audit gate rounds failed (three is
      chosen because two is within normal clean-coder variance; four
      rounds typically indicates a gate defect rather than fixable
      violations).
  There is no loop-count cap. A pathological diff with ever-changing
  findings will still exit via `stuck` once a FIX produces no commit.
</exit_conditions>

<cycle>
  Maintain inline across iterations:
    loop_count = 0
    last_action = "fresh"           # fresh | audited | fixed
    last_findings = {p0, p1, p2, total}
    loop_comment_index = {}
    audit_log = []

  Iteration:
    1. Dispatch on last_action:
       - "audited" and last_findings.total == 0 → exit "converged"
       - "fixed" and `git rev-parse HEAD` equals the sha captured
         immediately before FIX → exit "stuck"
       - "fresh" or "fixed" → run pre-audit, then AUDIT
       - "audited" and last_findings.total > 0 → run FIX

    2. Pre-audit (before every AUDIT):
       Run the gate script at <gate_script> with `--base origin/<base_branch>`.
       Non-zero exit → fix the reported violations inline and re-run the
       same command. Count consecutive failures. Three failed rounds →
       exit "error: code rules gate failed pre-audit".
       On exit 0: increment loop_count, proceed to AUDIT.

    3. AUDIT:
       Run: `gh pr diff <pr_number> -R <owner>/<repo> > <qbug_temp_dir>/loop-<loop_count>.patch`

       - Read the patch file.
       - Audit only added/modified lines. Read <categories_file> for the
         A–J category definitions; investigate each category explicitly.
       - Follow the shared audit contract at
         bugteam/reference/audit-contract.md. Per category: produce
         either a Shape A structured finding or a Shape B structured
         proof-of-absence. Bare "verified clean" labels are REJECTED.
       - Run the contract's adversarial second pass after the primary
         finding list.
       - The LEAD spawns the Haiku secondary auditor in parallel with
         this primary audit per the contract's Haiku secondary section.
       - Partition findings into anchored (line appears in the diff) vs
         unanchored (line does not).

       Persist the merged audit result to
       <qbug_temp_dir>/loop-<loop_count>-audit.json per the contract's
       persistence schema.

       Post ONE review per loop. Use the payload shape from
       <categories_file>'s sibling SKILL.md § "PR comments" — build
       the JSON with jq `--rawfile` / `-Rs` reading per-finding body
       files, pipe to
       `gh api repos/<owner>/<repo>/pulls/<pr_number>/reviews -X POST --input -`.
       Review body first line: `## /qbug loop <N> audit: <P0>P0 / <P1>P1 / <P2>P2`.
       If the review POST fails, fall back to one issue comment on
       `/issues/<pr_number>/comments` carrying the full body; mark every
       finding `used_fallback=true`.

       Harvest `html_url` for the parent review and each child comment
       into loop_comment_index[finding_id].

       Update state: last_action="audited", last_findings=counts.
       Append `<N> audit: <P0>P0 / <P1>P1 / <P2>P2` to audit_log.

    4. FIX:
       Capture the pre-FIX sha: `pre_fix_sha = git rev-parse HEAD`.
       Capture pre-fix file contents for every file this FIX will touch.

       Apply each fix. Read every file before editing. Preserve existing
       comments on lines you do not modify. Add type hints on every
       signature you touch.

       Validate each modified Python file with `python -m py_compile`
       (or the language-equivalent compile check).

       Compute fix_diff: the diff between pre-fix and post-fix file contents
       for every modified file.

       Post-fix self-audit: follow the contract's post-fix self-audit
       sequence at bugteam/reference/audit-contract.md. Paranoid mode
       (Haiku secondary in parallel), internal iteration cap = 3, exit
       "stuck: post-fix audit not converging" after 3 rounds with fresh
       findings. Only when gate_findings empty AND post_fix_findings
       empty: proceed to git add.

       Stage each modified path by explicit name: `git add <path>`.
       Create one commit summarizing the fixed findings. Let every git
       hook run. If a hook blocks the commit, capture its stderr, mark
       every finding in this loop `status=hook_blocked`, and move on to
       the next iteration without retrying this loop.

       Push with a plain fast-forward: `git push`.

       Write <qbug_temp_dir>/loop-<loop_count>-diagnostics.json per the
       contract's diagnostics schema (all eight keys required).

       Reply to each finding at loop_comment_index[finding_id].finding_comment_id
       using the reply CLI shape (jq `-Rs` → `gh api .../comments/<id>/replies --input -`).
       Reply body is one of:
         - `Fixed in <short_sha>`
         - `Could not address this loop: <one-line reason>`
         - `Hook blocked the fix commit: <one-line summary>`

       Update state: last_action="fixed". Append
       `<N> fix: <short_sha> — <fixed>/<could_not_address>/<hook_blocked>`
       to audit_log.

    5. Return to step 1.
</cycle>

<example_finding_body>
**[P1] race condition on shared cache write**
Category: I (concurrency hazards)
Two writers can both pass the existence check at line 88 before either
commits the write at line 91 — whichever writes second overwrites the
first under contention. Either hold the cache lock across the check
and the write, or use a compare-and-swap primitive.

_From /qbug audit loop 2._
</example_finding_body>

<constraints>
  - Edit only files reachable from the PR diff's scope.
  - Keep the branch linear: append one new commit per FIX loop and push
    fast-forward only.
  - Preserve existing comments on lines you do not modify.
  - Every signature you touch has complete type hints.
  - Every file is read before you edit it (investigate before answering).
  - Complete the entire cycle in this one subagent session using your
    available tools directly; keep all audit and fix work inside this
    session.
</constraints>

<output_format>
  Return to the lead with exactly these fields:
    - exit_reason: "converged" | "stuck" | "error: <detail>"
    - loop_count: integer
    - final_commit_sha: `git rev-parse HEAD` at exit
    - audit_log: ordered list of per-loop lines
    - unresolved: array of {file, line, severity, title, reason}
      (present only when exit_reason == "stuck")
</output_format>
```

## Step 3: PR description refresh (lead)

Delegate body composition to the `pr-description-writer` agent (the mandatory-pr-description hook requires it for `gh pr edit` to succeed). Feed it the final PR diff and the original body. Apply via `gh pr edit <number> -R <owner>/<repo> --body-file .qbug-final-body.md`.

On error exit paths: best-effort; log the failure in the final report and continue.

## Step 4: Final report (lead)

Use the same shape as [`bugteam/SKILL.md` Step 6](../bugteam/SKILL.md#step-6-final-report) with two deltas:

- Header substitutes `/qbug` for `/bugteam`.
- Exit states are `converged | stuck | error` (no `cap reached` state, since `/qbug` has no loop cap).

Delete the resolved `<qbug_temp_dir>` tree and any `.qbug-*.md` temp files in the working directory. The lead captured the dir as an absolute path via `tempfile.gettempdir()` in Step 1; reuse that literal for cleanup.

## Constraints

- **One primary + one secondary auditor, not a team.** Lead spawns a `clean-coder` primary (audit + fix cycle) and a `code-quality-agent` Haiku secondary (audit-only, read-only — no FIX, no git). No `TeamCreate`. Neither subagent spawns further subagents.
- **No loop cap.** Cycle runs until `converged`, `stuck`, or `error`. User can interrupt.
- **Code rules gate before every AUDIT.** Same `validate_content` logic as /bugteam.
- **One commit per FIX action.** Linear branch, fast-forward push only.
- **Categories A–J.** Same rubric as [`bugteam/PROMPTS.md`](../bugteam/PROMPTS.md).
- **One review per loop.** Anchored findings as `comments[]`; unanchored listed under "Findings without a diff anchor" in the review body.
- **PR description rewrite on every exit**, same as /bugteam Step 4.5.
- **Temp file cleanup on every exit path.**
- **No per-loop clean-room.** The single subagent's context accumulates across loops — that is the explicit trade vs /bugteam. For convergence-critical audits where bias isolation matters, use /bugteam.

## Examples

<example>
User: `/qbug`
Lead: [preflight, resolves PR #42, spawns ONE clean-coder subagent with the cycle prompt]
Subagent: [runs loops internally, returns]

`Loop 1 audit: 1P0 / 2P1 / 0P2`
`Loop 1 fix: commit a1b2c3d (3 files, +18/-7) — 3 fixed, 0 skipped`
`Loop 2 audit: 0P0 / 1P1 / 0P2`
`Loop 2 fix: commit e4f5g6h (1 file, +5/-2) — 1 fixed, 0 skipped`
`Loop 3 audit: 0P0 / 0P1 / 0P2 → converged`

`/qbug exit: converged`
`Loops: 3`
`Starting commit: 9d8c7b6`
`Final commit: e4f5g6h`
`Net change: 4 files, +23/-9`
</example>

<example>
User: `/qbug`
Subagent: [loop 4 fix produces no commit despite findings]

`Loop 4 fix: no changes — could not address remaining 2 findings`
`/qbug exit: stuck`
`Unresolved: src/cache.py:88 (P0 race condition); src/parser.py:44 (P1 unbound reference)`
</example>

<example>
User: `/qbug` (no PR or upstream diff)
Lead: `No PR or upstream diff. /qbug needs a target.`
</example>

