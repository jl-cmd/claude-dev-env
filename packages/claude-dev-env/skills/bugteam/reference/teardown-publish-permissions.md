# Utility scripts, teardown, PR body, permissions, report

## Utility scripts (progressive disclosure)

Fragile or repeatable shell sequences belong in `scripts/`. Anthropic: [Progressive disclosure patterns](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#progressive-disclosure-patterns) — utility scripts are **executed**, not loaded into context as primary reading. Details: [`../scripts/README.md`](../scripts/README.md).

### Pre-flight (recommended before Step 0)

From the repository root, run the command in `SKILL.md`. If the exit code is non-zero, stop and fix failing checks before granting permissions. Optional: `BUGTEAM_PREFLIGHT_SKIP=1` skips pre-flight (emergency only). Optional: `--pre-commit` when `.pre-commit-config.yaml` exists.

## Step 4 — Tear down the team and clean working tree

When the cycle exits (any reason), run these steps in order from **this** session (the lead).

1. **Confirm every teammate has shut down.** Any teammate still alive (for example, from an aborted shutdown mid-loop) must receive a shutdown message first. For each remaining teammate name:

   ```
   SendMessage(to="<teammate_name>", message={"type": "shutdown_request", "reason": "bugteam cycle ending"})
   ```

   Product docs: the lead’s cleanup checks for active teammates — shut them down first. Verbatim quote: [`../sources.md`](../sources.md) (lead cleanup).

   If any teammate returns `approve: false` during cleanup, log the name (for example `cleanup warning: <teammate_name> refused shutdown_request`) and **still** proceed to `TeamDelete`. `TeamDelete` may fail if teammates remain; if so, surface the error in the final report. Do not abort the sequence — continue through temp-dir deletion, Step 4.5, and Step 5.

2. **Clean up the team** with `TeamDelete()` (no arguments — reads `<team_name>` from session context). Maps to “clean up the team” in the docs; quote: [`../sources.md`](../sources.md).

3. **Delete the per-team temp directory** using the Python one-liner in `SKILL.md` with the same literal `<team_temp_dir>` from Step 2. The one-liner uses an `onexc`/`onerror` handler that strips the Windows ReadOnly attribute and retries the failing syscall — `ignore_errors=True` is unsafe on Windows because it silently swallows ReadOnly-attribute failures (see `~/.claude/rules/windows-filesystem-safe.md`).

## Step 4.5 — Finalize the PR description (mandatory)

After teardown and before permission revoke, the lead rewrites the PR body to the PR’s **final cumulative state** — what the change delivers, not the bugteam process. This is the **only** PR-write the lead performs (audit and fix comments stay with teammates).

The lead delegates body text to the `pr-description-writer` agent so the global mandatory-pr-description-writer hook accepts the subsequent `gh pr edit`. The lead does **not** compose the body inline.

`pr-description-writer` comes from the global git-workflow rule in `claude-code-config`. Invoke with `Agent`:

```
Agent(
  subagent_type="pr-description-writer",
  description="Rewrite PR <number> body from cumulative diff",
  prompt="<brief from steps below>"
)
```

If that subagent is missing, fall back to `general-purpose` with the same brief — the hook treats agent-authored bodies the same. If neither exists, log a warning and skip Step 4.5.

**Steps:**

1. Capture cumulative diff: `gh pr diff <number> -R <owner>/<repo> > .bugteam-final.diff`.
2. Capture original body: `gh pr view <number> -R <owner>/<repo> --json body --jq .body > .bugteam-original-body.md`.
3. Agent brief:
   - **Inputs:** diff path, original body path, head branch, base branch.
   - **Constraint:** describe what the PR delivers from the cumulative diff — behavior, user-visible effect, merge rationale. Process metadata (loops, fix counts, findings) stays in review comments.
   - **Preservation rule:** if the original body has manually curated sections (linked issues, screenshots, test plan, “Risk Assessment”, etc.), preserve them verbatim and only rewrite narrative around them.
   - **Output:** new body markdown.
4. Write `.bugteam-final-body.md`.
5. `gh pr edit <number> -R <owner>/<repo> --body-file .bugteam-final-body.md`.
6. Delete `.bugteam-final.diff`, `.bugteam-original-body.md`, `.bugteam-final-body.md`.

If Step 4.5 fails (agent error, hook block, network), report in the final report and continue to Step 5. The original PR body remains; commits and comments are unaffected.

## Step 5 — Revoke project permissions (mandatory, always)

After team cleanup — including on error, cap-reached, or stuck exits — run the revoke command from `SKILL.md`.

This removes allow rules and `additionalDirectories` added in Step 0. Revoke is non-negotiable: leaving the grant in place would let future sessions inherit elevated `.claude/**` access without an explicit opt-in. Run revoke even if Step 4 partially failed; log cleanup errors separately.

## Step 6 — Final report

Template and exit hints are in `SKILL.md`. If exit = `cap reached`, name remaining bug count and suggest `/findbugs` for human triage. If `stuck`, name which findings the fix agent could not resolve. If `error`, surface the error and loop number.
