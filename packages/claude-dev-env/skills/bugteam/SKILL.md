---
name: bugteam
description: >-
  Open pull request audit–fix until convergence: CODE_RULES gate, clean-room
  audit (`code-quality-agent`, opus) and fix (`clean-coder`, opus), per-loop
  GitHub reviews, 10-audit cap; grant then revoke `.claude/**`. **Path A** when
  `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` (orchestrated teams, `TeamCreate`).
  **Path B** otherwise (Task harness — workflow in
  `reference/workflow-path-b-task-harness.md`). **This `SKILL.md` holds only
  shared steps**; per-path harness lives in `reference/workflow-path-*.md`.
  Triggers: '/bugteam', 'run the bug team', 'auto-fix the PR until clean', 'loop
  audit and fix'.
---

# Bugteam

**Core principle:** Audit–fix until convergence. **Bugfind:**
`code-quality-agent`, fresh context each loop. **Bugfix:** `clean-coder`. Hard
cap: 10 audit loops. Grant `.claude/**` at start, revoke always at end.

**Path routing** picks **Path A** (orchestrated teams) vs **Path B** (Task
harness). Harness execution — `TeamCreate`, `Agent`/`Task` spawns,
`SendMessage`, `TeamDelete`, who runs Step 2.5 `gh api` — lives only in
[`reference/workflow-path-a-orchestrated-teams.md`][path-a] and
[`reference/workflow-path-b-task-harness.md`][path-b]. Verbatim doc quotes and
URLs: [`sources.md`](sources.md).

## Path routing (mandatory first branch)

At `/bugteam` entry, evaluate **once** (same rule as pr-converge §Team
infrastructure detection):

- **Path A** — `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` set and equals **`1`**
  after trim → load and follow
  [`reference/workflow-path-a-orchestrated-teams.md`][path-a] for every harness
  step (with this `SKILL.md` for shared material).
- **Path B** — otherwise → load and follow
  [`reference/workflow-path-b-task-harness.md`][path-b] for every harness step
  (with this `SKILL.md` for shared material).

Shared material is **everything else in this file** plus
[`PROMPTS.md`](PROMPTS.md), [`EXAMPLES.md`](EXAMPLES.md),
[`CONSTRAINTS.md`](CONSTRAINTS.md) — agent types, models, XML, gates, cycle
state machine, Step 2.5 payload shapes, shared teardown `rmtree`, revoke, final
report.

## Team lifecycle (Path A only)

The `TeamCreate` / `TeamDelete` pair has historically been bound to a single
`/bugteam` invocation. That coupling fails when an orchestrator (`pr-converge`
multi-PR mode, `monitor-open-prs`) needs to call `/bugteam` repeatedly inside
one parent session: only one team can be led at a time, and a missed Step 4
leaks the team. To decouple, every Path A invocation reads
`BUGTEAM_TEAM_LIFECYCLE` (defaults to `auto`) and may also read
`BUGTEAM_TEAM_NAME`.

**`owned`**

- **Step 2:** `TeamCreate(<computed_team_name>)`. If the runtime returns
  `Already leading team "<existing>". A leader can only manage one team at a
  time.` → **error**: `Already leading team <existing>; rerun with
  BUGTEAM_TEAM_LIFECYCLE=attach BUGTEAM_TEAM_NAME=<existing>`.
- **Step 4:** `TeamDelete()` (lead-owned).
- **Use case:** Pre-decoupling behavior. Use only when you know the session
  leads no other team.

**`attach`**

- **Step 2:** Require `BUGTEAM_TEAM_NAME`. Treat that team as already-led; do
  **not** call `TeamCreate`.
- **Step 4:** **Skip** `TeamDelete` — the orchestrator owns teardown.
- **Use case:** Orchestrators (pr-converge multi-PR, monitor-open-prs) that
  explicitly created a team and will tear it down themselves.

### `auto` (**default: `auto`**)

- **Step 2:** Try `TeamCreate(<computed_team_name>)`. On `Already leading team
  "<existing>"` → parse `<existing>`, attach (do **not** call `TeamCreate`
  again), set `team_owned=false`. On success → set `team_owned=true`.
- **Step 4:** If `team_owned=true` → `TeamDelete()`. Else → **skip**
  `TeamDelete`.
- **Use case:** All callers when in doubt. Solo invocations behave like `owned`;
  nested or repeated invocations attach safely.

**`team_owned` flag** — set in Step 2 by all three modes
(`owned` always `true`; `attach` always `false`; `auto` reflects the
`TeamCreate` outcome). Read in Step
4 to decide whether to call `TeamDelete`. The same flag also gates
`<team_temp_dir>` `rmtree`: when `team_owned=false`, only the per-PR subfolders
this invocation created (`<team_temp_dir>/pr-<N>/`) are removed; the
orchestrator's parent directory survives.

**Path B note:** Path B does not use `TeamCreate` / `TeamDelete`, so
`BUGTEAM_TEAM_LIFECYCLE` is read but only its `team_temp_dir` cleanup behavior
applies. `team_owned` is treated as `true` by default in Path B; orchestrators
driving Path B that share a temp directory should set
`BUGTEAM_TEAM_LIFECYCLE=attach` so the per-PR subfolder cleanup rule applies.

## Contents

Orchestration lives here; companion files hold prompts, invariants, examples,
citations, and domain reference notes. Scan this list before a partial read.

- [Path routing](#path-routing-mandatory-first-branch) — Path A vs Path B
- [Team lifecycle](#team-lifecycle-path-a-only) — `owned` / `attach` / `auto`
  modes; orchestrator-owned teams
- [`reference/workflow-path-a-orchestrated-teams.md`][path-a] — Path A harness
  (orchestrated teams)
- [`reference/workflow-path-b-task-harness.md`][path-b] — Path B harness (Task
  harness)
- When this skill applies — refusal cases and trigger conditions
- Utility scripts — pre-flight (`scripts/`, executed not inlined)
- Pre-audit gate — `validate_content` before each AUDIT
- The Process — checklist + Steps 0–6
  - Step 0 — Grant project permissions
  - Step 1 — Resolve PR scope
  - Step 2 — Path harness + loop state
  - Step 2.5 — PR comment lifecycle (per-loop review + fix replies)
  - Step 3 — Cycle (AUDIT ↔ FIX, exits)
  - Step 4 — Teardown + clean tree
  - Step 4.5 — PR body via `pr-description-writer`
  - Step 5 — Revoke permissions
  - Step 6 — Final report
- [`PROMPTS.md`](PROMPTS.md) — spawn XML, categories A–J, outcome schemas
- [`EXAMPLES.md`](EXAMPLES.md) — exit scenarios
- [`CONSTRAINTS.md`](CONSTRAINTS.md) — invariants and design rationale
- [`sources.md`](sources.md) — doc URLs and verbatim quotes
- [`reference/README.md`](reference/README.md) — expanded prose by topic
  (design, team setup, GitHub reviews, cycle, teardown)

## When this skill applies

`/bugteam` once authorizes the full cycle (up to 10 audits + fixes).

Refusals — first match wins; respond with the quoted line exactly and stop:

- **No PR or upstream diff.** `No PR or upstream diff. /bugteam needs a target.`
- **Dirty tree.** `Uncommitted changes detected. Stash, commit, or revert before
  /bugteam.`
- **Missing subagents.** Before Step 0, confirm `code-quality-agent` and
  `clean-coder` exist. Else: `Required subagent type <name> not installed.
  /bugteam needs both code-quality-agent and clean-coder available.`
- **Lead role must be held by the orchestrator.** Run /bugteam in the session
  that received the user's command. **Path A:** lead calls `TeamCreate` per
  [`reference/workflow-path-a-orchestrated-teams.md`][path-a]; runtime may
  return `Already leading team "<name>". A leader can only manage one team at a
  time.` **Path B:** lead runs the Task harness per
  [`reference/workflow-path-b-task-harness.md`][path-b]; no `TeamCreate`.

## Utility scripts

Shell-heavy steps live under
[`_shared/pr-loop/scripts/`](../../_shared/pr-loop/scripts/) (run, do not paste
into context). Utility scripts are **executed**, not loaded as primary context
([`sources.md`](sources.md) § Progressive disclosure and utility scripts).

### Pre-flight (before Step 0)

```bash
python "${CLAUDE_SKILL_DIR}/../../_shared/pr-loop/scripts/preflight.py"
```

Non-zero → fix before grant. `BUGTEAM_PREFLIGHT_SKIP=1` emergency only.
`--pre-commit` if `.pre-commit-config.yaml` exists.

**Auto-remediation for `core.hooksPath`:** when preflight fails with stderr
containing `core.hooksPath` (the message starts with `bugteam_preflight:
core.hooksPath is`, or `Git-side CODE_RULES enforcement is not active`), Claude
must auto-invoke the fix script — do not fall through to `AskUserQuestion`, do
not punt to the user, do not ask for confirmation:

```bash
python "${CLAUDE_SKILL_DIR}/../../_shared/pr-loop/scripts/fix_hookspath.py"
```

The fix script removes any non-canonical local-scope override on the active
repository, sets the global `core.hooksPath` to `~/.claude/hooks/git-hooks` if
missing or wrong, and re-runs `preflight.py`. Its exit code becomes the
preflight outcome. Exit 0 → continue to Step 0. Non-zero only when the
canonical hooks directory is missing (run `npx claude-dev-env .` first) or
`git config --global` writes are blocked. Other preflight failures (pytest,
pre-commit) still require manual fixes —
the auto-remediation only applies to the `core.hooksPath` failure mode.

## The Process

### Progress checklist

```
[ ] Step 0: project permissions granted
[ ] Step 1: PR scope resolved
[ ] Step 2: loop state set + path harness applied
[ ] Step 3: cycle complete (converged | cap reached | stuck | error)
[ ] Step 4: team torn down + working tree clean
[ ] Step 4.5: PR description rewritten (or skip warning logged)
[ ] Step 5: project permissions revoked
[ ] Step 6: final report printed
```

### Step 0: Grant project permissions (once, first)

```bash
python
"${CLAUDE_SKILL_DIR}/../../_shared/pr-loop/scripts/grant_project_claude_permis \
sions.py"
```

`${CLAUDE_SKILL_DIR}` is host-substituted before the shell runs (unlike normal
env expansion). Idempotent writes to `~/.claude/settings.json` from repo root.
Non-zero → stop. Revoke in Step 5 on every exit path.

### Step 1: Resolve PR scope (once)

Accept one or more PR numbers from the invocation. For each PR, run `gh pr view
--json number,baseRefName,headRefName,url` (falling back to the merge-base diff
path when no PR exists). Capture `all_prs = [{number, owner, repo, baseRef,
headRef, url}, ...]`. A single-PR invocation produces a one-element list and
follows the same downstream rules.

Keep: owner/repo, branches, PR number, URL — for all loops.

#### Per-PR workspace

For each PR in all_prs:

1. Create `<team_temp_dir>/pr-<N>/`.
2. Run `git worktree add "<team_temp_dir>/pr-<N>/worktree" origin/<headRef>`.
3. Record the absolute worktree path alongside the PR's other fields.

Teammates or Task workers for a PR operate inside that PR's worktree. Step 4
teardown runs `git worktree remove "<team_temp_dir>/pr-<N>/worktree"` for each
PR, then path-specific harness teardown per
[`reference/workflow-path-a-orchestrated-teams.md`][path-a] or
[`reference/workflow-path-b-task-harness.md`][path-b] § Step 4.

### Step 2: Path harness + loop state

Apply the path you chose in [Path
routing](#path-routing-mandatory-first-branch): **Path A** —
[`reference/workflow-path-a-orchestrated-teams.md`][path-a] § Step 2
(`TeamCreate`, team name, `team_temp_dir`, roles, optional Groq FIX,
`--bugbot-retrigger`). **Path B** —
[`reference/workflow-path-b-task-harness.md`][path-b] § Step 2 (no `TeamCreate`
/ `TeamDelete`; same worktrees and variables).

Path A also resolves the team lifecycle here per [Team
lifecycle](#team-lifecycle-path-a-only): pick the mode (`owned` / `attach` /
`auto`) from `BUGTEAM_TEAM_LIFECYCLE`, set `team_name` (computed for
`owned`/`auto` create paths; required `BUGTEAM_TEAM_NAME` for `attach` and
`auto`'s attach branch), and set `team_owned` (`true` when `TeamCreate`
succeeded in this invocation; `false` when attaching to an existing team). Step
4 reads `team_owned` to decide whether to call `TeamDelete`.

**Loop state (lead; not a single script):**

```bash
loop_count=0
last_action="fresh"
last_findings='{"total": 0}'
audit_log=""
starting_sha="$(git rev-parse HEAD)"
team_name="bugteam-pr-<number>-<YYYYMMDDHHMMSS>"
team_temp_dir="<absolute-path>/<team_name>"
team_owned="true" # set by Step 2 lifecycle resolution; see Team lifecycle table
loop_comment_index=""
```

**`loop_comment_index`:** reset each AUDIT start; filled during AUDIT; FIX
consumes for replies; cleared after FIX. Entries: `{loop, finding_id,
finding_comment_id, finding_comment_url, used_fallback, fix_status}`.

### Step 2.5: PR comments (one review per loop)

**Who posts:** Path A vs Path B —
[`reference/workflow-path-a-orchestrated-teams.md`][path-a] § Step 2.5 and
[`reference/workflow-path-b-task-harness.md`][path-b] § Step 2.5. Payloads and
endpoints below are identical for both paths.

Order: audit → buffer → validate anchors vs diff → single review POST.
Review body states counts; zero findings → still one review, `comments: []`,
body `## /bugteam loop <N> audit: 0P0 / 0P1 / 0P2 → clean`.

**Payloads:** build JSON with `jq --rawfile` / `-Rs`, pipe to `gh api ...
--input -` (avoids shell-quoting; satisfies `gh-body-backtick-guard`). Write
each markdown body to a temp file first.

**Review POST** (one `comments[]` object per anchored finding; single-line
`{path, line, side: "RIGHT", body}`; multi-line add `start_line`, `start_side:
"RIGHT"`):

```
jq -n \
--rawfile review_body <tmp_review_body.md> \
--arg commit_id "$(git rev-parse HEAD)" \
--rawfile finding_body_1 <tmp_finding_1.md> \
--arg path_1 "<file_1>" \
--argjson line_1 <line_1> \
[... one finding_body_K / path_K / line_K triple per finding ...] \
'{
commit_id: $commit_id,
event: "COMMENT",
body: $review_body,
comments: [
{path: $path_1, line: $line_1, side: "RIGHT", body: $finding_body_1}
[, ... ]
]
}' \
| gh api repos/<owner>/<repo>/pulls/<number>/reviews -X POST --input -
```

**Fix reply:** `jq -Rs '{body: .}' <tmp_reply.md | gh api
repos/<owner>/<repo>/pulls/<number>/comments/<finding_comment_id>/replies -X
POST --input -`

**Review POST fails:** issue comment fallback: `jq -Rs '{body: .}'
<tmp_fallback.md | gh api repos/<owner>/<repo>/issues/<number>/comments -X POST
--input -`

`<head_sha_at_post_time>`: `git rev-parse HEAD` in teammate cwd immediately
before POST.

**Review body template (`<tmp_review_body.md>`):**

```
## /bugteam loop <N> audit: <P0>P0 / <P1>P1 / <P2>P2

### Findings without a diff anchor
(only if needed)
- **[severity] title** — <file>:<line> — <one-line description>
```

**Anchor fallback:** lines not in diff → omit from `comments[]`, list under
`### Findings without a diff anchor`; outcome `used_fallback="true"`, empty
`finding_comment_id`, `finding_comment_url` = parent review URL.

**POST failure fallback:** one issue comment with full text; all findings
`used_fallback="true"`, URLs = issue comment.

**Endpoints:** `POST .../pulls/{pull}/reviews`; `POST
.../pulls/{pull}/comments/{id}/replies`; fallback `POST
.../issues/{issue}/comments` (`issue` = PR number).

### Step 3: The cycle

Run the AUDIT-FIX cycle for each PR in all_prs, reusing the same team across
PRs. The 10-loop cap applies per PR. Exit reasons (converged, cap reached,
stuck, error) are tracked per PR; the final report lists one outcome line per
PR.

**Gate:** `validate_content` / `hooks/blocking/code_rules_enforcer.py` on
PR-scoped files before every AUDIT
(`_shared/pr-loop/scripts/code_rules_gate.py`). Lead runs gate; clean-coder
clears failures; then bugfind audits.

**Pre-cycle: walk prior bugteam reviews end-first** (once per PR, after Step 2
and before iteration begins, when `last_action == "fresh"`). A re-invocation of
`/bugteam` on a PR with prior loops detects whether the most recent loop already
cleaned this HEAD (short-circuit) and otherwise records that prior loops were
dirty so the AUDIT runs against the latest diff with that signal in mind:

```bash
dirty_review_count=0
gh api "repos/<owner>/<repo>/pulls/<number>/reviews" \
--jq '[.[] | select(.body | startswith("## /bugteam loop "))] |
sort_by(.submitted_at) | reverse'
```

Iterate from index 0 (most recent) toward older entries:

- A bugteam review body that ends with `→ clean` is **clean**; any other `##
  /bugteam loop ...` body is **dirty**.
- For a dirty review, increment `dirty_review_count` by one. The review's
  specific finding bodies are not carried forward —
  bugteam's AUDIT regenerates
  findings against the current HEAD's diff each loop, so prior bodies are stale
  by definition. The count alone is the carried signal.
- Stop at the first clean review. Older reviews are presumed addressed at that
  clean checkpoint and are not re-read.
- When index 0 is itself clean AND its `commit_id` matches `git rev-parse HEAD`,
  the PR is already converged on this HEAD — set `last_action="audited"`,
  `last_findings='{"total": 0}'`, fall through to step 1's `converged` exit,
  skip Step 3 iteration entirely.
- When `dirty_review_count > 0`, log the count and proceed into the normal
  iteration; the next AUDIT regenerates anchored findings against the current
  HEAD so `loop_comment_index` stays correct. Unlike `pr-converge` — where
  Cursor Bugbot's prior dirty-review *bodies* are read back by the Fix protocol
  because each dirty body lists specific findings the loop must still address
  —
  bugteam's per-loop bodies are anchored to the diff at *that loop's* HEAD, so
  re-applying them against a newer diff would be incorrect. The count is
  sufficient signal that "prior loops did not converge here."

1. From `last_action` / `last_findings`:
   - `last_action == "audited"` and `last_findings.total == 0` → exit
     `converged`
   - `last_action == "fixed"` and `git rev-parse HEAD` unchanged since
     pre-FIX → exit `stuck`
   - `last_action in {"fresh", "fixed"}` → **pre-audit** then **AUDIT**
   - `last_action == "audited"` and `last_findings.total > 0` → **FIX**

2. **Pre-audit** (only when the next step is AUDIT):

   ```bash
   python \
     "${CLAUDE_SKILL_DIR}/../../_shared/pr-loop/scripts/code_rules_gate.py" \
     --base origin/<baseRefName>
   ```

Lead only; merge-base / diff semantics:
[`../../_shared/pr-loop/code-rules-gate.md`][path-code-rules]; shared script
inventory: [`../../_shared/pr-loop/scripts/README.md`][path-scripts-readme].
Non-zero → spawn **clean-coder** standards-fix (read stderr, edit, re-run
**this same** command, one commit, `git push`, shutdown) until exit **0** or
**5**
failed gate rounds → `error: code rules gate failed pre-audit`. After **0**:
`loop_count += 1`; if `loop_count > 10` → `cap reached`. Then **AUDIT**
(bugfind); print `Loop <N> audit: ...`.

3. **FIX** (`last_action == "audited"` and `last_findings.total > 0`):
   `loop_count += 1`; if `loop_count > 10` → `cap reached`; **FIX** (bugfix);
   print `Loop <N> fix: ...`; `last_action = "fixed"`, update `audit_log`; loop
   to step 1.

4. After **AUDIT**: update `last_action`, `last_findings`, `audit_log`; print
   audit line if not already printed.

5. Loop.

First pass: pre-audit → AUDIT. After a FIX, the next pass runs pre-audit again
before the next AUDIT.

### AUDIT action

```bash
mkdir -p "<team_temp_dir>/pr-<N>"
gh pr diff <N> -R <owner>/<repo> > "<team_temp_dir>/pr-<N>/loop-<L>.patch"
```

**Spawn and shutdown:** Path A —
[`reference/workflow-path-a-orchestrated-teams.md`][path-a] § AUDIT. Path B —
[`reference/workflow-path-b-task-harness.md`][path-b] § AUDIT. Same
`prompt="<audit XML; see PROMPTS.md>"` and outcome files.

Fresh spawn each loop; Path A teammate context excludes lead history
([`sources.md`](sources.md) § Teammate context isolation). Path B: fresh Task
per loop for the same clean-room intent. [`PROMPTS.md`](PROMPTS.md): XML +
outcome schema. Lead reads `.bugteam-pr<N>-loop<L>.outcomes.xml`, fills
`loop_comment_index`.

`last_action = "audited"`; append audit line to `audit_log`.

**Parallel auditors (`loop_count >= 4`):** gate passes immediately before;
after three full audit/fix rounds without convergence, issue three spawns in
one assistant message (parallel): Path A — three `Agent` calls; Path B —
three `Task` calls — full rules in the workflow files § parallel auditors.
`-a` posts
the review and merges outcomes from `-b`/`-c` (read
`.bugteam-pr<N>-loop<L>.outcomes.xml` plus
`<team_temp_dir>/pr-<N>/loop-<L>-b.outcomes.xml` and `...-c...`); merge key
`(file, line, category_letter)`; re-id `loopN-K`. `-b`/`-c` write sibling XML
only; prompts must pass literal absolute sibling paths. Shutdown order: Path A
workflow § parallel auditors; Path B: await all three Tasks.

### FIX action

**Spawn and shutdown:** Path A —
[`reference/workflow-path-a-orchestrated-teams.md`][path-a] § FIX. Path B —
[`reference/workflow-path-b-task-harness.md`][path-b] § FIX.

Pass finding comment URLs/ids from `loop_comment_index` in XML. Replies: `Fixed
in <sha>` or `Could not address this loop: <reason>`.

[`PROMPTS.md`](PROMPTS.md): fix XML + schema. Verify: `git rev-parse HEAD`
advanced; `git fetch origin <branch> && git rev-parse origin/<branch>` matches
`HEAD`. Unchanged HEAD →
`stuck — bugfix teammate could not address findings`.

### Step 4: Teardown

1. For each PR in `all_prs`: `git worktree remove
   "<team_temp_dir>/pr-<N>/worktree"` (from Step 1) before tearing down the team
   harness — tolerate already-removed worktrees.

2. Path-specific harness —
   [`reference/workflow-path-a-orchestrated-teams.md`][path-a] § Step 4
   (teammate `SendMessage`, `TeamDelete` **only when `team_owned=true`**) or
   [`reference/workflow-path-b-task-harness.md`][path-b] § Step 4 (omit those).

3. **Windows-safe `rmtree` — gated by `team_owned` from [Team
   lifecycle](#team-lifecycle-path-a-only).** The Windows-safe handler strips
   the Windows ReadOnly attribute and retries the failing syscall (see
   `~/.claude/rules/windows-filesystem-safe.md`).

   - `team_owned=true` → remove the full `<team_temp_dir>`:

     ```bash
python -c "import os, shutil, stat, sys; \
h = lambda f, p, *_: (os.chmod(p, stat.S_IWRITE), f(p)); \
shutil.rmtree(r'<team_temp_dir>', **({'onexc': h} if sys.version_info >= (3, 12)
else {'onerror': h}))"
     ```

   - `team_owned=false` (attach mode) → for each PR in `all_prs`, remove only
     that PR's `<team_temp_dir>/pr-<N>/` subfolder. The orchestrator-owned
     parent `<team_temp_dir>` survives so the next attached invocation can write
     its own per-PR subfolders without colliding.

     ```bash
python -c "import os, shutil, stat, sys; \
h = lambda f, p, *_: (os.chmod(p, stat.S_IWRITE), f(p)); \
shutil.rmtree(r'<team_temp_dir>/pr-<N>', **({'onexc': h} if sys.version_info >=
(3, 12) else {'onerror': h}))"
     ```

### Step 4.5: PR description

Lead only; cumulative product narrative (not process). Delegate body to
`pr-description-writer` via `Agent` (else `general-purpose`) so the
mandatory-pr-description hook accepts `gh pr edit`.

1. `gh pr diff <number> -R <owner>/<repo> > .bugteam-final.diff`
2. `gh pr view <number> -R <owner>/<repo> --json body --jq .body >
   .bugteam-original-body.md`
3. Agent brief: paths + branch names; describe merge-ready change from diff;
   keep curated original sections intact; return markdown body.
4. Write `.bugteam-final-body.md`; `gh pr edit <number> -R <owner>/<repo>
   --body-file .bugteam-final-body.md`
5. Delete the three temp files.

On failure: log in final report; continue to Step 5.

### Step 5: Revoke permissions (always)

```bash
python
"${CLAUDE_SKILL_DIR}/../../_shared/pr-loop/scripts/revoke_project_claude_permi \
ssions.py"
```

Removes Step 0 grant — run even if Step 4 partially failed (log separately).

### Step 6: Final report

```
/bugteam exit: <converged | cap reached | stuck | error>
Loops: <loop_count>
Starting commit: <starting_sha7>
Final commit: <current_HEAD_sha7>
Net change: <total_files> files, +<total_add>/-<total_del>

Loop log:
1 audit: 3P0 2P1 0P2
...
```

`cap reached` → suggest `/findbugs`. `stuck` → which findings. `error` →
detail + loop.

## Constraints

See [`CONSTRAINTS.md`](CONSTRAINTS.md).

## Examples

See [`EXAMPLES.md`](EXAMPLES.md).

## Reference

See [`reference/README.md`](reference/README.md).

## Sources

See [`sources.md`](sources.md).

[path-a]: reference/workflow-path-a-orchestrated-teams.md
[path-b]: reference/workflow-path-b-task-harness.md
[path-code-rules]: ../../_shared/pr-loop/code-rules-gate.md
[path-scripts-readme]: ../../_shared/pr-loop/scripts/README.md
