# Utility scripts, teardown, PR body, permissions, report

The ordered close sequence for a PR-loop run. `<caller>` is the invoking skill's name (`bugteam`, `pr-converge`, `autoconverge`, `qbug`); it prefixes scratch files and the final-report header.

## Utility scripts (progressive disclosure)

Fragile or repeatable shell sequences live under [`skills/_shared/pr-loop/scripts/`](../../_shared/pr-loop/scripts/). From a skill directory, reference them as `../_shared/…` in markdown and `${CLAUDE_SKILL_DIR}/../_shared/…` at runtime (resolves to `~/.claude/skills/_shared/`). That tree holds gate and permission helpers (`code_rules_gate.py`, `preflight.py`, `post_audit_thread.py`, grant/revoke) and loop helpers (`teardown_worktrees.py`, `build_audit_prompt.py`, `build_fix_prompt.py`, `init_loop_state.py`, outcome writers, `_path_resolver.py`). Inventory: [`../../_shared/pr-loop/scripts/README.md`](../../_shared/pr-loop/scripts/README.md).

Caller-specific scripts live in the calling skill's own `scripts/` directory with their own README inventory. Anthropic: [Progressive disclosure patterns](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#progressive-disclosure-patterns) — utility scripts are **executed**, not loaded into context as primary reading. Gate-only merge-base / diff semantics: [`../../_shared/pr-loop/code-rules-gate.md`](../../_shared/pr-loop/code-rules-gate.md).

## Clean working tree

When the run exits (any reason), run these steps in order from **this** session (the lead).

1. **TeamDelete (team callers only):** a caller that created an agent team removes `~/.claude/teams/<caller>/` and `~/.claude/tasks/<caller>/` with `TeamDelete`. Only at convergence/cap/stuck — not between loops. Single-agent and workflow callers skip this step.

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

## Publish the final PR description (mandatory)

After teardown and before permission revoke, the lead rewrites the PR body to the PR's **final cumulative state** — what the change delivers, not the loop's process. This is the **only** PR-write the lead performs (audit and fix comments stay with the agents that produced them).

The lead composes the body text directly against `docs/PR_DESCRIPTION_GUIDE.md` — no agent spawn — so the body passes the `pr_description_enforcer` hook's style audit on the `gh pr edit` that follows.

**Steps:**

1. Capture cumulative diff: `pull_request_read(method="get_diff", pullNumber=N, owner=O, repo=R)` → write the response text to `.<caller>-final.diff` using the `Write` tool.
2. Capture original body: `pull_request_read(method="get", pullNumber=N, owner=O, repo=R)` → extract `.body` from the response, write it to `.<caller>-original-body.md` using the `Write` tool.
3. Compose the new body from those inputs:
   - **Inputs:** diff path, original body path, head branch, base branch.
   - **Constraint:** describe what the PR delivers from the cumulative diff — behavior, user-visible effect, merge rationale. Process metadata (loops, fix counts, findings) stays in review comments.
   - **Preservation rule:** if the original body has manually curated sections (linked issues, screenshots, test plan, "Risk Assessment", etc.), preserve them verbatim and only rewrite narrative around them.
   - **Output:** new body markdown.
4. Write `.<caller>-final-body.md`.
5. Publish the new body: `update_pull_request(pullNumber=N, owner=O, repo=R, body=<contents of .<caller>-final-body.md>)`.
6. Remove `.<caller>-final.diff`, `.<caller>-original-body.md`, `.<caller>-final-body.md`.

If this step fails (hook block, network), report in the final report and continue to the revoke. The original PR body remains; commits and comments are unaffected.

## Revoke project permissions (mandatory, always)

After team cleanup — including on error, cap-reached, or stuck exits — run:

```bash
python "${CLAUDE_SKILL_DIR}/../_shared/pr-loop/scripts/revoke_project_claude_permissions.py"
```

This removes allow rules and `additionalDirectories` added at open. Revoke is non-negotiable: leaving the grant in place would let future sessions inherit elevated `.claude/**` access without an explicit opt-in. Run revoke even if teardown partially failed; log cleanup errors separately.

## Final report

```
/<caller> exit: <converged | cap reached | stuck | error>
Loops: <loop_count>
Starting commit: <starting_sha7>
Final commit: <current_HEAD_sha7>
Net change: <total_files> files, +<total_add>/-<total_del>

Loop log:
1 audit: 3P0 2P1 0P2
...
```

If exit = `cap reached`, name remaining bug count and suggest `/findbugs` for human triage. If `stuck`, name which findings the fix agent could not resolve. If `error`, surface the error and loop number.
