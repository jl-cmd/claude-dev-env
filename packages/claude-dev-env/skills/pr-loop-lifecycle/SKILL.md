---
name: pr-loop-lifecycle
description: >-
  Opens and closes a PR-loop run: the .claude/** permission grant (with the
  auto-mode AskUserQuestion escalation when the classifier blocks it),
  worktree preflight and cwd routing, then the ordered close — conditional
  TeamDelete for team callers, worktree teardown, working-tree clean, PR
  description rewrite composed by the lead, the always-run permission
  revoke, and the caller-parameterized final report. Invoked by PR-loop
  orchestrators (bugteam, pr-converge, autoconverge, qbug) at run start and
  run end, including error exits; not for general git cleanup or permission
  management outside a PR loop.
---

# PR Loop Lifecycle

**Core principle:** a PR-loop run opens with an explicit, revocable permission grant and closes the same way every time — teardown, description rewrite, revoke, report — no matter how the run ended.

## How callers invoke this

- **Skill-capable contexts** (a lead session with the `Skill` tool): `Skill({skill: "pr-loop-lifecycle", args: "--skill <caller> <open|close> [parameters]"})`.
- **Fallback** (a subagent or teammate without the `Skill` tool): the caller's spawn prompt says "Read `~/.claude/skills/pr-loop-lifecycle/SKILL.md` and apply the `<open|close>` section with the parameters below."

The caller passes its identity (fills the final-report header and scratch-file prefix), whether it runs an agent team (gates the TeamDelete step), and at close time the run's exit reason, loop count, and SHAs.

## Open

1. **Grant project permissions:**
   `python "$HOME/.claude/_shared/pr-loop/scripts/grant_project_claude_permissions.py"`
   The script writes idempotent allow-rules and `additionalDirectories` entries into `~/.claude/settings.json` so subagents can edit the project's `.claude/` tree without prompting.

   **Auto-mode escalation:** in an unattended run the permission classifier can block this grant as an unrequested allowlist change. Keep the run alive — surface the exact command to the user through `AskUserQuestion` and ask them to approve it or run it themselves with the `!` prefix. Continue once the grant lands. A user who wants future runs to skip the prompt can add a standing Bash allow-rule for the script in their settings.

2. **Worktree preflight:** confirm the session is isolated (the working directory path includes `.claude/worktrees/`) before the first tick or round. Classify the working tree against the PR's repo with
   `python "$HOME/.claude/skills/_shared/pr-loop/scripts/preflight_worktree.py" --owner <O> --repo <R> --mode <classify|strict>`
   and route per the caller's cwd-routing reference (pr-converge Step 1.5 for the classify route; autoconverge pre-flight for the strict route). Capture the session worktree path before routing away — close-time steps target the session repo.

## Close

Run these in order from the lead session on EVERY exit — converged, cap reached, stuck, or error.

1. **TeamDelete (team callers only).** Callers that created an agent team remove it with `TeamDelete`; single-agent and workflow callers skip this step.
2. **Worktree teardown:**
   ```bash
   python "$HOME/.claude/skills/_shared/pr-loop/scripts/teardown_worktrees.py" \
     --run-temp-dir "<run_temp_dir>" \
     --all-pr-jsons '<json array of {number, owner, repo}>'
   ```
   Tolerates already-removed worktrees and missing directories; removal is Windows-safe per `~/.claude/rules/windows-filesystem-safe.md`.
3. **Clean the working tree.** Return to the session worktree, remove run-scoped scratch files, and leave `git status` clean of run artifacts.
4. **Rewrite the PR description.** Follow [`reference/teardown-publish-permissions.md` § Publish the final PR description](reference/teardown-publish-permissions.md): capture the cumulative diff and original body, compose the new body directly against `docs/PR_DESCRIPTION_GUIDE.md`, publish via `update_pull_request`, remove the scratch files. On failure, report it and continue — the revoke still runs.
5. **Revoke project permissions (always):**
   `python "$HOME/.claude/_shared/pr-loop/scripts/revoke_project_claude_permissions.py"`
   Non-negotiable, including on error exits: leaving the grant in place lets future sessions inherit elevated `.claude/**` access without an explicit opt-in. Run revoke even when earlier close steps partially failed; log cleanup errors separately.
6. **Final report.** Print the caller's report block verbatim — no paraphrase, no extra commentary:
   ```
   /<caller> exit: <converged | cap reached | stuck | error>
   Loops: <loop_count>
   Starting commit: <starting_sha7>
   Final commit: <current_HEAD_sha7>
   ```
   Callers append their own lines (net change, loop log, converged SHAs) per their SKILL.md.

## Gotchas

- **Revoke runs on the error path too.** The single most common lifecycle defect is a run that dies mid-loop and leaves the `.claude/**` grant in settings.
- **Close targets the session repo.** A cross-repo run that routed its cwd into the PR's worktree returns to the session worktree before steps 3–5; grant and revoke read the current working directory.
- **TeamDelete fires once, at run end.** Removing the team between audit-fix iterations is a bug.

## Folder map

- `SKILL.md` — this file.
- `reference/teardown-publish-permissions.md` — the full close sequence: utility-script homes, teardown, PR-description rewrite brief, revoke, report shape.
