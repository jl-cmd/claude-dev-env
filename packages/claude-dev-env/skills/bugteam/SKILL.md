---
name: bugteam
description: >-
  Claude Code agent team on the open pull request: run the CODE_RULES gate,
  spawn a fresh clean-room audit (code-quality-agent, opus) and a fix pass
  (clean-coder, opus), post per-loop GitHub review threads from teammates,
  stop at zero findings or a 10-audit safety cap. Grants then revokes
  `.claude/**` edit permission around the run. SKILL.md is the orchestration
  checklist; `reference/` holds expanded prose by domain; CONSTRAINTS,
  PROMPTS, EXAMPLES, and sources are companion files. Requires
  CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1. Triggers: '/bugteam',
  'run the bug team', 'auto-fix the PR until clean', 'loop audit and fix'.
---

# Bugteam

**Core principle:** Agent team runs audit–fix until convergence. Bugfind: clean-room audit (fresh context each loop). Bugfix: addresses findings. Hard cap: 10 audit loops. Grant `.claude/**` permissions at start, revoke always at end.

Subagents fold back into the lead context; agent-team teammates do not — that separation is the clean-room guarantee. Verbatim doc quotes and URLs: [`sources.md`](sources.md).

## Contents

Orchestration lives here; companion files hold prompts, invariants, examples, citations, and domain reference notes. Scan this list before a partial read.

- When this skill applies — refusal cases (4) and trigger conditions
- Utility scripts — pre-flight (`scripts/`, executed not inlined)
- Pre-audit gate — `validate_content` before each AUDIT
- The Process — checklist + Steps 0–6
  - Step 0 — Grant project permissions
  - Step 1 — Resolve PR scope
  - Step 2 — Create the agent team
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
- [`reference/README.md`](reference/README.md) — expanded prose by topic (design, team setup, GitHub reviews, cycle, teardown)

## When this skill applies

`/bugteam` once authorizes the full cycle (up to 10 audits + fixes).

Refusals — first match wins; respond with the quoted line exactly and stop:

- **Agent teams not enabled.** Check `claude config get env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` and `~/.claude/settings.json`. If neither is `"1"`: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 not set. /bugteam requires the agent teams feature. See https://code.claude.com/docs/en/agent-teams#enable-agent-teams.`
- **No PR or upstream diff.** `No PR or upstream diff. /bugteam needs a target.`
- **Dirty tree.** `Uncommitted changes detected. Stash, commit, or revert before /bugteam.`
- **Missing subagents.** Before Step 0, confirm `code-quality-agent` and `clean-coder` exist. Else: `Required subagent type <name> not installed. /bugteam needs both code-quality-agent and clean-coder available.`
- **Lead role must be held by the orchestrator.** Run /bugteam in the session that received the user's command. The orchestrator session calls TeamCreate directly. Runtime confirms a single lead per team: `Already leading team "<name>". A leader can only manage one team at a time.`

## Utility scripts

Shell-heavy steps live under `scripts/` (run, do not paste into context). Utility scripts are **executed**, not loaded as primary context ([`sources.md`](sources.md) § Progressive disclosure and utility scripts). [`scripts/README.md`](scripts/README.md).

### Pre-flight (before Step 0)

```bash
python "${CLAUDE_SKILL_DIR}/scripts/bugteam_preflight.py"
```

Non-zero → fix before grant. `BUGTEAM_PREFLIGHT_SKIP=1` emergency only. `--pre-commit` if `.pre-commit-config.yaml` exists.

**Auto-remediation for `core.hooksPath`:** when preflight fails with stderr containing `core.hooksPath` (the message starts with `bugteam_preflight: core.hooksPath is`, or `Git-side CODE_RULES enforcement is not active`), Claude must auto-invoke the fix script — do not fall through to `AskUserQuestion`, do not punt to the user, do not ask for confirmation:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/bugteam_fix_hookspath.py"
```

The fix script removes any non-canonical local-scope override on the active repository, sets the global `core.hooksPath` to `~/.claude/hooks/git-hooks` if missing or wrong, and re-runs `bugteam_preflight.py`. Its exit code becomes the preflight outcome. Exit 0 → continue to Step 0. Non-zero only when the canonical hooks directory is missing (run `npx claude-dev-env .` first) or `git config --global` writes are blocked. Other preflight failures (pytest, pre-commit) still require manual fixes — the auto-remediation only applies to the `core.hooksPath` failure mode.

## The Process

### Progress checklist

```
[ ] Step 0: project permissions granted
[ ] Step 1: PR scope resolved
[ ] Step 2: agent team created + loop state set
[ ] Step 2.6: INITIAL standards review against cumulative PR diff
[ ] Step 3: cycle complete (converged | cap reached | stuck | error)
[ ] Step 3.5: FINAL standards review against cumulative PR diff
[ ] Step 4: team torn down + working tree clean
[ ] Step 4.5: PR description rewritten (or skip warning logged)
[ ] Step 5: project permissions revoked
[ ] Step 6: final report printed
```

### Step 0: Grant project permissions (once, first)

```bash
python "${CLAUDE_SKILL_DIR}/scripts/grant_project_claude_permissions.py"
```

`${CLAUDE_SKILL_DIR}` is host-substituted before the shell runs (unlike normal env expansion). Idempotent writes to `~/.claude/settings.json` from repo root. Non-zero → stop. Revoke in Step 5 on every exit path.

### Step 1: Resolve PR scope (once)

Accept one or more PR numbers from the invocation. For each PR, run `gh pr view --json number,baseRefName,headRefName,url` (falling back to the merge-base diff path when no PR exists). Capture `all_prs = [{number, owner, repo, baseRef, headRef, url}, ...]`. A single-PR invocation produces a one-element list and follows the same downstream rules.

Keep: owner/repo, branches, PR number, URL — for all loops.

#### Per-PR workspace

For each PR in all_prs:

1. Create `<team_temp_dir>/pr-<N>/`.
2. Run `git worktree add "<team_temp_dir>/pr-<N>/worktree" origin/<headRef>`.
3. Record the absolute worktree path alongside the PR's other fields.

Teammates spawned for a PR operate inside that PR's worktree. Step 4 teardown runs `git worktree remove "<team_temp_dir>/pr-<N>/worktree"` for each PR before `TeamDelete`.

### Step 2: Create the agent team

**This session is the lead.** The orchestrator calls `TeamCreate` directly:

```
TeamCreate(
  team_name="<team_name>",
  description="Bugteam audit/fix loop for PR <number> (<owner>/<repo>)",
  agent_type="team-lead"
)
```

**Team name:** For a single-PR invocation use `bugteam-pr-<number>-<YYYYMMDDHHMMSS>`. For a multi-PR invocation use `bugteam-<YYYYMMDDHHMMSS>`. The timestamp is captured once at team-creation time. Apply the no-PR fallback (`bugteam-<sanitized-head>-<YYYYMMDDHHMMSS>`) only when no PR resolves at all. `TeamCreate` implements natural-language team creation ([`sources.md`](sources.md) § Team creation in natural language).

**Sanitize head branch (no-PR only):** replace characters outside `[A-Za-z0-9._-]` with `-` (e.g. `feat/foo*bar` → `feat-foo-bar`). Apply once; reuse everywhere below.

**`<team_temp_dir>`:** `Path(tempfile.gettempdir()) / team_name` (lead resolves once to an absolute path; every shell gets that literal string).

**Roles (spawned per loop, not here):** bugfind → `code-quality-agent` opus (4.7) at xhigh effort; bugfix → `clean-coder` opus (4.7) at xhigh effort. `model="opus"` resolves to Opus 4.7 on the Anthropic API and runs at the model's default `xhigh` effort level — see [`CONSTRAINTS.md`](CONSTRAINTS.md) § **Opus 4.7 at xhigh effort for both teammates** for rationale. **Display:** inherit `teammateMode` from `~/.claude.json`. Reference subagent types by name when spawning teammates ([`sources.md`](sources.md) § Referencing subagent types when spawning teammates).

**Optional Groq-backed FIX path (explicit opt-in only):** the default flow above always uses Opus teammates. A separate optional path exists only when the user explicitly sets `BUGTEAM_FIX_IMPLEMENTER=groq-coder` before invocation: spawn the FIX teammate with `subagent_type="groq-coder"`. Before Step 3, `groq_bugteam.py` loads `packages/claude-dev-env/.env` when that file exists (gitignored; start from `packages/claude-dev-env/.env.example`). If `GROQ_API_KEY` is still unset after that load, stop and prompt the user to create `packages/claude-dev-env/.env` from the example path above—do not continue the Groq path without a key. Any other `BUGTEAM_FIX_IMPLEMENTER` value (or unset) keeps `clean-coder` on Opus. The FIX spawn XML in [`PROMPTS.md`](PROMPTS.md) is identical for both implementers.

**`--bugbot-retrigger` flag:** when present on the `/bugteam` invocation, after every successful FIX push in Step 3, post an additional `bugbot run` issue comment via the Step 2.5 issue-comments fallback endpoint (`POST .../issues/{issue}/comments`) to re-trigger Cursor's bugbot on the new commit. Omit when the flag is absent.

**Loop state (lead; not a single script):**

```bash
loop_count=0
last_action="fresh"
last_findings=""
audit_log=""
starting_sha="$(git rev-parse HEAD)"
team_name="bugteam-pr-<number>-<YYYYMMDDHHMMSS>"
team_temp_dir="<absolute-path>/<team_name>"
loop_comment_index=""
```

**`loop_comment_index`:** reset each AUDIT start; filled during AUDIT; FIX consumes for replies; cleared after FIX. Entries: `{loop, finding_id, finding_comment_id, finding_comment_url, used_fallback, fix_status}`.

### Step 2.5: PR comments (one review per loop)

Bugfind posts one `POST .../pulls/<n>/reviews` per loop after audit (body + `comments[]` for anchored P0/P1/P2). Bugfix posts `.../comments/<id>/replies` after push. Lead’s only PR write: Step 4.5 body edit.

Order: audit → buffer → validate anchors vs diff → single review POST. Review body states counts; zero findings → still one review, `comments: []`, body `## /bugteam loop <N> audit: 0P0 / 0P1 / 0P2 → clean`.

**Payloads:** build JSON with `jq --rawfile` / `-Rs`, pipe to `gh api ... --input -` (avoids shell-quoting; satisfies `gh-body-backtick-guard`). Write each markdown body to a temp file first.

**Review POST** (one `comments[]` object per anchored finding; single-line `{path, line, side: "RIGHT", body}`; multi-line add `start_line`, `start_side: "RIGHT"`):

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

**Fix reply:** `jq -Rs '{body: .}' <tmp_reply.md | gh api repos/<owner>/<repo>/pulls/<number>/comments/<finding_comment_id>/replies -X POST --input -`

**Review POST fails:** issue comment fallback: `jq -Rs '{body: .}' <tmp_fallback.md | gh api repos/<owner>/<repo>/issues/<number>/comments -X POST --input -`

`<head_sha_at_post_time>`: `git rev-parse HEAD` in teammate cwd immediately before POST.

**Review body template (`<tmp_review_body.md>`):**

```
## /bugteam loop <N> audit: <P0>P0 / <P1>P1 / <P2>P2

### Findings without a diff anchor
(only if needed)
- **[severity] title** — <file>:<line> — <one-line description>
```

**Anchor fallback:** lines not in diff → omit from `comments[]`, list under `### Findings without a diff anchor`; outcome `used_fallback="true"`, empty `finding_comment_id`, `finding_comment_url` = parent review URL.

**POST failure fallback:** one issue comment with full text; all findings `used_fallback="true"`, URLs = issue comment.

**Endpoints:** `POST .../pulls/{pull}/reviews`; `POST .../pulls/{pull}/comments/{id}/replies`; fallback `POST .../issues/{issue}/comments` (`issue` = PR number).

### Step 2.6: INITIAL standards review (once, before Loop 1 audit)

Run BEFORE the first pre-audit gate fires. Spawn a fresh `code-quality-agent`
teammate inside the same team and drive it through the K–N addendum (see
PROMPTS.md `<copilot_derived_addendum_source>`). The teammate audits the
cumulative PR diff (`gh pr diff <N>`) instead of a single loop's incremental
patch; clean-room context is preserved by the same agent-team isolation as
the per-loop bugfind teammate. Findings are posted using the same Step 2.5
review-shape with body `## /bugteam INITIAL standards review against PR #<N>
cumulative diff: <P0>P0 / <P1>P1 / <P2>P2`. Findings advance the audit/fix
cycle exactly as if they had been raised in Loop 1: the lead increments
`loop_count` to 1, sets `last_action = "audited"` with the merged
`last_findings`, and Step 3 begins on the FIX branch. When the INITIAL
review returns zero findings, `loop_count` stays at 0 and Step 3 begins on
the AUDIT branch as before. Failure on this phase logs the error and
proceeds to Step 3 unchanged so the legacy A–J cycle still runs.

### Step 3: The cycle

Run the AUDIT-FIX cycle for each PR in all_prs, reusing the same team across PRs. The 10-loop cap applies per PR. Exit reasons (converged, cap reached, stuck, error) are tracked per PR; the final report lists one outcome line per PR.

**Gate:** `validate_content` / `hooks/blocking/code_rules_enforcer.py` on PR-scoped files before every AUDIT (`bugteam_code_rules_gate.py`). Lead runs gate; clean-coder clears failures; then bugfind audits.

1. From `last_action` / `last_findings`:
   - `last_action == "audited"` and `last_findings.total == 0` → exit `converged`
   - `last_action == "fixed"` and `git rev-parse HEAD` unchanged since pre-FIX → exit `stuck`
   - `last_action in {"fresh", "fixed"}` → **pre-audit** then **AUDIT**
   - `last_action == "audited"` and `last_findings.total > 0` → **FIX**

2. **Pre-audit** (only when the next step is AUDIT):

   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/bugteam_code_rules_gate.py" --base origin/<baseRefName>
   ```

   Lead only; merge-base / diff details in [`scripts/README.md`](scripts/README.md). Non-zero → spawn **clean-coder** standards-fix (read stderr, edit, re-run **this same** command, one commit, `git push`, shutdown) until exit **0** or **5** failed gate rounds → `error: code rules gate failed pre-audit`. After **0**: `loop_count += 1`; if `loop_count > 10` → `cap reached`. Then **AUDIT** (bugfind); print `Loop <N> audit: ...`.

3. **FIX** (`last_action == "audited"` and `last_findings.total > 0`): `loop_count += 1`; if `loop_count > 10` → `cap reached`; **FIX** (bugfix); print `Loop <N> fix: ...`; `last_action = "fixed"`, update `audit_log`; loop to step 1.

4. After **AUDIT**: update `last_action`, `last_findings`, `audit_log`; print audit line if not already printed.

5. Loop.

First pass: pre-audit → AUDIT. After a FIX, the next pass runs pre-audit again before the next AUDIT.

### AUDIT action

```bash
mkdir -p "<team_temp_dir>/pr-<N>"
gh pr diff <N> -R <owner>/<repo> > "<team_temp_dir>/pr-<N>/loop-<L>.patch"
```

```
Agent(
  subagent_type="code-quality-agent",
  name="bugfind-pr<N>-loop<L>",
  team_name="<team_name>",
  model="opus",
  description="Bugfind audit PR <N> loop <L>",
  prompt="<audit XML; see PROMPTS.md>"
)
```

Fresh `Agent` each loop; teammate context excludes lead history ([`sources.md`](sources.md) § Teammate context isolation). [`PROMPTS.md`](PROMPTS.md): XML + outcome schema. Lead reads `.bugteam-pr<N>-loop<L>.outcomes.xml`, fills `loop_comment_index`.

**Shutdown:** If `Agent` returned and the teammate already ended, skip. Otherwise:

```
SendMessage(
  to="bugfind-pr<N>-loop<L>",
  message={"type": "shutdown_request", "reason": "audit PR <N> loop <L> complete; outcome XML captured"}
)
```

`approve: false` → `error: bugfind teammate refused shutdown` → Step 4 then 5.

`last_action = "audited"`; append audit line to `audit_log`.

**Parallel auditors (`loop_count >= 4`):** gate passes immediately before; after three full audit/fix rounds without convergence, issue three `Agent` calls in one assistant message (parallel). `-a` posts the review and merges outcomes from `-b`/`-c` (read `.bugteam-pr<N>-loop<L>.outcomes.xml` plus `<team_temp_dir>/pr-<N>/loop-<L>-b.outcomes.xml` and `...-c...`); merge key `(file, line, category_letter)`; re-id `loopN-K`. `-b`/`-c` write sibling XML only; prompts must pass literal absolute sibling paths. Shutdown: parallel `SendMessage` to `b` and `c`, then `a`.

### FIX action

```
Agent(
  subagent_type="clean-coder",
  name="bugfix-pr<N>-loop<L>",
  team_name="<team_name>",
  model="opus",
  description="Bugfix PR <N> loop <L>",
  prompt="<fix XML; see PROMPTS.md>"
)
```

Pass finding comment URLs/ids from `loop_comment_index` in XML. Replies: `Fixed in <sha>` or `Could not address this loop: <reason>`.

**Shutdown:** same as bugfind; else `SendMessage(to="bugfix-pr<N>-loop<L>", message={"type": "shutdown_request", "reason": "fix PR <N> loop <L> complete; commit <sha7> pushed"})`. `approve: false` → `error: bugfix teammate refused shutdown` → Step 4 then 5.

[`PROMPTS.md`](PROMPTS.md): fix XML + schema. Verify: `git rev-parse HEAD` advanced; `git fetch origin <branch> && git rev-parse origin/<branch>` matches `HEAD`. Unchanged HEAD → `stuck — bugfix teammate could not address findings`.

### Step 3.5: FINAL standards review (once, after convergence)

Run AFTER Step 3 exits with `converged`, `cap reached`, or `stuck`, and
BEFORE Step 4 teardown. Spawn one more fresh `code-quality-agent` teammate;
audit the cumulative PR diff against the K–N addendum a second time. Post
the review with body `## /bugteam FINAL standards review against PR #<N>
cumulative diff: <P0>P0 / <P1>P1 / <P2>P2`. When findings remain, the
exit reason is upgraded to `error: final standards review found <P0>+<P1>+<P2>
unresolved finding(s)` and the loop log gains an extra `final-review` line.
A clean FINAL review preserves the existing exit reason. Failure on this
phase logs the error and continues to Step 4 unchanged so teardown,
permission revoke, and the final report still run.

### Step 4: Teardown

1. For each live teammate: `SendMessage(to="<name>", message={"type": "shutdown_request", "reason": "bugteam cycle ending"})`. `approve: false` on cleanup → log and continue.

2. `TeamDelete()`

3. Windows-safe teardown — `ignore_errors=True` silently swallows ReadOnly-attribute failures on Windows (see `~/.claude/rules/windows-filesystem-safe.md`). Use the inline `force_rmtree` helper:

   ```bash
   python -c "import os, shutil, stat, sys; \
   h = lambda f, p, *_: (os.chmod(p, stat.S_IWRITE), f(p)); \
   shutil.rmtree(r'<team_temp_dir>', **({'onexc': h} if sys.version_info >= (3, 12) else {'onerror': h}))"
   ```

### Step 4.5: PR description

Lead only; cumulative product narrative (not process). Delegate body to `pr-description-writer` via `Agent` (else `general-purpose`) so the mandatory-pr-description hook accepts `gh pr edit`.

1. `gh pr diff <number> -R <owner>/<repo> > .bugteam-final.diff`
2. `gh pr view <number> -R <owner>/<repo> --json body --jq .body > .bugteam-original-body.md`
3. Agent brief: paths + branch names; describe merge-ready change from diff; keep curated original sections intact; return markdown body.
4. Write `.bugteam-final-body.md`; `gh pr edit <number> -R <owner>/<repo> --body-file .bugteam-final-body.md`
5. Delete the three temp files.

On failure: log in final report; continue to Step 5.

### Step 5: Revoke permissions (always)

```bash
python "${CLAUDE_SKILL_DIR}/scripts/revoke_project_claude_permissions.py"
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
  initial standards review: 1P0 0P1 2P2
  1 audit: 3P0 2P1 0P2
  ...
  final standards review: 0P0 0P1 0P2
```

`cap reached` → suggest `/findbugs`. `stuck` → which findings. `error` → detail + loop.

## Constraints

See [`CONSTRAINTS.md`](CONSTRAINTS.md).

## Examples

See [`EXAMPLES.md`](EXAMPLES.md).

## Reference

See [`reference/README.md`](reference/README.md).

## Sources

See [`sources.md`](sources.md).
