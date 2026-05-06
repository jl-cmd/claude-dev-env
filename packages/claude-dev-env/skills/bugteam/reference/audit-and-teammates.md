# Gate, cycle, AUDIT, and FIX

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
   3. If exit code **non-zero** → spawn a new **clean-coder** teammate — **standards-fix pass** — with instructions: read the script’s stderr, edit the repo until a **re-run** of the **same** gate command exits **0**, then one commit, `git push`, shutdown. Repeat standards-fix spawns until the gate exits **0** or **5** failed gate rounds (each round = one teammate session after a non-zero gate). If still non-zero after 5 rounds → exit reason = `error: code rules gate failed pre-audit`.
   4. After gate exit **0**, increment `loop_count`. If `loop_count > 10`, exit reason = `cap reached` (counts **audits**, not standards-only rounds).
   5. Execute **AUDIT action** (spawn bugfind). Print progress: `Loop <L> audit: ...`

3. **FIX path** (when `last_action == "audited"` and `last_findings.total > 0`):
   1. Increment `loop_count`. If `loop_count > 10`, exit reason = `cap reached`.
   2. Execute **FIX action** (spawn bugfix clean-coder for audit findings). Print: `Loop <L> fix: commit ...`
   3. Set `last_action = "fixed"`, update `audit_log`, loop to step 1 (next iteration hits **pre-audit path** before the next AUDIT).

4. After **AUDIT**, update `last_action`, `last_findings`, `audit_log`; print the audit progress line if not already printed.

5. Loop.

**Note:** The first iteration uses **pre-audit path** then **AUDIT**. After a **FIX**, the next iteration runs **pre-audit path** again (gate → then AUDIT), so `validate_content` stays green before semantic audit.

## AUDIT action (clean-room teammate, fresh per loop)

Capture a fresh PR diff for this loop into the per-PR scoped directory so concurrent `/bugteam` runs keep patches isolated. Use the literal `<run_temp_dir>` resolved once in Step 2 — Claude resolves the absolute path; every shell receives the same literal value.

Commands and `Agent(...)` shape: `SKILL.md`.

`<run_temp_dir>` includes the sanitized `team_name` and timestamp; `team_name` is already prefixed with `bugteam-`. Claude resolves `Path(tempfile.gettempdir()) / team_name` once and passes that absolute path to every shell. `tempfile.gettempdir()` honors `TMPDIR`, `TEMP`, `TMP` and falls back to the OS temp directory, so the same approach works on macOS, Linux, Windows cmd.exe, and PowerShell.

Each loop calls `Agent` again with a fresh invocation so the teammate starts with its own context window. Doc line on lead history: [`../sources.md`](../sources.md).

See [`../PROMPTS.md`](../PROMPTS.md) for AUDIT spawn-prompt XML and bugfind outcome schema. Substitute placeholders (`repo`, `branch`, `base_branch`, `pr_url`, `loop`, `diff_path`) into the `prompt` argument.

After the teammate returns, the lead reads `.bugteam-pr<N>-loop<L>.outcomes.xml` from the worktree directory with the `Read` tool, parses it, and populates `loop_comment_index` from `<finding>` elements.

### Shutdown (bugfind)

Teammates self-terminate when complete — the background-completion notification arrives and the lead reads the outcomes XML. If the notification does not arrive within the lead timeout (120s), treat as a hard blocker and abort the loop.

`last_action = "audited"`. Append audit metadata to `audit_log`.

### Parallel auditors (`loop_count >= 4`)

The pre-audit gate must pass immediately before this step. After three full audit/fix rounds without convergence, issue eleven `Agent` calls in **one** assistant message so they run in parallel:

```
Agent(subagent_type="code-quality-agent", name="bugfind-pr<N>-loop<L>-a", team_name="<team_name>", model="opus", run_in_background=true, description="Bugfind audit PR <N> loop <L> validator", prompt="<audit XML; poll for all 10 sibling XMLs at <run_temp_dir>/pr-<N>/loop-<L>-b.outcomes.xml through <run_temp_dir>/pr-<N>/loop-<L>-k.outcomes.xml (60s timeout, 2s interval); on timeout: log diagnostics entry, proceed with validated findings from available XMLs; validate each finding: file exists, line in bounds, excerpt matches claimed line, category A-J, severity P0/P1/P2; quarantine hallucinated findings to <run_temp_dir>/pr-<N>/loop-<L>-diagnostics.json under validator_rejected; de-dup by (file, line, category), max severity wins, keep longest description on conflict; re-id as loop<L>-<K>; write <worktree_path>/.bugteam-pr<N>-loop<L>.outcomes.xml; post review>")
Agent(subagent_type="code-quality-agent", name="bugfind-pr<N>-loop<L>-b", team_name="<team_name>", model="haiku", run_in_background=true, description="Bugfind audit PR <N> loop <L> variant b", prompt="<audit XML; write outcome to <run_temp_dir>/pr-<N>/loop-<L>-b.outcomes.xml; skip PR posting>")
Agent(subagent_type="code-quality-agent", name="bugfind-pr<N>-loop<L>-c", team_name="<team_name>", model="haiku", run_in_background=true, description="Bugfind audit PR <N> loop <L> variant c", prompt="<audit XML; write outcome to <run_temp_dir>/pr-<N>/loop-<L>-c.outcomes.xml; skip PR posting>")
Agent(subagent_type="code-quality-agent", name="bugfind-pr<N>-loop<L>-d", team_name="<team_name>", model="haiku", run_in_background=true, description="Bugfind audit PR <N> loop <L> variant d", prompt="<audit XML; write outcome to <run_temp_dir>/pr-<N>/loop-<L>-d.outcomes.xml; skip PR posting>")
Agent(subagent_type="code-quality-agent", name="bugfind-pr<N>-loop<L>-e", team_name="<team_name>", model="haiku", run_in_background=true, description="Bugfind audit PR <N> loop <L> variant e", prompt="<audit XML; write outcome to <run_temp_dir>/pr-<N>/loop-<L>-e.outcomes.xml; skip PR posting>")
Agent(subagent_type="code-quality-agent", name="bugfind-pr<N>-loop<L>-f", team_name="<team_name>", model="haiku", run_in_background=true, description="Bugfind audit PR <N> loop <L> variant f", prompt="<audit XML; write outcome to <run_temp_dir>/pr-<N>/loop-<L>-f.outcomes.xml; skip PR posting>")
Agent(subagent_type="code-quality-agent", name="bugfind-pr<N>-loop<L>-g", team_name="<team_name>", model="haiku", run_in_background=true, description="Bugfind audit PR <N> loop <L> variant g", prompt="<audit XML; write outcome to <run_temp_dir>/pr-<N>/loop-<L>-g.outcomes.xml; skip PR posting>")
Agent(subagent_type="code-quality-agent", name="bugfind-pr<N>-loop<L>-h", team_name="<team_name>", model="haiku", run_in_background=true, description="Bugfind audit PR <N> loop <L> variant h", prompt="<audit XML; write outcome to <run_temp_dir>/pr-<N>/loop-<L>-h.outcomes.xml; skip PR posting>")
Agent(subagent_type="code-quality-agent", name="bugfind-pr<N>-loop<L>-i", team_name="<team_name>", model="haiku", run_in_background=true, description="Bugfind audit PR <N> loop <L> variant i", prompt="<audit XML; write outcome to <run_temp_dir>/pr-<N>/loop-<L>-i.outcomes.xml; skip PR posting>")
Agent(subagent_type="code-quality-agent", name="bugfind-pr<N>-loop<L>-j", team_name="<team_name>", model="haiku", run_in_background=true, description="Bugfind audit PR <N> loop <L> variant j", prompt="<audit XML; write outcome to <run_temp_dir>/pr-<N>/loop-<L>-j.outcomes.xml; skip PR posting>")
Agent(subagent_type="code-quality-agent", name="bugfind-pr<N>-loop<L>-k", team_name="<team_name>", model="haiku", run_in_background=true, description="Bugfind audit PR <N> loop <L> variant k", prompt="<audit XML; write outcome to <run_temp_dir>/pr-<N>/loop-<L>-k.outcomes.xml; skip PR posting>")
```

Teammate `-a` is the opus validator: polls for all 10 sibling XMLs at explicit absolute paths under `<run_temp_dir>/pr-<N>` (60s timeout, 2s interval; on timeout: log diagnostics entry, proceed with validated findings from available XMLs), then validates each finding — file exists, line in bounds, excerpt matches claimed line, category is A–J, severity is P0/P1/P2. Hallucinated findings are quarantined to `<run_temp_dir>/pr-<N>/loop-<L>-diagnostics.json` under `validator_rejected`. Valid findings are de-duplicated by `(file, line, category)` (max severity wins, keep longest description on conflict) and re-assigned merged IDs as `loop<L>-<K>`. The `-a` prompt must embed sibling paths as literal absolutes so `Read` works without discovery.

All subagents self-terminate via background completion. The lead awaits only the validator (-a) notification (120s timeout). Missing notification → hard blocker.

## FIX action (fresh teammate)

`Agent` shape in `SKILL.md`. The teammate sees only the latest audit’s findings — each `Agent` call starts with a fresh context window; prior-loop findings, fix history, and chat stay in the lead.

Pass finding comment URL and id for each finding (from `loop_comment_index`) in the XML prompt so the teammate owns replies. After commit: one reply per finding (`Fixed in <commit_sha>` or `Could not address this loop: <one-line reason>`). Same identity model as bugfind: teammate posts; lead waits.

After replies, the teammate writes outcome XML (schema in [`../PROMPTS.md`](../PROMPTS.md)).

### Shutdown (bugfix)

Same self-termination model as bugfind. Missing notification → hard blocker.

`approve: false` → `error: bugfix teammate refused shutdown` → Step 4 then 5.

Substitute placeholders from `last_findings` into the fix prompt per [`../PROMPTS.md`](../PROMPTS.md).

**Verify push:** `git rev-parse HEAD` after fix must differ from before; new HEAD must exist on `origin/<branch>` (`git fetch origin <branch> && git rev-parse origin/<branch>` matches `HEAD`). If HEAD did not change → `stuck — bugfix teammate could not address findings`.

`last_action = "fixed"`. Append fix line to `audit_log`.
