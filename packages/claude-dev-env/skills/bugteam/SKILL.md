---
name: bugteam
description: >-
  Runs an autonomous audit-and-fix loop on the current branch's PR using a
  Claude Code agent team — bugfind teammate (code-quality-agent, clean-room
  audit) and bugfix teammate (clean-coder, sonnet fix) — until the audit
  returns zero bugs or a 10-loop safety cap is reached. One up-front
  confirmation authorizes the entire cycle. Each audit teammate is spawned
  fresh per loop to prevent anchoring bias. Wraps the cycle with project
  permission grant/revoke. Requires CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1.
  Triggers: '/bugteam', 'run the bug team',
  'auto-fix the PR until clean', 'loop audit and fix'.
---

# Bugteam

**Core principle:** A Claude Code **agent team** runs the audit-and-fix loop until convergence. The bugfind teammate audits clean-room (own context window, no chat history); the bugfix teammate addresses each audit's findings; both spawn fresh per loop. A 10-loop hard cap prevents runaway cost. Project permissions are granted at session start and revoked at session end.

> **Source:** [Anthropic — Orchestrate teams of Claude Code sessions](https://code.claude.com/docs/en/agent-teams). Direct quote: *"Each teammate has its own context window. When spawned, a teammate loads the same project context as a regular session: CLAUDE.md, MCP servers, and skills. It also receives the spawn prompt from the lead. The lead's conversation history does not carry over."* That isolation is the design's whole point — independent context per teammate enforces the clean-room property automatically.

> **Why agent teams, not parallel subagents:** Subagents return their results into the lead's context, which accumulates across loops. Agent team teammates are independent sessions with their own context windows and do not pollute the lead. The lead can shut down + respawn each loop, guaranteeing every audit starts fresh. Per the docs: *"Use subagents when you need quick, focused workers that report back. Use agent teams when teammates need to share findings, challenge each other, and coordinate on their own."* For this skill, the independent-context property is what we need; parallel subagents fail the clean-room requirement.

## Contents

This file is 400+ lines. The list below is for the LLM reading this skill — partial reads (e.g., `head -100`) miss what comes later, so this section ensures the full scope is visible from the top. (Per Anthropic's [Skill authoring best practices — Structure longer reference files with table of contents](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#structure-longer-reference-files-with-table-of-contents).)

- When this skill applies — refusal cases (4) and trigger conditions
- Utility scripts — pre-flight checks (`scripts/`, executed not loaded as context)
- Pre-audit code rules gate — `validate_content` / hook parity before each AUDIT
- The Process — Progress checklist + Steps 0–6
  - Step 0 — Grant project permissions
  - Step 1 — Resolve PR scope
  - Step 2 — Create the agent team
  - Step 2.5 — PR comment lifecycle (per-loop review with child finding comments, fix replies)
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
- **Missing PR or upstream diff.** Respond exactly: `No PR or upstream diff. /bugteam needs a target.` and stop.
- **Working tree dirty with uncommitted changes the user did not stage.** Respond: `Uncommitted changes detected. Stash, commit, or revert before /bugteam.` and stop. Reason: the fix teammate will commit the working tree, mixing user-uncommitted work into automated fixes.
- **Required subagents not installed.** Before Step 0, verify `code-quality-agent` and `clean-coder` subagent types exist in the available agents list. If either is missing, respond: `Required subagent type <name> not installed. /bugteam needs both code-quality-agent and clean-coder available.` and stop.

## Utility scripts

Fragile or repeatable shell sequences belong in `scripts/` (see Anthropic [Skill authoring best practices — Progressive disclosure](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#progressive-disclosure-patterns): utility scripts are **executed**, not loaded into context). Details: [`scripts/README.md`](scripts/README.md).

### Pre-flight (recommended before Step 0)

From the repository root, run:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/bugteam_preflight.py"
```

If the exit code is non-zero, stop and fix failing checks before granting permissions. Optional: `BUGTEAM_PREFLIGHT_SKIP=1` skips pre-flight (emergency only). Optional: `--pre-commit` when `.pre-commit-config.yaml` exists.

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

Capture: `<owner>/<repo>`, head branch, base branch, PR number, PR URL. This scope persists across every loop — `/bugteam` runs to completion from the single up-front confirmation.

### Step 2: Create the agent team

This session is the **team lead**. Create the team by calling the `TeamCreate` tool with these exact arguments:

```
TeamCreate(
  team_name="<team_name>",
  description="Bugteam audit/fix loop for PR <number> (<owner>/<repo>)",
  agent_type="team-lead"
)
```

`<team_name>` is the value built below under **Team name** (sanitization + timestamp already applied). `TeamCreate` is the tool that resolves the docs' phrasing: *"tell Claude to create an agent team and describe the task and the team structure you want in natural language. Claude creates the team, spawns teammates, and coordinates work based on your prompt."*

Team specification:

- **Team name:** `bugteam-pr-<number>-<YYYYMMDDHHMMSS>` (or `bugteam-<sanitized-head-branch>-<YYYYMMDDHHMMSS>` if no PR). The timestamp is captured at team-creation time from the lead session and prevents two concurrent invocations on the same PR from colliding.
- **Branch-name sanitization (no-PR fallback only):** Before substituting `<head-branch>` into the team_name template, replace every character outside `[A-Za-z0-9._-]` with `-`. The whitelist keeps safe portable filename characters only; OS-reserved and shell-special characters (`/ \ : * ? < > | "` plus ASCII control chars 0x00–0x1F) fall outside the whitelist and become `-`. Example: `feat/foo*bar` → `feat-foo-bar`; team_name becomes `bugteam-feat-foo-bar-<YYYYMMDDHHMMSS>`. Apply the sanitization when team_name is first assembled so every downstream use (team creation, scoped temp dir, cleanup) sees the safe form.
- **Per-team temp directory (resolved once, reused everywhere):** After team_name is captured, resolve a portable absolute path with a Claude-side lookup using Python's `tempfile.gettempdir()`, which honors `TMPDIR`, `TEMP`, and `TMP` in the platform-correct order and falls back to `C:\Users\<user>\AppData\Local\Temp` on Windows or `/tmp` on Unix: `Path(tempfile.gettempdir()) / team_name` (requires `import tempfile`). The `team_name` value already carries the `bugteam-` prefix, so keep it as-is here. Let `tempfile.gettempdir()` do the lookup; use its result directly. Capture the resolved absolute path as `<team_temp_dir>` and pass that literal path to every shell command that follows. Claude performs all temp-root resolution, so every shell (bash, cmd.exe, PowerShell) receives the same literal absolute value.
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

### Step 2.5: PR comment lifecycle (one review per loop)

The team narrates its work to the PR via a **GitHub pull-request review** per loop so findings render as a tree under a single parent review (like Cursor Bugbot). **Teammates own all PR comment posting** — bugfind posts the review (parent body + child finding comments in one batched POST), bugfix posts fix replies. All comment, review, and reply POSTs belong to the teammates. The lead's single PR-write action is the final description rewrite at Step 4.5 (via `pr-description-writer` agent).

- **Per-loop review** — one `POST /pulls/<number>/reviews` per loop, posted by the bugfind teammate AFTER auditing. The review body is the loop header (with audit counts); the review's `comments[]` array holds one anchored finding per P0/P1/P2 finding. GitHub renders this as a single collapsible thread with each finding as a child comment — the tree shape Cursor Bugbot produces.

- **Fix replies** — replies to each child finding comment. Posted by the bugfix teammate after the commit lands. Body: `Fixed in <commit_sha>` if addressed, or `Could not address this loop: <one-line reason>` if not. The `/pulls/<number>/comments/<id>/replies` endpoint works on any review comment, including those created as part of a review, so this shape is unchanged.

**Ordering:** bugfind audits FIRST, buffers the findings, validates anchors against the captured diff, then posts the review ONCE at the end. The review body names the finding count authoritatively. Keep all posting bunched into that single end-of-loop review POST.

CLI shapes (teammate runs these). All three POSTs use the same robust pattern: build the JSON payload with `jq` (pulling file contents in with `--rawfile` or `-Rs` so markdown with backticks, newlines, and quotes survives intact), then pipe the JSON to `gh api ... --input -` on stdin. This avoids every shell-quoting edge case.

- **Per-loop review (one POST creates the parent review AND all child finding comments).** Build the `comments[]` array programmatically from the buffered, diff-anchored findings. The shape per finding is `{path, line, side: "RIGHT", body: <finding markdown>}` for single-line anchors; use `{path, start_line, start_side: "RIGHT", line, side: "RIGHT", body: ...}` for multi-line ranges (all four fields required).

  ```
  jq -n \
    --rawfile review_body <tmp_review_body.md> \
    --arg commit_id "$(git rev-parse HEAD)" \
    --rawfile finding_body_1 <tmp_finding_1.md> \
    --arg path_1 "<file_1>" \
    --argjson line_1 <line_1> \
    [... one finding_body_K / path_K / line_K triple per anchored finding ...] \
    '{
       commit_id: $commit_id,
       event: "COMMENT",
       body: $review_body,
       comments: [
         {path: $path_1, line: $line_1, side: "RIGHT", body: $finding_body_1}
         [, ... one object per anchored finding ...]
       ]
     }' \
  | gh api repos/<owner>/<repo>/pulls/<number>/reviews -X POST --input -
  ```

  Response JSON carries the parent review `id` / `html_url` plus a `comments` array of child comments, each with its own `id` and `html_url`. Harvest the child entries in index order and match them to the finding list the teammate posted.

- **Fix reply** — replying to a child finding comment only needs `body`:

  ```
  jq -Rs '{body: .}' < <tmp_reply.md> \
  | gh api repos/<owner>/<repo>/pulls/<number>/comments/<finding_comment_id>/replies -X POST --input -
  ```

- **Review-POST failure fallback** — top-level PR comment via the issue-comments endpoint (`{issue_number}` is the PR number):

  ```
  jq -Rs '{body: .}' < <tmp_fallback.md> \
  | gh api repos/<owner>/<repo>/issues/<number>/comments -X POST --input -
  ```

`<head_sha_at_post_time>` = the SHA at the moment the review is posted (run `git rev-parse HEAD` in the teammate's working dir immediately before the POST). The review anchors its finding comments to the head SHA at audit time, which is the SHA before this loop's fix lands.

Write each body (review body and every per-finding body) to its own temp file before running the jq pipeline. The `jq --rawfile` / `jq -Rs` pattern loads file contents as a single string into the JSON payload, which preserves backticks, newlines, and quotes intact. The body stays inside the file the jq pipeline reads — it reaches GitHub as part of the JSON payload — which keeps it compatible with the `gh-body-backtick-guard` hook that scans command-line `--body` arguments.

**Review body shape** (content of `<tmp_review_body.md>`):

```
## /bugteam loop <N> audit: <P0>P0 / <P1>P1 / <P2>P2

<if any findings could not be anchored to a diff line, include this section:>
### Findings without a diff anchor

- **[severity] title** — <file>:<line> — <one-line description>
```

If the audit returns zero findings, the teammate still posts ONE review with `event=COMMENT`, an empty `comments[]`, and body `## /bugteam loop <N> audit: 0P0 / 0P1 / 0P2 → clean`. This keeps every loop's section self-contained on the PR.

**Anchor-validation fallback (teammate handles).** GitHub rejects the entire review POST if any `comments[]` entry targets a line not in the diff. Before posting, the bugfind teammate validates every finding's `(file, line)` against the captured diff. Findings whose anchor is not in the diff are NOT added to `comments[]`; they are listed in the review body under `### Findings without a diff anchor`. The outcome XML records `used_fallback="true"` for each such finding, with `finding_comment_id=""` and `finding_comment_url=<review_url>` (the parent review URL, since no child comment exists for it). The teammate logs the fallback count in its outcome XML so the lead's final report can count fallbacks. Cycle continues; no anchor failure aborts the loop.

**Review POST failure fallback.** If the review POST itself fails (rate limit, network, malformed payload), the teammate falls back to a single top-level issue comment containing the review body plus every finding inline (severity, file:line, description). Every finding in that run carries `used_fallback="true"` and the issue-comment URL as `finding_comment_url`. Use the Review-POST failure fallback CLI shape above (`jq -Rs | gh api .../issues/<number>/comments --input -`).

**GitHub REST endpoints the teammate POSTs to:**

- Per-loop batched review: `POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews` (required: `body`, `event=COMMENT`, `commit_id`; optional `comments[]` — each entry needs `path`, `body`, `line`, `side`)
- Fix reply: `POST /repos/{owner}/{repo}/pulls/{pull_number}/comments/{comment_id}/replies` (required: `body`)
- Review-POST failure fallback: `POST /repos/{owner}/{repo}/issues/{issue_number}/comments` (required: `body`; `{issue_number}` is the PR number)

### Step 3: The cycle

Repeat until an exit condition fires.

**Ordering principle:** Mandatory **CODE_RULES** checks (`validate_content` from `hooks/blocking/code_rules_enforcer.py`) must pass on the PR-scoped file set **before** any **AUDIT** (bugfind) teammate runs. The **clean-coder** teammate clears gate failures; then the **code-quality-agent** teammate audits. This mirrors “CI green, then review,” without relying on GitHub Actions — the script is the gate.

1. Decide the next action from `last_action` and `last_findings`:
   - `last_action == "audited"` and `last_findings.total == 0` → exit reason = `converged`
   - `last_action == "fixed"` and `git rev-parse HEAD` did not change since pre-FIX → exit reason = `stuck` (see FIX action)
   - `last_action in {"fresh", "fixed"}` → go to **pre-audit path** (below), then **AUDIT**
   - `last_action == "audited"` and `last_findings.total > 0` → go to **FIX** (below)

2. **Pre-audit path** (only when the next step is **AUDIT**):
   1. From the repository root, run the gate script (align `--base` with the PR base branch from Step 1, e.g. `origin/main` or `origin/develop`):

      ```bash
      python "${CLAUDE_SKILL_DIR}/scripts/bugteam_code_rules_gate.py" --base origin/<baseRefName>
      ```

      Use `git merge-base` + `git diff --name-only` inside the script; see [`scripts/README.md`](scripts/README.md). The lead runs this (not a teammate).
   2. If exit code **0** → continue to step 3 (AUDIT spawn) below.
   3. If exit code **non-zero** → spawn a NEW **clean-coder** teammate — **standards-fix pass** — with instructions: read the script’s stderr, edit the repo until a **re-run** of the **same** gate command exits **0**, then one commit, `git push`, shutdown. Repeat standards-fix spawns until the gate exits **0** or **5** failed gate rounds (each round = one teammate session after a non-zero gate). If still non-zero after 5 rounds → exit reason = `error: code rules gate failed pre-audit`.
   4. After gate exit **0**, increment `loop_count`. If `loop_count > 10`, exit reason = `cap reached` (counts **audits**, not standards-only rounds).
   5. Execute **AUDIT action** (spawn bugfind). Print progress: `Loop <N> audit: ...`

3. **FIX path** (when `last_action == "audited"` and `last_findings.total > 0`):
   1. Increment `loop_count`. If `loop_count > 10`, exit reason = `cap reached`.
   2. Execute **FIX action** (spawn bugfix clean-coder for audit findings). Print: `Loop <N> fix: commit ...`
   3. Set `last_action = "fixed"`, update `audit_log`, loop to step 1 (next iteration will hit **pre-audit path** before the next AUDIT).

4. After **AUDIT**, update `last_action`, `last_findings`, `audit_log`; print the audit progress line if not already printed.

5. Loop.

**Note:** The first iteration uses **pre-audit path** then **AUDIT**. After a **FIX** for audit findings, the next iteration runs **pre-audit path** again (gate → then AUDIT), so `validate_content` stays green before semantic audit.

### AUDIT action (clean-room teammate, fresh per loop)

Capture a fresh PR diff for this loop into the per-team scoped directory so each concurrent `/bugteam` run keeps its patches isolated. Use the literal `<team_temp_dir>` resolved once in Step 2 — Claude resolves the absolute path, and every shell receives the same literal value:

```
mkdir -p "<team_temp_dir>"
gh pr diff <number> -R <owner>/<repo> > "<team_temp_dir>/loop-<N>.patch"
```

`<team_temp_dir>` is the absolute path captured in Step 2 (already includes the sanitized team_name and timestamp suffix, and `team_name` itself is already prefixed with `bugteam-`). Claude resolves the portable temp root once via `Path(tempfile.gettempdir()) / team_name` (requires `import tempfile`) and passes the literal absolute path to every shell command. `tempfile.gettempdir()` honors `TMPDIR`, `TEMP`, and `TMP` in the platform-correct order and falls back to `C:\Users\<user>\AppData\Local\Temp` on Windows or `/tmp` on Unix, so this works identically on macOS, Linux, Windows cmd.exe, and PowerShell: Claude resolves the literal path once and every shell receives the same absolute value.

Spawn a fresh `bugfind` teammate for this loop by calling the `Agent` tool with these exact arguments:

```
Agent(
  subagent_type="code-quality-agent",
  name="bugfind",
  team_name="<team_name>",
  model="sonnet",
  description="Bugfind audit loop <N>",
  prompt="<audit XML from the block below, with placeholders substituted>"
)
```

Each loop calls `Agent` again with a fresh `Agent` invocation so the teammate starts with its own context window. The docs guarantee this: *"The lead's conversation history does not carry over."* Spawning per loop keeps every audit independent.

Keep the spawn prompt self-contained: reference only the PR scope, audit rubric, and this loop number. Write each instruction as a standalone statement so the teammate reads the prompt as a fresh brief and every audit starts from first principles.

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
  1. Audit the diff against the 10 categories above. Buffer the findings
     in memory; all posting happens at step 6 once anchors are validated.
  2. Assign each finding a stable finding_id of exactly the form `loopN-K`
     where K is 1-based within this loop.
  3. Validate every finding's (file, line) against the captured diff. Split
     findings into two buckets: anchored (line is in the diff) and
     unanchored (line is not in the diff — goes into the review body's
     "Findings without a diff anchor" section per Step 2.5).
  4. Build the review body per Step 2.5's review-body shape, filling in the
     P0/P1/P2 counts and the unanchored-findings list (if any).
  5. For each anchored finding, write its body to its own temp file:

       **[severity] one-line title**
       Category: <letter> (<category name>)
       <2-3 sentence description with concrete trace>

       _From /bugteam audit loop N._

  6. Post ONE review via Step 2.5's per-loop review CLI shape. Harvest the
     parent review `html_url` from the response JSON and the `comments[]`
     child entries (each with its own `id` and `html_url`). Match child
     entries to anchored findings in index order.
  7. If the review POST itself fails, use Step 2.5's Review POST failure
     fallback (single issue comment with full body and all findings inline).
  8. Write every body (review body, each finding body, any fallback body)
     to its own temp file. Load each file into the JSON payload via jq's
     `--rawfile` or `-Rs`, then pipe the jq output to `gh api ... --input -`
     so every body reaches GitHub as file contents inside the JSON payload.
</comment_posting>

<output_format>
  Write the outcome XML below to .bugteam-loop-N.outcomes.xml in the
  working directory. Return only that path on stdout. The schema:
</output_format>
```

Outcome XML schema (bugfind writes this):

```xml
<bugteam_audit loop="<N>" review_url="<url>">
  <finding
    finding_id="loop<N>-<index>"
    severity="P0|P1|P2"
    category="<letter>"
    file="<path>"
    line="<int>"
    finding_comment_id="<gh child comment id, or empty if unanchored/review-fallback>"
    finding_comment_url="<url of child comment, OR review_url if unanchored, OR fallback issue comment URL>"
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

After the teammate writes the XML and returns, the lead reads `.bugteam-loop-<N>.outcomes.xml` with the `Read` tool, parses it, and populates `loop_comment_index` from `<finding>` elements.

**Expected path: self-termination.** In practice, teammates self-terminate when their task is complete — the `Agent` call returns and the teammate's session ends automatically. When that happens, no `SendMessage` shutdown is needed and the cycle proceeds directly to the next action.

**Fallback path: lead-initiated shutdown.** If the teammate has not self-terminated after the `Agent` call returns (observable as the teammate still appearing in the active-teammates list), send a shutdown message:

```
SendMessage(
  to="bugfind",
  message={
    "type": "shutdown_request",
    "reason": "audit loop <N> complete; outcome XML captured"
  }
)
```

The teammate replies with `{type: "shutdown_response", approve: true}` and exits. If `approve` comes back `false`, treat this as a fatal error: set exit reason = `error: bugfind teammate refused shutdown` and jump to Step 4 teardown followed by Step 5 revoke.

`last_action = "audited"`. `last_findings = parsed`. Append `(loop=N, action="audit", counts={P0,P1,P2}, sha=current_HEAD, review_url=<url>, finding_count=<n>, fallback_count=<n>)` to `audit_log`.

**Parallel auditors from loop 4 onward (`loop_count >= 4`).** The pre-audit code rules gate must still pass immediately before this step (Step 3). After three full audit/fix rounds without convergence, spawn three bugfind teammates concurrently by issuing three `Agent` calls in a single assistant message so they run in parallel:

```
Agent(subagent_type="code-quality-agent", name="bugfind-loop-<N>-a", team_name="<team_name>", model="sonnet", description="Bugfind audit loop <N> variant a", prompt="<audit XML; write outcome to .bugteam-loop-<N>.outcomes.xml; post the per-loop review; read and merge b/c outcomes from <team_temp_dir>/loop-<N>-b.outcomes.xml and <team_temp_dir>/loop-<N>-c.outcomes.xml>")
Agent(subagent_type="code-quality-agent", name="bugfind-loop-<N>-b", team_name="<team_name>", model="sonnet", description="Bugfind audit loop <N> variant b", prompt="<audit XML; write outcome to <team_temp_dir>/loop-<N>-b.outcomes.xml; skip PR posting>")
Agent(subagent_type="code-quality-agent", name="bugfind-loop-<N>-c", team_name="<team_name>", model="sonnet", description="Bugfind audit loop <N> variant c", prompt="<audit XML; write outcome to <team_temp_dir>/loop-<N>-c.outcomes.xml; skip PR posting>")
```

Teammate `-a` is the post-owner: it reads all three outcome XML files using their explicit absolute paths — its own outcome at `.bugteam-loop-<N>.outcomes.xml` (working directory), and the sibling outcomes at `<team_temp_dir>/loop-<N>-b.outcomes.xml` and `<team_temp_dir>/loop-<N>-c.outcomes.xml` — then merges findings by `(file, line, category_letter)` (same tuple collapses to one finding, keeping the longest description and the highest severity of the group), re-assigns merged-finding IDs as `loopN-K`, and posts the single per-loop review per the standard posting protocol above. The `-a` spawn prompt must include both sibling paths as literal absolute values so `-a` can read them with the `Read` tool by path without any discovery step.

Shut down `-b` and `-c` first with two parallel `SendMessage` calls, then shut down `-a` after its post completes:

```
SendMessage(to="bugfind-loop-<N>-b", message={"type": "shutdown_request", "reason": "variant XML captured"})
SendMessage(to="bugfind-loop-<N>-c", message={"type": "shutdown_request", "reason": "variant XML captured"})
```

then

```
SendMessage(to="bugfind-loop-<N>-a", message={"type": "shutdown_request", "reason": "merged review posted"})
```

### FIX action (fresh teammate, only sees latest audit)

Spawn a fresh `bugfix` teammate for this loop by calling the `Agent` tool with these exact arguments:

```
Agent(
  subagent_type="clean-coder",
  name="bugfix",
  team_name="<team_name>",
  model="sonnet",
  description="Bugfix loop <N>",
  prompt="<fix XML from the block below, with placeholders substituted>"
)
```

The teammate sees only the most recent audit's findings — each `Agent` call starts with a fresh context window, so prior-loop findings, prior-loop fix history, and prior chat history stay inside the lead.

Pass the **finding comment URL and id for each finding** (from `loop_comment_index`) inside the XML prompt so the teammate owns reply posting. After committing fixes, the teammate posts one reply per finding: `Fixed in <commit_sha>` for addressed findings, `Could not address this loop: <one-line reason>` for skipped or failed findings. Same one-identity model as bugfind: teammate posts, lead waits.

After all replies are posted, the teammate writes its own outcome XML (see schema below) and returns.

**Expected path: self-termination.** In practice, teammates self-terminate when their task is complete — the `Agent` call returns and the teammate's session ends automatically. When that happens, no `SendMessage` shutdown is needed and the cycle proceeds directly to the next action.

**Fallback path: lead-initiated shutdown.** If the teammate has not self-terminated after the `Agent` call returns, send a shutdown message:

```
SendMessage(
  to="bugfix",
  message={
    "type": "shutdown_request",
    "reason": "fix loop <N> complete; commit <sha7> pushed"
  }
)
```

If the shutdown response returns `approve: false`, treat it the same as the bugfind refusal case above: exit reason = `error: bugfix teammate refused shutdown`, jump to Step 4 teardown then Step 5 revoke.

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
  5. git push with a plain fast-forward push (the default, no flag overrides).
  6. For each bug, post a fix reply to its finding_comment_id via the
     Step 2.5 reply CLI shape:
     - "Fixed in <commit_sha>" if the bug was addressed by your commit
     - "Could not address this loop: <one-line reason>" if you skipped or failed it
     - "Hook blocked the fix commit: <one-line summary>" if the commit was hook-blocked
     Use the Fix reply CLI shape from Step 2.5 (`jq -Rs | gh api .../comments/<id>/replies --input -`). Write every reply body to a temp file first.
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
  - Keep the branch linear and the PR base fixed; append one new commit per
    loop and fast-forward push only.
  - Let every git hook run on every commit.
  - git add by explicit path — name each file being staged.
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

When the cycle exits (any reason), run these steps in order from THIS session (the lead):

1. **Confirm every teammate has shut down.** Any teammate still alive (for example, from an aborted shutdown mid-loop) must receive a shutdown message first. For each remaining teammate name:

   ```
   SendMessage(to="<teammate_name>", message={"type": "shutdown_request", "reason": "bugteam cycle ending"})
   ```

   The docs state: *"When the lead runs cleanup, it checks for active teammates and fails if any are still running, so shut them down first."*

   If any teammate returns `approve: false` during this cleanup shutdown, log the refusing teammate name (e.g., `cleanup warning: <teammate_name> refused shutdown_request`) and force-proceed to step 2 (`TeamDelete`) anyway. `TeamDelete` may fail if active teammates remain; if it does, surface the error in the final report with the refusing teammate name so the user can manually clean up. Do not abort the cleanup sequence — continue through temp-dir deletion, Step 4.5, and Step 5 regardless.

2. **Clean up the team** by calling `TeamDelete` with no arguments — it reads `<team_name>` from the current session's team context:

   ```
   TeamDelete()
   ```

   The docs state: *"When you're done, ask the lead to clean up: 'Clean up the team'."* `TeamDelete` is the tool that resolves that sentence.

3. **Delete the per-team scoped temp directory** by running this Python one-liner through the `Bash` tool (same literal `<team_temp_dir>` path resolved at Step 2):

   ```
   python -c "import shutil; shutil.rmtree(r'<team_temp_dir>', ignore_errors=True)"
   ```

   `shutil.rmtree(..., ignore_errors=True)` works identically on Windows and Unix, so the lead uses one command regardless of platform.

### Step 4.5: Finalize the PR description (mandatory)

After teardown and before permission revoke, the lead rewrites the PR body to reflect the PR's **final cumulative state** — the change the PR delivers, not the bugteam process. This is the **only** PR-write the lead performs (audit and fix comments belong to the teammates).

The lead delegates the body authoring to the `pr-description-writer` agent so the global mandatory-pr-description-writer hook accepts the subsequent `gh pr edit`. The lead does NOT compose the body inline.

`pr-description-writer` is provided by the global git-workflow rule in `claude-code-config`. Invoke it with the `Agent` tool:

```
Agent(
  subagent_type="pr-description-writer",
  description="Rewrite PR <number> body from cumulative diff",
  prompt="<brief from step 3 below>"
)
```

If `pr-description-writer` is not in the available agents list for the current environment, fall back to `general-purpose` with the same brief — the global hook treats agent-authored bodies the same regardless of the specific agent type:

```
Agent(
  subagent_type="general-purpose",
  description="Rewrite PR <number> body from cumulative diff",
  prompt="<brief from step 3 below>"
)
```

When neither agent is available, log a warning in the final report and skip Step 4.5 so the original PR body stays in place.

Steps:

1. Capture the cumulative diff: `gh pr diff <number> -R <owner>/<repo> > .bugteam-final.diff`.
2. Capture the original body: `gh pr view <number> -R <owner>/<repo> --json body --jq .body > .bugteam-original-body.md`.
3. Invoke the `pr-description-writer` agent (or `general-purpose` fallback) with this brief:
   - **Inputs:** the diff path, the original body path, the head branch name, the base branch name.
   - **Constraint:** describe what the PR delivers based on the cumulative diff — code behavior, user-facing effect, and merge rationale. Process metadata (audit loops, fix commit counts, finding counts) lives in the finding comments. The description speaks to the merge audience.
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
- **Orchestrator-only `TeamCreate`.** Only the lead session (this session, when `/bugteam` is invoked) calls `TeamCreate`. Teammates never call `TeamCreate` — if a teammate's spawn prompt instructs it to, that is a skill defect. When additional parallel work is needed (e.g., parallel auditors from loop 4 onward, supplementary audit of adjacent files), the lead spawns additional teammates into the EXISTING team by passing the current `team_name` to every `Agent(...)` call. Multiple teammate "sets" live inside one team under one orchestrator. The runtime enforces this: `TeamCreate` called while the session already leads a team returns the error `Already leading team "<name>". A leader can only manage one team at a time. Use TeamDelete to end the current team before creating a new one.` — direct quote from the runtime's response when this invariant is violated.
- **Grant before any spawn, revoke before any return.** Step 0 grants project `.claude/**` permissions; Step 5 revokes. Both are mandatory. Revoke runs on every exit path including error, cap-reached, and stuck.
- **Fresh teammate per loop.** Both bugfind and bugfix are spawned new each loop and shut down after their action. Reusing a teammate across loops accumulates context inside that teammate's window — defeats clean-room.
- **One up-front confirmation = whole cycle.** The `/bugteam` invocation authorizes the entire cycle; every subsequent decision runs on that single authorization.
- **10-loop hard cap.** Counted as **AUDIT** completions (increment in Step 3). Standards-fix passes before an audit do not advance `loop_count`. Worst case includes extra clean-coder spawns for the code-rules gate.
- **Code rules gate before every AUDIT.** Run `scripts/bugteam_code_rules_gate.py` until exit **0** before spawning **bugfind**. Same `validate_content` logic as `hooks/blocking/code_rules_enforcer.py`.
- **Clean-room audits, every loop.** Each bugfind teammate's spawn prompt contains only the PR scope, audit rubric, and the current loop number. Prior loop history stays in the lead.
- **Targeted fixes.** Each fix teammate sees ONLY the most recent audit's findings. Prior loops are invisible to the fix teammate.
- **Sonnet for both teammates.** Predictable cost, fits-purpose for code work.
- **Fix teammate receives the latest audit as its input contract.** Passing the audit's findings to the fix teammate is the input contract — each loop's fix run operates on the current audit's output and only that.
- **One commit per fix action.** Loops produce one commit per loop, not one per bug.
- **Linear branch, fixed PR base.** Every loop appends one forward-only commit; existing commits and the PR base stay intact throughout the cycle.
- **Lead-only cleanup.** Per the docs: *"Always use the lead to clean up. Teammates should not run cleanup because their team context may not resolve correctly, potentially leaving resources in an inconsistent state."* This session is the lead, and cleanup runs here only.
- **Cleanup the per-team scoped temp directory on exit.** The resolved `<team_temp_dir>` (absolute literal captured in Step 2) is deleted entirely so no loop patches leak between runs.
- **Cleanup all `.bugteam-*` files on exit.** `.bugteam-loop-*.patch`, `.bugteam-loop-*.outcomes.xml`, `.bugteam-final.diff`, `.bugteam-original-body.md`, `.bugteam-final-body.md`. Working directory ends clean.
- **Teammates own audit/fix comment posting.** Bugfind posts ONE per-loop review (parent body + child finding comments in a single batched POST, with review-fallback to a top-level issue comment). Bugfix posts the fix replies after committing. All comment, review, and reply POSTs belong to the teammates; the lead's single PR-write action is the final description rewrite at Step 4.5.
- **Lead owns the final PR description rewrite only** (Step 4.5), and only via the `pr-description-writer` agent. The lead does not compose the description inline.
- **One review per loop, findings as child comments of that review.** Each loop posts a single pull-request review whose body is the loop header and whose `comments[]` are the anchored findings. Each loop's review stands alone — one review created per loop, fully self-contained on the PR conversation.
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
