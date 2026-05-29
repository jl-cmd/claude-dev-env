# Utility scripts, teardown, PR body, permissions, report

## Utility scripts (progressive disclosure)

Fragile or repeatable shell sequences live in one of two shared script directories. Match the reference depth to the directory:

- **Package-root** [`_shared/pr-loop/scripts/`](../../../_shared/pr-loop/scripts/) holds `code_rules_gate.py`, `preflight.py`, `post_audit_thread.py`, and the permission helpers. Reference it as `../../../_shared/…` in markdown and `${CLAUDE_SKILL_DIR}/../../_shared/…` at runtime (resolves to `~/.claude/_shared/`). Inventory: [`../../../_shared/pr-loop/scripts/README.md`](../../../_shared/pr-loop/scripts/README.md).
- **Skill-tree** [`skills/_shared/pr-loop/scripts/`](../../_shared/pr-loop/scripts/) holds `teardown_worktrees.py`, `build_audit_prompt.py`, `build_fix_prompt.py`, `init_loop_state.py`, `write_audit_outcomes.py`, `write_fix_outcomes.py`, and `_path_resolver.py`. Reference it as `../../_shared/…` in markdown and `${CLAUDE_SKILL_DIR}/../_shared/…` at runtime (resolves to `~/.claude/skills/_shared/`).

Bugteam-specific scripts (e.g. revoke, see Step 5) live in the skill-local [`scripts/`](../scripts/) directory. Anthropic: [Progressive disclosure patterns](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#progressive-disclosure-patterns) — utility scripts are **executed**, not loaded into context as primary reading. Bugteam-script inventory: [`../scripts/README.md`](../scripts/README.md). Gate-only merge-base / diff semantics: [`../../../_shared/pr-loop/code-rules-gate.md`](../../../_shared/pr-loop/code-rules-gate.md).

### Pre-flight (recommended before Step 0)

From the repository root, run the command in `SKILL.md`. If the exit code is non-zero, stop and fix failing checks before granting permissions. Optional: `BUGTEAM_PREFLIGHT_SKIP=1` skips pre-flight (emergency only). Optional: `--pre-commit` when `.pre-commit-config.yaml` exists.

## Step 4 — Clean working tree

When the cycle exits (any reason), run these steps in order from **this** session (the lead).

1. **Delete the team:** `TeamDelete` removes `~/.claude/teams/bugteam/` and `~/.claude/tasks/bugteam/`. Only at convergence/cap/stuck — not between loops.

2. Run [`teardown_worktrees.py`](../../_shared/pr-loop/scripts/teardown_worktrees.py)
   to remove each PR's worktree (`git worktree remove`) and the run temp
   directory (Windows-safe `shutil.rmtree`):

   ```bash
   python "${CLAUDE_SKILL_DIR}/../_shared/pr-loop/scripts/teardown_worktrees.py" \
     --run-temp-dir "<run_temp_dir>" \
     --all-pr-jsons '<json array of {number, owner, repo}>'
   ```

   Tolerates already-removed worktrees and missing directories. Uses an
   `onexc`/`onerror` handler for Windows ReadOnly attribute safety
   (see `~/.claude/rules/windows-filesystem-safe.md`).

## Step 4.5 — Finalize the PR description (mandatory)

After teardown and before permission revoke, the lead rewrites the PR body to the PR’s **final cumulative state** — what the change delivers, not the bugteam process. This is the **only** PR-write the lead performs (audit and fix comments stay with teammates).

The lead delegates body text to the `pr-description-writer` agent so the global mandatory-pr-description-writer hook accepts the subsequent `gh pr edit`. The lead does **not** compose the body inline.

`pr-description-writer` comes from the global git-workflow rule in `claude-code-config`. Invoke with `Agent`:

```
Agent(
  subagent_type="pr-description-writer",
  mode="bypassPermissions",
  description="Rewrite PR <number> body from cumulative diff",
  prompt="<brief from steps below>"
)
```

If that subagent is missing, fall back to `general-purpose` with the same brief — the hook treats agent-authored bodies the same. If neither exists, log a warning and skip Step 4.5.

**Steps:**

1. Capture cumulative diff: `pull_request_read(method="get_diff", pullNumber=N, owner=O, repo=R)` → write the response text to `.bugteam-final.diff` using the `Write` tool.
2. Capture original body: `pull_request_read(method="get", pullNumber=N, owner=O, repo=R)` → extract `.body` from the response, write it to `.bugteam-original-body.md` using the `Write` tool.
3. Agent brief:
   - **Inputs:** diff path, original body path, head branch, base branch.
   - **Constraint:** describe what the PR delivers from the cumulative diff — behavior, user-visible effect, merge rationale. Process metadata (loops, fix counts, findings) stays in review comments.
   - **Preservation rule:** if the original body has manually curated sections (linked issues, screenshots, test plan, “Risk Assessment”, etc.), preserve them verbatim and only rewrite narrative around them.
   - **Output:** new body markdown.
4. Write `.bugteam-final-body.md`.
5. Publish the new body: `update_pull_request(pullNumber=N, owner=O, repo=R, body=<contents of .bugteam-final-body.md>)`.
6. Delete `.bugteam-final.diff`, `.bugteam-original-body.md`, `.bugteam-final-body.md`.

If Step 4.5 fails (agent error, hook block, network), report in the final report and continue to Step 5. The original PR body remains; commits and comments are unaffected.

## Step 5 — Revoke project permissions (mandatory, always)

After team cleanup — including on error, cap-reached, or stuck exits — run:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/revoke_project_claude_permissions.py"
```

This removes allow rules and `additionalDirectories` added in Step 0. Revoke is non-negotiable: leaving the grant in place would let future sessions inherit elevated `.claude/**` access without an explicit opt-in. Run revoke even if Step 4 partially failed; log cleanup errors separately.

## Step 6 — Final report

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

If exit = `cap reached`, name remaining bug count and suggest `/findbugs` for human triage. If `stuck`, name which findings the fix agent could not resolve. If `error`, surface the error and loop number.
