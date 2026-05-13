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
prior_reviews = [
    rev for rev in all_reviews
    if rev.get("body", "").startswith("## /bugteam loop ")
]
prior_reviews.sort(key=lambda rev: rev["submitted_at"], reverse=True)
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
      python "${CLAUDE_SKILL_DIR}/../../_shared/pr-loop/scripts/code_rules_gate.py" --base origin/<baseRefName>
      ```

      `git merge-base` + `git diff --name-only` live inside the script; see [`../../../_shared/pr-loop/scripts/README.md`](../../../_shared/pr-loop/scripts/README.md) for what lives under this directory, and [`../../../_shared/pr-loop/code-rules-gate.md`](../../../_shared/pr-loop/code-rules-gate.md) for gate-only merge-base / invocation semantics. The lead runs this (not a teammate).

   2. If exit code **0** → continue to step 2.5 (AUDIT spawn) below.
   3. If exit code **non-zero** → spawn a new **clean-coder** teammate (`mode="bypassPermissions"`) — **standards-fix pass** — with instructions: read the script’s stderr, edit the repo until a **re-run** of the **same** gate command exits **0**, then one commit, `git push`, shutdown. Repeat standards-fix spawns until the gate exits **0** or **5** failed gate rounds (each round = one teammate session after a non-zero gate). If still non-zero after 5 rounds → exit reason = `error: code rules gate failed pre-audit`.
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

Spawn one audit agent that walks all A–K categories:

```
Agent(
  subagent_type="code-quality-agent",
  name="bugfind-pr<N>-loop<L>",
  model="opus",
  run_in_background=true,
  description="Audit {owner}/{repo}#{N} loop {L}",
  prompt="<output of build_audit_prompt.py; see ../../_shared/pr-loop/scripts/build_audit_prompt.py>"
)
```

The audit prompt XML is emitted by
[`build_audit_prompt.py`](../../_shared/pr-loop/scripts/build_audit_prompt.py).
Run it with `--owner --repo --pr-number --loop --head-ref --base-ref --worktree-path --run-temp-dir`
to generate the complete `<spawn_prompt>` XML on stdout.

`last_action = "audited"`. Append audit metadata to `audit_log`.

## FIX action (fresh teammate)

Spawn:

```
Agent(
  subagent_type="clean-coder",
  name="bugfix-pr<N>-loop<L>",
  model="opus",
  mode="bypassPermissions",
  run_in_background=true,
  description="Bugfix PR <N> loop <L>",
  prompt="<output of build_fix_prompt.py; see ../../_shared/pr-loop/scripts/build_fix_prompt.py>"
)
```

The teammate sees only the latest audit’s findings — each `Agent` call starts with a fresh context window; prior-loop findings, fix history, and chat stay in the lead.

Pass finding comment URL and id for each finding (from `loop_comment_index`) in the XML prompt so the teammate owns replies. After commit: one reply per finding (`Fixed in <commit_sha>` or `Could not address this loop: <one-line reason>`). Same identity model as bugfind: teammate posts; lead waits.

After replies, the teammate writes outcome XML (schema in [`../PROMPTS.md`](../PROMPTS.md)).

### Shutdown (bugfix)

Same self-termination model as bugfind. Missing notification → hard blocker.

`approve: false` → `error: bugfix teammate refused shutdown` → Step 4 then 5.

Substitute placeholders from `last_findings` into the fix prompt per [`../PROMPTS.md`](../PROMPTS.md). The spawn XML includes TaskCreate/self_audit_checklist for task tracking — the FIX subagent MUST create tasks before starting.

**Verify push:** `git rev-parse HEAD` after fix must differ from before; new HEAD must exist on `origin/<branch>` (`git fetch origin <branch> && git rev-parse origin/<branch>` matches `HEAD`). If HEAD did not change → `stuck — bugfix teammate could not address findings`.

**Scope verification.** Run `git diff HEAD~1 --name-only` and compare against the set of files referenced in `bugs_to_fix`. When the commit touches files NOT in the `bugs_to_fix` list, judge whether the extras are a coherent part of the fix: a shared helper the auditor did not think to name, a test file that exercises the fix, a config update the fix requires. If the extras are coherent with the fix, note them in the outcome XML's `<scope_notes>` and keep the outcome as `fixed`. If the extras look unrelated, suspicious, or out of scope, downgrade to `unverified_fixed` with reason `commit touched unexpected files: <list>`. The auditor's file list is a default, not a contract — the fix's coherence is the contract.

`last_action = "fixed"`. Append fix line to `audit_log`.
