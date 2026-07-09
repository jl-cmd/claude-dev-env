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
- `implement` — structured implementation from an existing plan packet
- `bdd-protocol` — BDD depth: Example Mapping, scenario quality, outside-in layout
- `verified-build` — build + test loop that gates on a verifier verdict
- `orchestrator` — turns the session into the advisor-orchestrator: it spawns executor subagents to do the code edits and test runs; hard decisions go to a shared advisor (Claude warm `session-advisor` via SendMessage; Grok self-as-advisor on the orchestrating session)
- `orchestrator-refresh` — sub-skill fired by the `/orchestrator` loop to re-assert the host-matched shared-advisor discipline mid-run (Claude SendMessage; Grok self-as-advisor, no Agent spawn)
- `team-advisor` — binds one advisor at the strongest reachable tier (Claude warm agent; Grok self-as-advisor) and consults it for a second opinion before a big decision, at completion, when stuck, or when reconsidering the approach

**PR review and convergence**
- `autoconverge` — autonomous single-run workflow that drives a PR to ready
- `pr-converge` — paced convergence loop across `ScheduleWakeup` ticks
- `bugteam` — open-loop audit-fix until convergence
- `pr-review-responder` — fetches all reviewer comments and replies systematically
- `pr-consistency-audit` — cross-file consistency check on a PR diff
- `copilot-review` — requests and polls a GitHub Copilot review
- `findbugs` / `fixbugs` — find bugs then fix them in separate passes
- `reviewer-gates` — availability gates for external reviewers (opt-out parse, Copilot quota, Bugbot trigger/detect)
- `pr-scope-resolve` — one resolution ladder for a PR-loop skill's audit/fix target
- `pr-fix-protocol` — fix, reply, and resolve reviewer findings; the unresolved-thread sweep
- `post-audit-findings` — publishes an audit pass as one GitHub PR review
- `pr-loop-lifecycle` — opens and closes a PR-loop run (grant, teardown, PR description, revoke, report)
- `code` — strict-mode code generation session

**Research and discovery**
- `deep-research` — multi-source research with citation
- `research-mode` — activates anti-hallucination discipline for a session
- `recall` — retrieves facts from memory files
- `remember` — saves a decision, gotcha, or architectural choice to the Obsidian vault
- `everything-search` — file-system search via the Everything `es.exe` CLI
- `caveman` — trims noise from a draft artifact

**Session and workflow management**
- `session-log` — logs a session report to the Obsidian vault
- `session-tidy` — tidies the session folder
- `bg-agent` — launches a background agent
- `task-build` — gathers open tasks
- `update` — updates the dev-env package
- `gh-paginate` — safe `gh api` pagination patterns
- `fresh-branch` — creates a clean branch off main
- `rebase` — rebases onto main
- `gotcha` — records a hard-won lesson to memory
- `logifix` — restores the Logitech Gaming Software (LCore) tray icon when it disappears on Windows
- `refine` — refinement pass on an artifact
- `structure-prompt` — structures a freeform prompt
- `monitor-open-prs` — polls open PRs for status
- `pre-compact` — compact-safe session handoff
- `qbug` — required baseline PR audit; one clean-coder subagent loops audit → fix → commit → push until clean or stuck
- `usage-pause` — waits out the 5-hour usage window in ScheduleWakeup stages that keep agent contexts warm; probes the OAuth usage endpoint or takes a manual reset override
- `skill-builder` — complete skill-building lifecycle
- `auditing-claude-config` — audits a Claude Code setup for context-budget waste and produces a migration table with savings
- `log-audit` — background agent that audits this repo's own logs for recurring errors and timing regressions and files grouped fixes
