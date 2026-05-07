---
name: bugteam
description: >-
  Open pull request audit–fix until convergence: CODE_RULES gate, clean-room
  audit (`code-quality-agent`, opus) and fix (`clean-coder`, opus), per-loop
  GitHub reviews, 10-audit cap; grant then revoke `.claude/**`. Spawns
  background subagents (`Agent(..., run_in_background=true)`). Triggers: '/bugteam', 'run
  the bug team', 'auto-fix the PR until clean', 'loop audit and fix'.
---

# Bugteam

**Core principle:** Audit–fix until convergence. **Bugfind:**
`code-quality-agent`, fresh context each loop. **Bugfix:** `clean-coder`. Hard
cap: 10 audit loops. Grant `.claude/**` at start, revoke always at end.

Both audit and fix roles run as background subagents
(`Agent(..., run_in_background=true)`). Verbatim doc quotes and URLs:
[`sources.md`](sources.md).

## Contents

Orchestration lives here; companion files hold prompts, invariants, examples,
citations, and domain reference notes. Scan this list before a partial read.

- When this skill applies — refusal cases and trigger conditions
- Utility scripts — pre-flight (`scripts/`, executed not inlined)
- Pre-audit gate — `validate_content` before each AUDIT
- The Process — checklist + Steps 0–6
  - Step 0 — Grant project permissions
  - Step 1 — Resolve PR scope
  - Step 2 — Loop state
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
[ ] Step 2: loop state set
[ ] Step 3: cycle complete (converged | cap reached | stuck | error)
[ ] Step 4: working tree clean
[ ] Step 4.5: PR description rewritten (or skip warning logged)
[ ] Step 5: project permissions revoked
[ ] Step 6: final report printed
```

### Step 0: Grant project permissions (once, first)

```bash
python \
"${CLAUDE_SKILL_DIR}/../../_shared/pr-loop/scripts/"\
"grant_project_claude_permissions.py"
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

**`<run_temp_dir>`:** `Path(tempfile.gettempdir()) / run_name` where
`run_name = "bugteam-pr-<number>-<YYYYMMDDHHMMSS>"` for a single-PR invocation
or `"bugteam-<YYYYMMDDHHMMSS>"` for multi-PR. Lead resolves once to an absolute
path; every shell gets that literal string.

#### Per-PR workspace

For each PR in all_prs:

1. Create `<run_temp_dir>/pr-<N>/`.
2. Run `git worktree add "<run_temp_dir>/pr-<N>/worktree" origin/<headRef>`.
3. Record the absolute worktree path alongside the PR's other fields.

Background subagents for a PR operate inside that PR's worktree. Step 4
teardown runs `git worktree remove "<run_temp_dir>/pr-<N>/worktree"` for each
PR before the shared `rmtree`.

### Step 2: Loop state

**Loop state (lead; not a single script; per-PR):** The variables
below are tracked independently for each PR in `all_prs`. Each PR has its
own cycle, state, and exit reason.

```bash
loop_count=0
last_action="fresh"
last_findings='{"total": 0}'
audit_log=""
run_temp_dir="<absolute-path>/<run_name>"
starting_sha="$(git -C "<run_temp_dir>/pr-<N>/worktree" rev-parse HEAD)"
loop_comment_index=""
```

**Optional Groq-backed FIX (explicit opt-in only):** when the user explicitly
sets `BUGTEAM_FIX_IMPLEMENTER=groq-coder` before invocation, spawn the FIX
subagent with `subagent_type="groq-coder"`. Requires `GROQ_API_KEY` in the
environment (load from `packages/claude-dev-env/.env` when that file exists;
prompt the user to create it from `.env.example` if still unset). Any other
`BUGTEAM_FIX_IMPLEMENTER` value (or unset) uses `clean-coder`.

**`--bugbot-retrigger` flag:** when present, the FIX subagent posts a `bugbot
run` issue comment via the Step 2.5 issue-comments fallback endpoint after
every successful FIX push, to re-trigger Cursor's bugbot on the new commit.

**`loop_comment_index`:** reset each AUDIT start; filled during AUDIT; FIX
consumes for replies; cleared after FIX. Entries: `{loop, finding_id,
finding_comment_id, finding_comment_url, used_fallback, fix_status}`.

### Step 2.5: PR comments (one review per loop)

**Who posts:** the AUDIT subagent posts one `POST .../pulls/<n>/reviews` per
loop. The FIX subagent posts `.../comments/<id>/replies` after push. The lead's
only PR write before Step 4.5 is the final description rewrite.

Order: audit → buffer → validate anchors vs diff → single review POST.
Review body states counts; zero findings → still one review, `comments: []`,
body `## /bugteam loop <L> audit: 0P0 / 0P1 / 0P2 → clean`.

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

`<head_sha_at_post_time>`: `git rev-parse HEAD` in subagent cwd immediately
before POST.

**Review body template (`<tmp_review_body.md>`):**

```
## /bugteam loop <L> audit: <P0>P0 / <P1>P1 / <P2>P2

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

Run the AUDIT-FIX cycle for each PR in all_prs. The 10-loop cap applies per PR. Exit reasons (converged, cap reached,
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
gh api "repos/<owner>/<repo>/pulls/<number>/reviews?per_page=100" --paginate --slurp \
  | jq '[.[][] | select((.body // "") | startswith("## /bugteam loop "))] | sort_by(.submitted_at) | reverse'
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
Non-zero → spawn **clean-coder** standards-fix (`mode="bypassPermissions"`) (read stderr, edit, re-run
**this same** command, one commit, `git push`, shutdown) until exit **0** or
**5**
failed gate rounds → `error: code rules gate failed pre-audit`. After **0**:
`loop_count += 1`; if `loop_count > 10` → `cap reached`. Then **AUDIT**
(bugfind); print `Loop <L> audit: ...`.

3. **FIX** (`last_action == "audited"` and `last_findings.total > 0`):
   `loop_count += 1`; if `loop_count > 10` → `cap reached`; **FIX** (bugfix);
   print `Loop <L> fix: ...`; `last_action = "fixed"`, update `audit_log`; loop
   to step 1.

4. After **AUDIT**: update `last_action`, `last_findings`, `audit_log`; print
   audit line if not already printed.

5. Loop.

First pass: pre-audit → AUDIT. After a FIX, the next pass runs pre-audit again
before the next AUDIT.

### AUDIT action

```bash
mkdir -p "<run_temp_dir>/pr-<N>"
gh pr diff <N> -R <owner>/<repo> > "<run_temp_dir>/pr-<N>/loop-<L>.patch"
```

**Spawn:**

```
Agent(
  subagent_type="code-quality-agent",
  name="bugfind-pr<N>-loop<L>",
  model="opus",
  mode="bypassPermissions",
  run_in_background=true,
  description="Bugfind audit PR <N> loop <L>",
  prompt="<audit XML; see PROMPTS.md>"
)
```

Fresh spawn each loop for clean-room isolation. Lead awaits the
background-completion notification, then reads
`.bugteam-pr<N>-loop<L>.outcomes.xml` from the worktree directory, fills
`loop_comment_index`. [`PROMPTS.md`](PROMPTS.md): XML + outcome schema.

`last_action = "audited"`; append audit line to `audit_log`.

**Parallel auditors (`loop_count >= 4`):** gate passes immediately before;
after three full audit/fix rounds without convergence, issue eleven `Agent`
calls in one assistant message (`run_in_background=true`):

- **10 haiku auditors (`-b` through `-k`):** `subagent_type="code-quality-agent"`,
  `model="haiku"`, `mode="bypassPermissions"`, write sibling XML to
  `<run_temp_dir>/pr-<N>/loop-<L>-<letter>.outcomes.xml`, skip PR posting.
  Prompts must pass literal absolute sibling paths.
- **1 opus validator (`-a`):** `subagent_type="code-quality-agent"`,
  `model="opus"`, `mode="bypassPermissions"`:
  - Polls for all 10 sibling XMLs before proceeding (60s timeout, 2s interval). On timeout: log diagnostics entry, proceed with validated findings from available XMLs, report count in validator output.
  - Validates each finding: file exists, line in bounds, excerpt contains the exact
    text of the cited line, category is A–J, severity is P0/P1/P2.
  - Hallucinated findings → quarantined to `<run_temp_dir>/pr-<N>/loop-<L>-diagnostics.json` under
    `validator_rejected` (added alongside the required diagnostics keys defined in the shared audit contract).
  - De-dups by `(file, line, category)`, max severity wins; on conflict, keep longest description text.
  - Re-ids as `loop<L>-<K>`.
  - Writes `<worktree_path>/.bugteam-pr<N>-loop<L>.outcomes.xml`, posts review.

Lead awaits the opus validator (-a) background-completion notification (120s
timeout). The validator independently polls all 10 sibling XMLs; the lead does
not gate on haiku peer completion. On lead timeout: the validator did not post
a merged review — treat as a hard blocker and abort the loop.

The sibling-output paths in [`PROMPTS.md`](PROMPTS.md) must cover the full
`-b` through `-k` range.

After the validator completes, lead runs `verify_review.py` to confirm exactly
one review was posted at the correct commit:

```bash
python <script_dir>/verify_review.py \
  --owner <owner> --repo <repo> --number <N> \
  --commit-id "$(git -C <worktree_path> rev-parse HEAD)" --loop <L>
```

Non-zero exit → lead checks for an existing fallback issue comment from
the validator. If one exists, use its URL directly. Otherwise, post a new
fallback issue comment with all findings inline from the outcome XML.
Populate `loop_comment_index` from the (existing or new) comment URL.
`<script_dir>` = absolute path to `_shared/pr-loop/scripts/`.

### FIX action

**Spawn:**

```
Agent(
  subagent_type="clean-coder",
  name="bugfix-pr<N>-loop<L>",
  model="opus",
  mode="bypassPermissions",
  run_in_background=true,
  description="Bugfix PR <N> loop <L>",
  prompt="<fix XML; see PROMPTS.md>"
)
```

Pass finding comment URLs/ids from `loop_comment_index` in XML. Lead awaits the
background-completion notification. Replies: `Fixed in <sha>` or `Could not
address this loop: <reason>`.

[`PROMPTS.md`](PROMPTS.md): fix XML + schema. Verify from worktree: `git -C "<run_temp_dir>/pr-<N>/worktree" rev-parse HEAD`
advanced; `git -C "<run_temp_dir>/pr-<N>/worktree" fetch origin <branch> && git -C "<run_temp_dir>/pr-<N>/worktree" rev-parse origin/<branch>` matches
`HEAD`. Unchanged HEAD →
`stuck — bugfix subagent could not address findings`.

**Scope verification.** Run `git diff HEAD~1 --name-only` and compare against the set of files referenced in bugs_to_fix. When the commit touches any file NOT in the bugs_to_fix list, downgrade the outcome to `unverified_fixed` with reason "commit touched unexpected files: <list>".

### Step 4: Teardown

1. For each PR in `all_prs`: `git worktree remove
   "<run_temp_dir>/pr-<N>/worktree"` (from Step 1) — tolerate already-removed
   worktrees.

2. **Windows-safe `rmtree`** — strips the Windows ReadOnly attribute and retries
   the failing syscall (see `~/.claude/rules/windows-filesystem-safe.md`).
   Remove the full `<run_temp_dir>`:

   ```bash
python -c "import os, shutil, stat, sys; \
h = lambda f, p, *_: (os.chmod(p, stat.S_IWRITE), f(p)); \
shutil.rmtree(r'<run_temp_dir>', **({'onexc': h} if sys.version_info >= (3, 12)
else {'onerror': h}))"
   ```

### Step 4.5: PR description

Lead only; cumulative product narrative (not process). Delegate body to
`pr-description-writer` via `Agent` (`mode="bypassPermissions"`) (else `general-purpose`) so the
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
python \
"${CLAUDE_SKILL_DIR}/../../_shared/pr-loop/scripts/"\
"revoke_project_claude_permissions.py"
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

[path-code-rules]: ../../_shared/pr-loop/code-rules-gate.md
[path-scripts-readme]: ../../_shared/pr-loop/scripts/README.md
