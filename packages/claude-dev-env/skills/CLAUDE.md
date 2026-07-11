# Skills Directory

Each skill is a self-contained folder Claude Code loads on demand. At startup, only the skill's `name` and `description` metadata load. The full `SKILL.md` body and any support files load only when a skill becomes relevant to the conversation.

## Skill folder convention

| Item | Role |
|---|---|
| `SKILL.md` | Required entry point. YAML frontmatter with `name` and `description` (the trigger). Body holds the skill's full instructions. |
| `scripts/` | Python helper scripts the skill invokes at runtime. |
| `workflow/` | `.mjs` workflow scripts run via the `Workflow` tool. |
| `templates/` | Template files the skill or workflow renders at build time. |
| `reference/` | Reference docs the skill cites or the workflow reads. |
| `*_constants/` | Python package of named constants imported by `scripts/`. |

Skills install to `~/.claude/skills/<skill-name>/` via `packages/claude-dev-env/bin/install.mjs`. See `docs/references/skill-install-system.md` for the install pipeline.

## Shared support code

`_shared/` — support code used by more than one skill. It holds `pr-loop/`, which provides prompt templates and Python helper scripts shared across the PR-loop skills, and `advisor/`, which provides the shared warm-advisor protocol used by `team-advisor` and `orchestrator`.

## Skill groups

**Planning and implementation**
- `anthropic-plan` — creates a source-grounded plan packet before any code changes
- `orchestrator` — turns the session into the advisor-orchestrator: it spawns executor subagents to do the code edits and test runs; hard decisions go to a shared advisor (Claude warm `session-advisor` via SendMessage; Grok self-as-advisor on the orchestrating session)
- `orchestrator-refresh` — sub-skill fired by the `/orchestrator` loop to re-assert the host-matched shared-advisor discipline mid-run (Claude SendMessage; Grok self-as-advisor, no Agent spawn)
- `team-advisor` — binds one advisor at the strongest reachable tier (Claude warm agent; Grok self-as-advisor) and consults it for a second opinion before a big decision, at completion, when stuck, or when reconsidering the approach

**PR review and convergence**
- `autoconverge` — autonomous single-run workflow that drives a PR to ready
- `pr-converge` — paced convergence loop across `ScheduleWakeup` ticks
- `bugteam` — open-loop audit-fix until convergence
- `copilot-review` — requests and polls a GitHub Copilot review
- `copilot-finding-triage` — tiers each Copilot gate finding and routes it (auto-fix or user page)
- `reviewer-gates` — availability gates for external reviewers (opt-out parse, Copilot quota, Bugbot trigger/detect)
- `pr-loop-lifecycle` — opens and closes a PR-loop run (grant, teardown, PR description, revoke, report)
- `pr-loop-cloud-transport` — six-step transport workflow that lets any PR-loop skill run in a session whose `gh` CLI is absent or cannot act on the PR (MCP schema load, origin/HEAD fix, identity rules, the gh-to-MCP substitution matrix, the Copilot status rule, and the post self-check)

**Research and discovery**
- `recall` — retrieves facts from memory files
- `remember` — saves a decision, gotcha, or architectural choice to the Obsidian vault
- `everything-search` — file-system search via the Everything `es.exe` CLI

**Session and workflow management**
- `session-log` — logs a session report to the Obsidian vault
- `session-tidy` — tidies the session folder
- `task-build` — gathers open tasks
- `privacy-hygiene` — full-repo personal-data and secret sweep plus remediation guide
- `update` — updates the dev-env package
- `fresh-branch` — creates a clean branch off main
- `rebase` — rebases onto main
- `usage-pause` — waits out the 5-hour usage window in ScheduleWakeup stages that keep agent contexts warm; probes the OAuth usage endpoint or takes a manual reset override
- `skill-builder` — complete skill-building lifecycle
- `auditing-claude-config` — audits a Claude Code setup for context-budget waste and produces a migration table with savings
