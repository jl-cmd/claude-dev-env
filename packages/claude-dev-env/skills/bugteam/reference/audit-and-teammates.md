# Gate, cycle, AUDIT, and FIX

## Pre-cycle: walk prior bugteam reviews end-first

**Pre-cycle: walk prior bugteam reviews end-first** (once per PR, after Step 2
and before iteration begins, when `last_action == "fresh"`). A re-invocation of
`/bugteam` on a PR with prior loops detects whether the most recent loop already
cleaned this HEAD (short-circuit) and otherwise records that prior loops were
dirty so the AUDIT runs against the latest diff with that signal in mind:

```python
dirty_review_count = 0
all_reviews = pull_request_read(
    method="get_reviews", pullNumber=N, owner=O, repo=R
)

NEW_BUGTEAM_HEADER_PREFIX = "**Bugteam audit completed**"
LEGACY_BUGTEAM_HEADER_PREFIX = "## /bugteam loop "
NEW_CLEAN_STATE_LABEL = "Clean — no findings"
LEGACY_CLEAN_TOKEN = "→ clean"


def is_bugteam_review(review_body: str) -> bool:
    return (
        review_body.startswith(NEW_BUGTEAM_HEADER_PREFIX)
        or review_body.startswith(LEGACY_BUGTEAM_HEADER_PREFIX)
    )


def is_clean_bugteam_review(review_body: str) -> bool:
    if review_body.startswith(NEW_BUGTEAM_HEADER_PREFIX):
        return NEW_CLEAN_STATE_LABEL in review_body.splitlines()[0]
    return review_body.rstrip().endswith(LEGACY_CLEAN_TOKEN)


prior_reviews = [
    rev for rev in all_reviews
    if is_bugteam_review(rev.get("body", ""))
]
prior_reviews.sort(key=lambda rev: rev["submitted_at"], reverse=True)
```

The classifier handles both shapes. The new shape — emitted by
`_shared/pr-loop/scripts/post_audit_thread.py` reading
`_shared/pr-loop/audit-reply-template.md` at runtime — opens with
`**Bugteam audit completed** —— Clean — no findings` on CLEAN and
`**Bugteam audit completed** —— Findings requested` on DIRTY. The legacy
shape — emitted before `post_audit_thread.py` became canonical — opens
with `## /bugteam loop <N> audit:` and ends with `→ clean` on CLEAN. Both
shapes are recognized so re-invocations on long-lived branches with
mixed-shape history classify correctly.

Iterate from index 0 (most recent) toward older entries:

- A bugteam review body whose first line carries the
  `Clean — no findings` state label (new shape) or whose body ends with
  `→ clean` (legacy shape) is **clean**; any other bugteam review body
  is **dirty**.
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

## Step 3 — The cycle (full detail)

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
      python "${CLAUDE_SKILL_DIR}/../_shared/pr-loop/scripts/code_rules_gate.py" --base origin/<baseRefName>
      ```

      `git merge-base` + `git diff --name-only` live inside the script; see [`../../_shared/pr-loop/scripts/README.md`](../../_shared/pr-loop/scripts/README.md) for what lives under this directory, and [`../../_shared/pr-loop/code-rules-gate.md`](../../_shared/pr-loop/code-rules-gate.md) for gate-only merge-base / invocation semantics. The lead runs this (not a teammate).

   2. If exit code **0** → continue to step 2.5 (AUDIT spawn) below.
   3. If exit code **non-zero** → run a **standards-fix pass** through the
      worker-spawn dispatcher (role `clean-coder`; see **Standards-fix
      action** below). Instructions: read the gate script’s stderr, edit the
      repo until a **re-run** of the **same** gate command exits **0**. On
      tiers 1 and 3 the headless worker edits and runs tests but never
      commits or pushes — the lead stages with explicit `git add`, mints the
      code-verifier verdict, then commits and pushes. Tier 2 keeps in-agent
      commit and push with `mode="bypassPermissions"`. Repeat standards-fix
      spawns until the gate exits **0** or **5** failed gate rounds (each
      round = one worker session after a non-zero gate). If still non-zero
      after 5 rounds → exit reason = `error: code rules gate failed pre-audit`.
   4. After gate exit **0**, increment `loop_count`. If `loop_count > 20`, exit reason = `cap reached` (counts **audits**, not standards-only rounds).
   5. Execute **AUDIT action** (spawn bugfind). Print progress: `Loop <L> audit: ...`

3. **FIX path** (when `last_action == "audited"` and `last_findings.total > 0`):
   1. Increment `loop_count`. If `loop_count > 20`, exit reason = `cap reached`.
   2. Execute **FIX action** (spawn bugfix clean-coder for audit findings). Print: `Loop <L> fix: commit ...`
   3. Set `last_action = "fixed"`, update `audit_log`, loop to step 1 (next iteration hits **pre-audit path** before the next AUDIT).

4. After **AUDIT**, update `last_action`, `last_findings`, `audit_log`; print the audit progress line if not already printed.

5. Loop.

**Note:** The first iteration uses **pre-audit path** then **AUDIT**. After a **FIX**, the next iteration runs **pre-audit path** again (gate → then AUDIT), so `validate_content` stays green before semantic audit.

## AUDIT action

Walk all A–Q categories through the worker-spawn dispatcher
([`worker-spawn.md`](../../_shared/pr-loop/worker-spawn.md)). Every loop
is a fresh process or a fresh agent context.

1. **Build the headless audit prompt** and write it to a prompt file under the
   per-PR workspace:

   ```bash
   python "${CLAUDE_SKILL_DIR}/../_shared/pr-loop/scripts/build_audit_prompt.py" \
     --owner <O> --repo <R> --pr-number <N> --loop <L> \
     --head-ref <head> --base-ref <base> \
     --worktree-path <worktree_path> --run-temp-dir <run_temp_dir> \
     --flavor headless \
     > "${run_temp_dir}/pr-<N>/loop-<L>.audit-prompt.xml"
   ```

   Optional: `--pr-body-file <path>` when the PR body is available on disk.

2. **Dispatch** via
   [`resolve_worker_spawn.py`](../../../scripts/resolve_worker_spawn.py). Role
   `bugteam` maps to primary agent `code-quality-agent`:

   ```bash
   python "${CLAUDE_SKILL_DIR}/../../scripts/resolve_worker_spawn.py" \
     --role bugteam \
     --prompt-file "${run_temp_dir}/pr-<N>/loop-<L>.audit-prompt.xml" \
     --cwd <worktree_path> \
     --run-temp-dir <run_temp_dir>
   ```

   The lead **blocks on the process** and reads the stdout JSON result.

3. **Follow the result:**

   - **Tier 1 or 3 served** (`tier_used` is `1` or `3`, exit `0`): the
     dispatcher ran the worker to completion. Read the outcome XML at
     `<worktree_path>/.bugteam-pr<N>-loop<L>.outcomes.xml`. The **lead**
     posts the audit review with
     [`post_audit_thread.py`](../../_shared/pr-loop/scripts/post_audit_thread.py)
     (see [SKILL.md § Audit posting](../SKILL.md#audit-posting)).
   - **`claude_agent_required`** (exit `2`, attempts include tier `2` with
     that reason): rebuild the prompt with default `--flavor agent` (omit
     `--flavor` or pass `agent`) and spawn the Agent-tool worker, including
     in-worker posting:

     ```
     Agent(
       subagent_type="code-quality-agent",
       name="bugfind-pr<N>-loop<L>",
       model="opus",
       run_in_background=true,
       description="Audit {owner}/{repo}#{N} loop {L}",
       prompt="<output of build_audit_prompt.py --flavor agent>"
     )
     ```

The audit prompt XML is emitted by
[`build_audit_prompt.py`](../../_shared/pr-loop/scripts/build_audit_prompt.py).
`--flavor headless` targets the dispatcher path (gh reads, outcome file, no
MCP/TaskCreate/Artifact). Default `--flavor agent` targets the Agent-tool
path (MCP posting).

`last_action = "audited"`. Append audit metadata to `audit_log`.

## Standards-fix action

Route through the worker-spawn dispatcher
([`worker-spawn.md`](../../_shared/pr-loop/worker-spawn.md)). Role
`clean-coder` maps to primary agent `clean-coder`. Every round is a fresh
process or a fresh agent context. The **5-round cap** stays (each round = one
worker session after a non-zero gate).

1. **Write a standards-fix prompt** under the per-PR workspace that includes
   the gate stderr, the exact gate re-run command, and the worktree path. On
   headless tiers the permission flag maps to each CLI's own flag
   (`--permission-mode bypassPermissions`).

2. **Dispatch:**

   ```bash
   python "${CLAUDE_SKILL_DIR}/../../scripts/resolve_worker_spawn.py" \
     --role clean-coder \
     --prompt-file "${run_temp_dir}/pr-<N>/loop-<L>.standards-fix-prompt.txt" \
     --cwd <worktree_path> \
     --run-temp-dir <run_temp_dir>
   ```

3. **Follow the result:**

   - **Tier 1 or 3 served** (`tier_used` is `1` or `3`, exit `0`): the
     headless worker edits and runs tests but never commits or pushes. The
     lead session stages the worker's files itself with an explicit `git add`
     (the session edit tracker does not see files the lead did not edit),
     mints the code-verifier verdict in its own context, then commits and
     pushes — so the commit gate and the staged-commit scans fire on the real
     diff. Re-run the gate command; if still non-zero, start the next round.
   - **`claude_agent_required`** (exit `2`, attempts include tier `2` with
     that reason): spawn the Agent-tool worker with in-agent commit and push:

     ```
     Agent(
       subagent_type="clean-coder",
       name="standards-fix-pr<N>-loop<L>-round<R>",
       model="opus",
       mode="bypassPermissions",
       run_in_background=true,
       description="Standards-fix {owner}/{repo}#{N} loop {L} round {R}",
       prompt="<gate stderr + re-run command + commit/push/shutdown>"
     )
     ```

The missing-subagent refusal in [`../SKILL.md`](../SKILL.md) applies to tier 2
only; headless tiers rely on the preflight's agent-definition-file check.

## FIX action (fresh teammate)

Route through the worker-spawn dispatcher
([`worker-spawn.md`](../../_shared/pr-loop/worker-spawn.md)). Role
`clean-coder` maps to primary agent `clean-coder`. Every loop is a fresh
process or a fresh agent context. The teammate sees only the latest audit’s
findings — prior-loop findings, fix history, and chat stay in the lead.

Pass finding comment URL, comment id, and thread node id for each finding
(from `loop_comment_index`) in the XML prompt.

1. **Build the headless fix prompt** and write it to a prompt file under the
   per-PR workspace:

   ```bash
   python "${CLAUDE_SKILL_DIR}/../_shared/pr-loop/scripts/build_fix_prompt.py" \
     --owner <O> --repo <R> --pr-number <N> --loop <L> \
     --head-ref <head> --base-ref <base> \
     --worktree-path <worktree_path> \
     --findings-json <findings_json_path> \
     --flavor headless \
     > "${run_temp_dir}/pr-<N>/loop-<L>.fix-prompt.xml"
   ```

2. **Dispatch** via
   [`resolve_worker_spawn.py`](../../../scripts/resolve_worker_spawn.py):

   ```bash
   python "${CLAUDE_SKILL_DIR}/../../scripts/resolve_worker_spawn.py" \
     --role clean-coder \
     --prompt-file "${run_temp_dir}/pr-<N>/loop-<L>.fix-prompt.xml" \
     --cwd <worktree_path> \
     --run-temp-dir <run_temp_dir>
   ```

   The lead **blocks on the process** and reads the stdout JSON result.

3. **Follow the result:**

   - **Tier 1 or 3 served** (`tier_used` is `1` or `3`, exit `0`): On tiers 1
     and 3 the headless worker edits and runs tests but never commits or
     pushes. The lead session stages the worker's files itself with an
     explicit `git add` (the session edit tracker does not see files the lead
     did not edit), mints the code-verifier verdict in its own context, then
     commits and pushes — so the commit gate and the staged-commit scans fire
     on the real diff. Read the outcome XML at
     `<worktree_path>/.bugteam-pr<N>-loop<L>.fix-outcomes.xml`. The **lead**
     posts one reply per finding using the unified template at
     [`../../_shared/pr-loop/audit-reply-template.md`](../../_shared/pr-loop/audit-reply-template.md)
     — the full header / horizontal rule / `<action_heading> ✅` /
     explanation / anchored-bullet / closing-paragraph skeleton, with
     `<status_line>` set per the path (`Fixed in <short_sha>` for
     `status=fixed`, `Could not address this loop` for
     `status=could_not_address`, `Hook blocked the fix commit` for
     `status=hook_blocked`). Per-thread reply and `resolve_thread` are
     atomic; the mechanics follow the shared 13-step sequence in
     [`../../_shared/pr-loop/fix-protocol.md`](../../_shared/pr-loop/fix-protocol.md)
     (step 12 carries the exact reply-and-resolve sequence).
   - **`claude_agent_required`** (exit `2`, attempts include tier `2` with
     that reason): Tier 2 keeps the current behavior end to end, including
     in-agent commit and push and `mode="bypassPermissions"`. Rebuild the
     prompt with default `--flavor agent` (omit `--flavor` or pass `agent`)
     and spawn the Agent-tool worker, pinning model opus:

     ```
     Agent(
       subagent_type="clean-coder",
       name="bugfix-pr<N>-loop<L>",
       model="opus",
       mode="bypassPermissions",
       run_in_background=true,
       description="Bugfix PR <N> loop <L>",
       prompt="<output of build_fix_prompt.py --flavor agent>"
     )
     ```

     After commit, the teammate posts one reply per finding using the same
     unified template and writes outcome XML (schema in
     [`../PROMPTS.md`](../PROMPTS.md)).

The fix prompt XML is emitted by
[`build_fix_prompt.py`](../../_shared/pr-loop/scripts/build_fix_prompt.py).
`--flavor headless` targets the dispatcher path (gh reads, outcome file, no
commit/push/MCP/TaskCreate/Artifact). Default `--flavor agent` targets the
Agent-tool path (in-agent commit, push, and MCP replies). On headless tiers
the permission flag maps to each CLI's own flag
(`--permission-mode bypassPermissions`).

### Tier-1 flag profiles

When tier-1 (headless grok) runs for audit or fix work and the **grok-spawn**
skill is installed on the host, take CLI flag profiles from that skill's
flag-profiles reference. Do not restate those flags here. When the skill is
absent, use the host's grok headless defaults from the worker-spawn protocol
and the headless runner. This page keeps the Agent-tool spawn shape for
Claude-host teammates.

### Shutdown (bugfix)

Same self-termination model as bugfind. Missing notification → hard blocker.

`approve: false` → `error: bugfix teammate refused shutdown` → Step 4 (`pr-loop-lifecycle` Close).

Substitute placeholders from `last_findings` into the fix prompt per [`../PROMPTS.md`](../PROMPTS.md). The agent-flavor spawn XML includes TaskCreate/self_audit_checklist for task tracking — the tier-2 FIX subagent MUST create tasks before starting. Headless flavors omit TaskCreate.

**Verify push:** `git rev-parse HEAD` after fix must differ from before; new HEAD must exist on `origin/<branch>` (`git fetch origin <branch> && git rev-parse origin/<branch>` matches `HEAD`). If HEAD did not change → `stuck — bugfix teammate could not address findings`. On tiers 1 and 3 this check runs after the **lead** commit and push.

**Scope verification.** Run `git diff HEAD~1 --name-only` and compare against the set of files referenced in `bugs_to_fix`. When the commit touches files NOT in the `bugs_to_fix` list, judge whether the extras are a coherent part of the fix: a shared helper the auditor did not think to name, a test file that exercises the fix, a config update the fix requires. If the extras are coherent with the fix, note them in the outcome XML's `<scope_notes>` and keep the outcome as `fixed`. If the extras look unrelated, suspicious, or out of scope, downgrade to `unverified_fixed` with reason `commit touched unexpected files: <list>`. The auditor's file list is a default, not a contract — the fix's coherence is the contract.

`last_action = "fixed"`. Append fix line to `audit_log`.
