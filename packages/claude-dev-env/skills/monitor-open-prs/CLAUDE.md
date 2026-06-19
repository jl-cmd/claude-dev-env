# monitor-open-prs skill

Discovers every open pull request across the `jl-cmd/*` and `JonEcho/*` owner scopes, dispatches `/bugteam` on each with the `--bugbot-retrigger` flag, and polls for new Cursor bugbot replies after each bugteam run.

**Trigger:** `/monitor-open-prs`, "sweep the open PRs", "audit the open PR backlog".

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Full workflow: refusal cases, discovery, dispatch, post-convergence polling, final report |
| `test_skill_contract.py` | Contract tests for the skill |
| `packages/claude-dev-env/skills/monitor-open-prs/scripts/discover_open_prs.py` | Shells out to `gh search prs` per owner scope and flattens results to a uniform dict shape |
| `packages/claude-dev-env/skills/monitor-open-prs/scripts/test_discover_open_prs.py` | Tests for the discovery helper |

## Subdirectories

| Directory | Role |
|---|---|
| `scripts/` | Discovery helper and its tests |

## Workflow summary

1. Call `discover_open_prs.discover_open_prs(all_owners=["jl-cmd", "JonEcho"])` to get the full open-PR list.
2. For each PR, invoke `/bugteam --bugbot-retrigger <pr_number>` (omit `--bugbot-retrigger` if `CLAUDE_REVIEWS_DISABLED` has `bugbot`).
3. After each bugteam run, poll for new bugbot comments on a 60s → 120s → 240s → 480s → 960s backoff. Re-invoke bugteam if new findings appear.
4. Emit a sweep summary when all PRs exit polling.

## Refusals (checked first)

- `CLAUDE_REVIEWS_DISABLED` has `bugteam` → stop with a message.
- GitHub API not accessible → stop.
- Uncommitted changes in the caller's repo → stop.
- Required subagent types missing (`code-quality-agent`, `clean-coder`) → stop.
