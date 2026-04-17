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

## Contents

This file is 400+ lines. The list below is for the LLM reading this skill — partial reads (e.g., `head -100`) miss what comes later, so this section ensures the full scope is visible from the top. (Per Anthropic's [Skill authoring best practices — Structure longer reference files with table of contents](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#structure-longer-reference-files-with-table-of-contents).)

- When this skill applies — refusal cases (4) and trigger conditions
- The Process — Progress checklist + Steps 0–6
  - Step 0 — Grant project permissions
  - Step 1 — Resolve PR scope
  - Step 2 — Create the agent team
  - Step 2.5 — PR comment lifecycle (loop comment, finding comments, fix replies)
  - Step 3 — The cycle (AUDIT ↔ FIX, decision table, exit conditions)
  - Step 4 — Tear down the team and clean working tree
  - Step 4.5 — Finalize the PR description (via pr-description-writer)
  - Step 5 — Revoke project permissions
  - Step 6 — Print the final report
- Constraints — invariants the implementer must preserve
- Examples — five end-to-end scenarios
- Why this design — rationale for agent-teams + clean-room + grant/revoke

## When this skill applies

User wants automated convergence on a clean PR without babysitting each step. Typed `/bugteam` once = full authorization for up to 10 audit cycles and the corresponding fix commits.

Refusal cases — check in order; first match short-circuits and stops:

- **Agent teams not enabled.** Check `claude config get env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` and `~/.claude/settings.json`. If neither sets it to `"1"`, respond: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 not set. /bugteam requires the agent teams feature. See https://code.claude.com/docs/en/agent-teams#enable-agent-teams.` and stop.
- **Claude Code version too old.** Run `claude --version`. If older than v2.1.32, respond: `Claude Code v<version> is older than the v2.1.32 minimum for agent teams. Upgrade first.` and stop.
- **No PR or upstream diff.** Respond exactly: `No PR or upstream diff. /bugteam needs a target.` and stop.
- **Working tree dirty with uncommitted changes the user did not stage.** Respond: `Uncommitted changes detected. Stash, commit, or revert before /bugteam.` and stop. Reason: the fix teammate will commit the working tree, mixing user-uncommitted work into automated fixes.
- **Required subagents not installed.** Before Step 0, verify `code-quality-agent` and `clean-coder` subagent types exist in the available agents list. If either is missing, respond: `Required subagent type <name> not installed. /bugteam needs both code-quality-agent and clean-coder available.` and stop.

## The Process

### Progress checklist (copy at start, tick as you go)

```
[ ] Step 0: project permissions granted
[ ] Step 1: PR scope resolved
[ ] Step 2: agent team created + initial loop state set
[ ] Step 3: cycle complete (converged | cap reached | stuck | error)
[ ] Step 4: team torn down + working tree clean
[ ] Step 4.5: PR description rewritten (or skip warning logged)
[ ] Step 5: project permissions revoked
[ ] Step 6: final report printed
```

### Step 0: Grant project permissions (mandatory, runs once)

Before spawning any teammates, grant the team session write access to the project's `.claude/**` tree:

```bash
python "${CLAUDE_SKILL_DIR}/grant_project_claude_permissions.py"
```

Note: `${CLAUDE_SKILL_DIR}` is a Claude Code host-managed token, pre-substituted by the runtime before any shell sees it. Unlike `${TMPDIR}` and similar shell parameter expansions, it does not depend on the shell's expansion semantics, so it works identically on Unix and Windows shells.

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

- **Team name:** `bugteam-pr-<number>-<YYYYMMDDHHMMSS>` (or `bugteam-<sanitized-head-branch>-<YYYYMMDDHHMMSS>` if no PR). The timestamp is captured at team-creation time from the lead session and prevents two concurrent invocations on the same PR from colliding.
- **Branch-name sanitization (no-PR fallback only):** Before substituting `<head-branch>` into the team_name template, replace every character that is NOT in `[A-Za-z0-9._-]` with `-`. This whitelist covers safe portable filename characters and rejects all OS-reserved or shell-special chars including `/ \ : * ? < > | "` and ASCII control chars (0x00–0x1F). Example: `feat/foo*bar` → `feat-foo-bar`; team_name becomes `bugteam-feat-foo-bar-<YYYYMMDDHHMMSS>`. Apply this sanitization BEFORE the team_name is captured, not after — every downstream use of `team_name` (team creation, scoped temp dir, cleanup) sees the safe form.
- **Per-team temp directory (resolved once, reused everywhere):** After team_name is captured, resolve a portable absolute path with a Claude-side lookup using Python's `tempfile.gettempdir()`, which honors `TMPDIR`, `TEMP`, and `TMP` in the platform-correct order and falls back to `C:\Users\<user>\AppData\Local\Temp` on Windows or `/tmp` on Unix: `Path(tempfile.gettempdir()) / team_name` (requires `import tempfile`). The `team_name` value already carries the `bugteam-` prefix, so do NOT add it again here. Avoid hand-rolled env var chains. Capture the resolved absolute path as `<team_temp_dir>` and pass that literal path to every shell command that follows. Shell-side parameter expansion (`${TMPDIR:-/tmp}`) is forbidden because cmd.exe and PowerShell do not expand it.
- **Roles defined up front (spawned per loop, not at team creation):**
  - `bugfind` — uses teammate role `code-quality-agent`, model sonnet
  - `bugfix` — uses teammate role `clean-coder`, model sonnet
- **Display mode:** inherit user's default (`teammateMode` in `~/.claude.json`); do not override.

Reference teammate role definitions by name when spawning. Per the docs: *"When spawning a teammate, you can reference a subagent type from any subagent scope: project, user, plugin, or CLI-defined. This lets you define a role once... and reuse it both as a delegated subagent and as an agent team teammate."*

Initialize loop state. The block below mixes lead-internal variables and one shell command (the SHA capture). Read it as instructions, not a literal script:

```bash
loop_count=0
last_action="fresh"
last_findings=""
audit_log=""
starting_sha="$(git rev-parse HEAD)"   # captured once, used in the final report
team_name="bugteam-pr-<number>-<YYYYMMDDHHMMSS>"  # no-PR fallback uses sanitized branch
team_temp_dir="<resolved-absolute-path>/<team_name>"
loop_comment_index=""                  # reset at every AUDIT, see scope note below
```

**`loop_comment_index` scope (per-loop, not cross-loop).** This list is reset at the start of every AUDIT action, populated as finding comments are posted during AUDIT, consumed by the matching FIX action when it posts fix replies, and discarded after FIX completes. It does not persist across loops; each loop starts with an empty index and its own fresh set of comment URLs.

Each entry: `{loop, finding_id, finding_comment_id, finding_comment_url, used_fallback, fix_status}`. Populated by AUDIT, consumed by FIX.

### Step 2.5: PR comment lifecycle (start simple)

The team narrates its work to the PR via GitHub comments so a reviewer can scan `/bugteam` activity inline with the code. **Teammates own all PR comment posting** — bugfind posts audit comments, bugfix posts fix replies. The lead never calls `gh pr comment` or `gh api repos/.../comments`. The lead's only PR-write action is the final description rewrite at Step 4.5 (via `pr-description-writer` agent).

- **Loop comment** — one top-level PR issue comment per loop. Posted by the bugfind teammate at the start of each loop. Body: short header naming the loop and the action. Example body:

  ```
  ## /bugteam loop <N>: audit running

  Clean-room audit on PR diff. Finding comments will appear below
  this line.
  ```

  New loop comment per loop, not one across loops — keeps each loop's section self-contained.

- **Finding comments** — inline review comments anchored to file:line in the diff. Posted by the bugfind teammate, one per P0/P1/P2 finding. Body: severity, category, description, and a `From /bugteam audit loop <N>` footer.

- **Fix replies** — replies to each finding comment. Posted by the bugfix teammate after the commit lands. Body: `Fixed in <commit_sha>` if addressed, or `Could not address this loop: <one-line reason>` if not.

This is the **simplest** comment shape that links findings and fixes inline. Do not add cross-loop threading, comment editing, thread resolution, batched reviews, or comment summarization in this version. Build out from observed behavior later.

CLI shapes (teammate runs these):

- Loop comment: `gh pr comment <number> -R <owner>/<repo> --body-file <tmp>` → returns the comment URL on stdout. (GitHub API name: issue comment.)
- Finding comment: `gh api repos/<owner>/<repo>/pulls/<number>/comments -X POST -f body=@<tmp> -f commit_id=<head_sha_at_post_time> -f path=<file> -F line=<line> -f side=RIGHT` → returns JSON; capture `id` and `html_url`. (GitHub API name: pull-request review comment.)
- Fix reply: `gh api repos/<owner>/<repo>/pulls/<number>/comments/<finding_comment_id>/replies -X POST -f body=@<tmp>` → returns JSON.

`<head_sha_at_post_time>` = the SHA at the moment the finding comment is posted (run `git rev-parse HEAD` in the teammate's working dir immediately before the POST). Each loop's audit anchors its finding comments to the head SHA at audit time, which is the SHA before this loop's fix lands.

Use `--body-file` everywhere, not `--body` — the existing `gh-body-backtick-guard` hook blocks inline bodies that contain backticks, and bug descriptions almost always contain code excerpts.

**Finding-comment failure fallback (teammate handles).** If the finding-comment POST fails (rate limit, line not in the diff, malformed payload, network), the bugfind teammate falls back to a top-level issue comment with the file:line in the body text and prefixes the body with `**Inline failed for <file>:<line>** — finding follows below.` The teammate logs the fallback in its outcome XML so the lead's final report can count fallbacks. Cycle continues; no single-comment failure aborts the loop.

### Step 3: The cycle

Repeat until an exit condition fires:

1. Increment `loop_count`. If `loop_count > 10`, exit reason = `cap reached`.
2. Decide the next action:
   - `last_action in {"fresh", "fixed"}` → run **AUDIT**
   - `last_action == "audited"` and `last_findings.total > 0` → run **FIX**
   - `last_action == "audited"` and `last_findings.total == 0` → exit reason = `converged`
   - `last_action == "fixed"` and `git rev-parse HEAD` did not change since pre-FIX → exit reason = `stuck` (see FIX action for detection)
3. Execute the chosen action (see action specs below).
4. Update `last_action`, `last_findings`, and append to `audit_log`.
5. Print a one-line progress marker so the user can watch convergence:
   - After audit: `Loop <N> audit: <P0>P0 / <P1>P1 / <P2>P2`
   - After fix: `Loop <N> fix: commit <sha7> (<files_changed> files, +<add>/-<del>)`
6. Loop.

### AUDIT action (clean-room teammate, fresh per loop)

Capture a fresh PR diff for this loop into the per-team scoped directory so concurrent `/bugteam` runs do not collide. Use the literal `<team_temp_dir>` resolved once in Step 2 — do NOT rewrite the path with shell expansion:

```
mkdir -p "<team_temp_dir>"
gh pr diff <number> -R <owner>/<repo> > "<team_temp_dir>/loop-<N>.patch"
```

`<team_temp_dir>` is the absolute path captured in Step 2 (already includes the sanitized team_name and timestamp suffix, and `team_name` itself is already prefixed with `bugteam-`). Claude resolves the portable temp root once via `Path(tempfile.gettempdir()) / team_name` (requires `import tempfile`) and passes the literal absolute path to every shell command. `tempfile.gettempdir()` honors `TMPDIR`, `TEMP`, and `TMP` in the platform-correct order and falls back to `C:\Users\<user>\AppData\Local\Temp` on Windows or `/tmp` on Unix, so this works identically on macOS, Linux, Windows cmd.exe, and PowerShell because the shell never has to interpret `${TMPDIR:-/tmp}` or `%TEMP%`.

Spawn a NEW `bugfind` teammate for this loop using the `code-quality-agent` subagent type. The teammate is fresh: no prior loop's findings, no chat history, no inherited audit context. Per the docs: *"The lead's conversation history does not carry over."* — and we further guarantee independence by spawning a new teammate per loop rather than reusing one.

The teammate's spawn prompt is the full XML below — copy it verbatim with the placeholders substituted. **Forbid all conversation references** in the spawn prompt. No "as we discussed," "the earlier issue," "fix from the prior loop," "you previously identified." Each loop's audit teammate has no idea other loops happened.

```xml
<context>
  <repo>owner/repo</repo>
  <branch>head ref</branch>
  <base_branch>base ref</base_branch>
  <pr_url>full URL</pr_url>
  <loop>N</loop>
</context>

<scope>
  <diff_path>Absolute path to the loop-N patch file under team_temp_dir from Step 2 (same path as gh pr diff redirect in AUDIT)</diff_path>
  <scope_rule>Audit only lines added or modified in the diff. Pre-existing code on untouched lines is out of scope.</scope_rule>
</scope>

<bug_categories>
  Investigate each category explicitly. For each, return either at least
  one finding OR a verified-clean entry with the evidence used to clear it:
  A. API contract verification (signatures, return types, async/await correctness)
  B. Selector / query / engine compatibility
  C. Resource cleanup and lifecycle (file handles, connections, processes, locks)
  D. Variable scoping, ordering, and unbound references
  E. Dead code and unused imports
  F. Silent failures (catch-all excepts, unconditional success returns, missing error propagation)
  G. Off-by-one, bounds, and integer overflow
  H. Security boundaries (injection, path traversal, auth bypass, secret leakage)
  I. Concurrency hazards (race conditions, missing awaits, shared mutable state)
  J. Magic values and configuration drift
</bug_categories>

<constraints>
  - Read-only on source code: the audit does not modify any source file.
  - Cite file:line for every finding.
  - When the diff alone does not provide enough context to confirm a bug,
    list it under "Open questions" rather than assert it.
</constraints>

<comment_posting>
  1. Post the loop comment for this loop FIRST, before auditing. Use
     the Step 2.5 loop-comment CLI shape with this body:

       ## /bugteam loop N: audit running

       Clean-room audit on PR diff. Finding comments will appear below
       this line.

  2. Audit the diff against the 10 categories above.
  3. For each finding, post a finding comment via the Step 2.5
     finding-comment CLI shape. Body:

       **[severity] one-line title**
       Category: <letter> (<category name>)
       <2-3 sentence description with concrete trace>

       _From /bugteam audit loop N._

     On POST failure (rate limit, line not in diff, malformed payload,
     network), fall back to a top-level issue comment per Step 2.5.
  4. Assign each finding a stable finding_id of exactly the form
     `loopN-K` where K is 1-based within this loop.
  5. Use --body-file (never --body) to avoid the gh-body-backtick-guard hook.
</comment_posting>

<output_format>
  Write the outcome XML below to .bugteam-loop-N.outcomes.xml in the
  working directory. Return only that path on stdout. The schema:
</output_format>
```

Outcome XML schema (bugfind writes this):

```xml
<bugteam_audit loop="<N>" loop_comment_url="<url>">
  <finding
    finding_id="loop<N>-<index>"
    severity="P0|P1|P2"
    category="<letter>"
    file="<path>"
    line="<int>"
    finding_comment_id="<gh comment id, or empty if fallback>"
    finding_comment_url="<url, inline OR fallback issue comment URL>"
    used_fallback="true|false"
  >
    <title>one-line title</title>
    <description>2-3 sentence description with concrete trace</description>
  </finding>
  <verified_clean>
    <category letter="<letter>" name="<name>" evidence="brief evidence + cleared conclusion"/>
  </verified_clean>
</bugteam_audit>
```

After the teammate writes the XML and returns, the lead reads `.bugteam-loop-<N>.outcomes.xml`, parses it, and populates `loop_comment_index` from `<finding>` elements. Then **shut down the bugfind teammate**: `Ask the bugfind teammate to shut down`. Per the docs: *"The lead sends a shutdown request. The teammate can approve, exiting gracefully, or reject with an explanation."* If the teammate rejects shutdown, force-shut by failing the team and starting Step 5 cleanup with exit reason = `error: bugfind teammate refused shutdown`.

`last_action = "audited"`. `last_findings = parsed`. Append `(loop=N, action="audit", counts={P0,P1,P2}, sha=current_HEAD, loop_comment_url=<url>, finding_count=<n>, fallback_count=<n>)` to `audit_log`.

### FIX action (fresh teammate, only sees latest audit)

Spawn a NEW `bugfix` teammate for this loop using the `clean-coder` teammate role, model sonnet. The teammate sees ONLY the most recent audit's findings — no prior-loop findings, no prior-loop fix history, no chat history.

The teammate receives the **finding comment URL and id for each finding** (from `loop_comment_index`) and **owns the reply posting**. After committing fixes, the teammate posts one reply per finding: `Fixed in <commit_sha>` for addressed findings, `Could not address this loop: <one-line reason>` for skipped or failed findings. Same one-identity model as bugfind: teammate posts, lead does not.

After all replies are posted, the teammate writes its own outcome XML (see schema below), returns, and the lead **shuts down the bugfix teammate** the same way as the bugfind shutdown.

Prompt skeleton:

```xml
<context>
  <repo>owner/repo</repo>
  <branch>head</branch>
  <base_branch>base</base_branch>
  <pr_url>url</pr_url>
  <loop>N</loop>
</context>

<bugs_to_fix>
  [for each P0/P1/P2 finding from last_findings:]
  <bug
    finding_id="loop<N>-<index>"
    severity="P0|P1|P2"
    file="<path>"
    line="<int>"
    category="<letter>"
    finding_comment_id="<id>"
    finding_comment_url="<url>"
  >
    <description>...</description>
  </bug>
</bugs_to_fix>

<execution>
  1. Read each referenced file before editing.
  2. Apply each fix you can address.
  3. Run `python -m py_compile` (or language-equivalent) on every modified file.
  4. git add by explicit path, then git commit with a message summarizing the bugs fixed.
     - If the commit fails because a git hook (pre-commit, commit-msg, etc.) blocked it,
       capture the hook's stderr, write status=hook_blocked for every finding in this loop
       (the commit was atomic; if it failed, no finding was applied), populate hook_output
       on each outcome, and return WITHOUT retrying. The lead will treat this loop as no-progress.
  5. git push (NEVER --force, NEVER --force-with-lease).
  6. For each bug, post a fix reply to its finding_comment_id via the
     Step 2.5 reply CLI shape:
     - "Fixed in <commit_sha>" if the bug was addressed by your commit
     - "Could not address this loop: <one-line reason>" if you skipped or failed it
     - "Hook blocked the fix commit: <one-line summary>" if the commit was hook-blocked
     Use --body-file (the existing gh-body-backtick-guard hook blocks --body).
  7. Write `.bugteam-loop-<N>.outcomes.xml` (schema below) and return its path.
</execution>

<outcome_xml_schema>
  <bugteam_fix loop="<N>" commit_sha="<sha or empty if no commit>">
    <outcome
      finding_id="loop<N>-<index>"
      status="fixed|could_not_address|hook_blocked"
      commit_sha="<sha if fixed, empty otherwise>"
      reply_comment_id="<id of the reply posted>"
      reply_comment_url="<url of the reply posted>"
    >
      <reason>only present when status=could_not_address; one-line reason text</reason>
      <hook_output>only present when status=hook_blocked; verbatim stderr from the blocked hook</hook_output>
    </outcome>
  </bugteam_fix>
</outcome_xml_schema>

<constraints>
  - Modify only files referenced in bugs_to_fix.
  - One commit on the existing branch, then push.
  - Do NOT rebase, amend, --force, --force-with-lease, or change the PR base.
  - Do NOT skip git hooks.
  - git add by explicit path; never `git add .` or `git add -A`.
  - Preserve existing comments on lines you do not modify.
  - Type hints on every signature you touch.
</constraints>
```

Verify the fix actually committed and pushed:

- `git rev-parse HEAD` after fix should differ from before
- The new HEAD should be present on `origin/<branch>` (`git fetch origin <branch> && git rev-parse origin/<branch>` matches HEAD)

If `git rev-parse HEAD` did not change, exit reason = `stuck — bugfix teammate could not address findings`. The fix teammate ran but produced no commit; further loops will not converge.

`last_action = "fixed"`. Append `(loop=N, action="fix", commit_sha=new_HEAD, files_changed, lines_added, lines_removed)` to `audit_log`.

### Step 4: Tear down the team and clean working tree

When the cycle exits (any reason):

1. **Clean up the team as the lead.** Per the docs: *"When you're done, ask the lead to clean up: 'Clean up the team'. This removes the shared team resources. When the lead runs cleanup, it checks for active teammates and fails if any are still running, so shut them down first."* The lead is THIS session — call cleanup directly. If any teammate is still alive (e.g., from an aborted shutdown), shut it down first.
2. Delete the per-team scoped temp directory using Python: `shutil.rmtree(team_temp_dir, ignore_errors=True)` (requires `import shutil`). This works on every platform without OS-detection branching. Pass the literal absolute path Claude resolved at Step 2 — do NOT defer to the shell, and never use shell `${TMPDIR:-/tmp}` or `%TEMP%` expansion at this step either.

### Step 4.5: Finalize the PR description (mandatory)

After teardown and before permission revoke, the lead rewrites the PR body to reflect the PR's **final cumulative state** — the change the PR delivers, not the bugteam process. This is the **only** PR-write the lead performs (audit and fix comments belong to the teammates).

The lead delegates the body authoring to the `pr-description-writer` agent so the global mandatory-pr-description-writer hook accepts the subsequent `gh pr edit`. The lead does NOT compose the body inline.

`pr-description-writer` is provided by the global git-workflow rule in `claude-code-config` (as the `pr-description-writer` agent type). If that agent is not available in the current environment, fall back to spawning a `general-purpose` agent with the same brief — the global hook treats agent-authored bodies the same regardless of the specific agent type. If neither agent is available, log a warning in the final report and skip Step 4.5; the original PR body remains.

Steps:

1. Capture the cumulative diff: `gh pr diff <number> -R <owner>/<repo> > .bugteam-final.diff`.
2. Capture the original body: `gh pr view <number> -R <owner>/<repo> --json body --jq .body > .bugteam-original-body.md`.
3. Invoke the `pr-description-writer` agent (or `general-purpose` fallback) with this brief:
   - **Inputs:** the diff path, the original body path, the head branch name, the base branch name.
   - **Constraint:** describe what the PR delivers based on the cumulative diff. Do NOT mention `/bugteam`, audit loops, fix commits, finding counts, or any process metadata. Those belong in the finding comments, not the description. The description is for the merge audience.
   - **Preservation rule:** if the original body contains sections that look manually curated (linked issues, screenshots, a populated test plan, "Risk Assessment" sections), preserve those verbatim and only rewrite the prose narrative around them.
   - **Output:** the new body markdown.
4. Write the agent's returned body to `.bugteam-final-body.md`.
5. Apply: `gh pr edit <number> -R <owner>/<repo> --body-file .bugteam-final-body.md`.
6. Delete `.bugteam-final.diff`, `.bugteam-original-body.md`, and `.bugteam-final-body.md`.

If Step 4.5 fails for any reason (agent error, hook block, network), surface the failure in the final report and continue to Step 5. The original PR body remains; the rest of the cycle's work (commits, comments, replies) is unaffected.

### Step 5: Revoke project permissions (mandatory, runs always)

After team cleanup completes — including on error, cap-reached, or stuck exits — run:

```bash
python "${CLAUDE_SKILL_DIR}/revoke_project_claude_permissions.py"
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
- **Cleanup the per-team scoped temp directory on exit.** The resolved `<team_temp_dir>` (absolute literal captured in Step 2) is deleted entirely so no loop patches leak between runs.
- **Cleanup all `.bugteam-*` files on exit.** `.bugteam-loop-*.patch`, `.bugteam-loop-*.outcomes.xml`, `.bugteam-final.diff`, `.bugteam-original-body.md`, `.bugteam-final-body.md`. Working directory ends clean.
- **Teammates own audit/fix comment posting.** Bugfind posts the loop comment and finding comments (with issue-comment fallback). Bugfix posts the fix replies after committing. The lead never calls `gh pr comment` or `gh api repos/.../comments` for these.
- **Lead owns the final PR description rewrite only** (Step 4.5), and only via the `pr-description-writer` agent. The lead does not compose the description inline.
- **Loop comment per loop, fresh finding comments per loop.** No cross-loop comment threading, no comment editing in place, no thread resolution in this version. Each loop's section on the PR is self-contained.
- **PR description rewrite on every exit.** Step 4.5 runs on `converged`, `cap reached`, and `stuck`. On `error`, the rewrite is best-effort; if it fails, surface the error in the final report and continue to revoke.
- **Outcome XML, not JSON.** Both teammates write structured outcome data (findings or fix outcomes) to `.bugteam-loop-<N>.outcomes.xml`. The lead reads these files between actions. XML chosen for parser robustness against multi-line, special-character, and quoted reason fields.

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
User: `/bugteam` (mixed-outcome path: some findings fixed, others skipped)
Claude: [resolves PR #99, runs loop with partial-fix outcomes]

`Loop 1 audit: 1P0 / 3P1 / 0P2`
`Loop 1 fix: commit a1b2c3d (2 files, +8/-3) — 2 fixed, 2 could_not_address`
`Loop 2 audit: 0P0 / 2P1 / 0P2`
`Loop 2 fix: 0 fixed, 2 could_not_address (no commit)`

`/bugteam exit: stuck`
`Loops: 2`
`Unresolved findings (2): src/auth.py:45 (P1: file is generated, cannot edit); src/legacy.py:200 (P1: rewrite scope exceeds the bug)`

The bugfix teammate writes one outcome per finding to `.bugteam-loop-2.outcomes.xml`. Findings with `status=could_not_address` carry their `<reason>` text, and the teammate posts a matching reply to each finding comment so the reviewer sees why each bug stayed open.
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
