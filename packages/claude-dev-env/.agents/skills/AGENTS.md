# Skills Directory

Each skill is a self-contained folder Claude Code loads on demand. At startup, only the skill's `name` and `description` metadata load. The full `SKILL.md` body and any support files load only when a skill becomes relevant to the conversation.

Skill bodies use `~/.claude/rules/asd-ste100-language.md` for user-facing word choice, sentence style, tone, punctuation, and prose form. Each skill keeps its capability-specific output contract.

## Skill folder convention

| Item | Role |
|---|---|
| `SKILL.md` | Required entry point. YAML frontmatter with `name` and `description` (the trigger). Body holds the skill's full instructions. |
| `scripts/` | Python helper scripts the skill invokes at runtime. |
| `workflow/` | `.mjs` workflow scripts run via the `Workflow` tool. |
| `templates/` | Template files the skill or workflow renders at build time. |
| `reference/` | Reference docs the skill cites or the workflow reads. |
| `*_constants/` | Python package of named constants imported by `scripts/`. |

Skills install to `~/.agents/skills/<skill-name>/` via `packages/claude-dev-env/bin/install.mjs`. Claude Code looks them up at `~/.claude/skills/<skill-name>/`, a directory pointer to that folder. See `docs/references/skill-install-system.md` for the install pipeline.

Retired skills live in `../skills-archived/` — versioned in the repo, not installed, not under the `.claude/skills` pointer. See `../skills-archived/AGENTS.md` for the archive index.

## Shared support code

**`skills/_shared/`** — skill-local PR-loop helpers plus `@` stubs that name
canonical homes under **`@~/.claude/_shared/`** (advisor protocol, PR-loop
contracts, runtime scripts). Map: `skills/_shared/.claude/CLAUDE.md`. End-of-run gotchas: `skills/_shared/end-of-run-gotcha-recommendations.md`.

## Skill groups

**Planning and implementation**
- `orchestrator` — turns the session into the orchestrator: it spawns executor subagents to do the code edits and test runs; hard decisions go to a shared advisor
- `orchestrator-refresh` — re-asserts orchestrator discipline on a one-shot delayed wake
- `team-advisor` — binds one advisor at the strongest reachable tier
- `grok-spawn` — orchestrator playbook for fleets of headless grok CLI workers

**PR review and convergence**

- `shared-extraction-audit` — audits workflow packages for helpers that belong in shared libraries; extracts in small tested CLs
- `name-by-capability-audit` — audits PR paths/titles for driver/motive words on reusable capability code
- `review-tier` — classifies `review_tier_constants` from change axes, hard triggers, and user overrides
- `review-router` — resolves and arms one supported `route_review_config` route through the registered Agent|Task gate
- `pr-cleanup` — one-agent end-to-end PR cleanup: extraction → naming → sr-loop → small-cl; apply and validate fixes as they return
- `autoconverge` — autonomous single-run workflow that drives a PR to ready
- `e-code-review` — max-recall code review at a selectable effort level
- `e-simplify` — cleanup-only pass on the current diff
- `small-cl` — the Small CLs guide for scope and split decisions

**Research and discovery**
- `everything-search` — file-system search via the Everything `es.exe` CLI on Windows
- `eli5` — owns beginner framing, large visuals, minimal text, one stable self-contained HTML artifact, update-in-place continuity, and sharing

**Source commands**
- `source-command-logifix` — restore the Logitech Gaming Software tray icon on Windows
- `source-command-sr-loop` — converging cleanup loop: simplify then code-review until clean

**Samsung certification**
- `cert-classification-rule` — add or change a Samsung cert-failure classification rule

**Session and workflow management**
- `session-log` — logs a session report to the Obsidian vault
- `session-tidy` — tidies the session folder
- `task-build` — gathers open tasks
- `issue-tracker` — GitHub epic and sub-issue workflow
- `privacy-hygiene` — full-repo personal-data and secret sweep
- `update` — fast-forwards a local `main` branch
- `fresh-branch` — creates a clean branch off main in a worktree
- `rebase` — rebases onto main with verification gates
- `usage-pause` — waits out the usage window in ScheduleWakeup stages
- `skill-builder` — complete skill-building lifecycle
- `run-claude-dev-env` — build, install, and test the claude-dev-env installer
- `prototype` — isolated hookless worktree sandbox for proof-of-concept builds
