# claude-dev-env

Consistent development standards for Claude Code across every repo. Install once, get TDD enforcement, code quality hooks, specialized agents, and battle-tested rules everywhere.

## Quick Start

### Prerequisites

- **Node.js 18+** (includes `npx`)
- **Python 3.8+** (for hook scripts)
- **Claude Code CLI** installed and working

### Install

```bash
npx claude-dev-env
```

That's it. The installer will:

1. Detect your Python 3 command (`python3`, `python`, or `py -3`)
2. Copy rules, docs, commands, and hooks to `~/.claude/`; copy agents and skills to `~/.agents/` and point `~/.claude/agents` and `~/.claude/skills` at that home
3. Copy hook scripts to `~/.claude/hooks/`
4. Merge hook groups into `~/.claude/settings.json` (preserves your existing hooks)
5. Write a manifest to `~/.claude/.claude-dev-env-manifest.json` for clean uninstall
6. Copy Codex exec-policy files into `~/.codex/rules` (`CODEX_HOME/rules` when that variable is set)
7. Generate Cursor `.mdc` files into `~/.cursor/rules` from the installed Claude rules

### Selective Install

Only want specific tools? Use the `--only` flag with one or more groups:

```bash
npx claude-dev-env --only core             # dev standards, hooks, agents, commands
```

| Group | What's included |
|-------|----------------|
| `core` | Rules, docs, commands, agents, all hooks, Codex exec-policy files |

Run `node bin/install.mjs --help` for the live group list, which also carries any group a
declared dependency package contributes.

The install target comes from the managed root, so the installer reads only flags. A bare
path argument such as `npx claude-dev-env .` carries no meaning: the run lands in
`~/.claude` the same way. Select another root with `--target DIR`, `--profile ID`, or the
`CLAUDE_CONFIG_DIR` environment variable.

### Verify

Start a new Claude Code session. You should see hook activity on your first prompt (code-rules-reminder, hook-structure-context). Run `/sr-loop` to confirm commands loaded.

### Update

Run the same command again. It overwrites existing files and updates hook entries in place:

```bash
npx claude-dev-env
```

### Uninstall

Removes only the files this package installed (tracked via manifest) and cleans hook entries from `settings.json`:

```bash
npx claude-dev-env --uninstall
```

### Bootstrap the project-path registry (one-time, post-install)

The Everything search command and the untracked-repo detector both read `~/.claude/project-paths.json`. That file maps short repository names to absolute paths. It is per-user data and is not committed here.

After installing or updating `claude-dev-env`, run the bootstrap script once to populate the registry by scanning for `.git` directories with Everything's command-line binary:

```bash
python packages/claude-dev-env/scripts/setup_project_paths.py
```

Requirements:

- Everything (from voidtools) installed with its service running
- `es.exe` available on `PATH`

The script discovers candidate repos via `es.exe`, filters out ephemeral locations (`temp`, `tmp`, `worktree`, `node_modules`, `.cache`, `$recycle.bin`), shows the proposed mapping, and writes `~/.claude/project-paths.json` only after you confirm at the prompt. The file is atomically replaced on write and merges with any entries already present.

Once the registry is populated, run:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/everything_search.py" <repo-name> <search arguments>
```

An exact repository name becomes one absolute path. The command then starts `es.exe`. Put the search scope in the first argument. An options-only request exits before `es.exe` starts.

## What This Solves

Without shared config, every repo needs its own `.claude/rules/`, `.claude/hooks/`, `.claude/agents/`, etc. That means:

- Duplicated config across 5+ repos
- Drift when you update standards in one place but forget others
- New repos start with zero guardrails

This package centralizes all general-purpose Claude Code config. Project-specific rules still live in each repo's `.claude/` directory and merge with these.

## What's Included

### Rules

Behavioral rules loaded into every session. These shape how Claude approaches work before any code is written.

| Rule | What it does |
|------|-------------|
| `agent-spawn-protocol` | Check context sufficiency before delegating to an agent |
| `anti-corollary-tests` | Each test carries information; skip corollary matrices |
| `asd-ste100-language` | Plain word choice, sentence style, and tone for user-facing text |
| `ask-user-question-required` | Route every user-directed question through AskUserQuestion |
| `bdd` | Discovery, illustration, and should-style specifications around the TDD loop |
| `claims-as-quotes` | A claim about existing code travels with its path, lines, and quote |
| `cleanup-temp-files` | Remove scratch files after tasks complete |
| `code-standards` | Point at CODE_RULES.md for review and code generation |
| `confirm-implementation-forks` | Ask which path at a fork that changes scope or a hard-to-reverse contract |
| `destructive-commands` | Allowed removal forms, and destructive literals kept out of command strings |
| `doc-inventory-integrity` | A doc that inventories code stays in step with the directory |
| `docstring-prose-matches-implementation` | A docstring's enumeration covers every behavior the body applies |
| `durable-post-artifacts` | Keep volatile local paths out of GitHub posts |
| `explore-thoroughly` | Read before proposing, map patterns before committing |
| `failure-blast-radius` | Name what a raise stops: the run, or one member of a batch |
| `falsify-before-green` | A check's green counts once that check ran red on a named break |
| `file-global-constants` | A module-level constant earns its place with two consumers |
| `filesystem-search` | Every filesystem search names a scope |
| `gh-cli-conventions` | Body content travels by file; paginated reads slurp before they filter |
| `git-workflow` | Draft PRs, stacked PR patterns, review-response protocol |
| `hedging-claims` | State a claim with its evidence, or name it unverified |
| `long-horizon-autonomy` | Carry a long or unwatched run to completion |
| `measurement-denominators` | Every count names what it scanned |
| `nas-ssh-invocation` | Reach the NAS through its runner script |
| `no-cross-skill-duplicate-helpers` | A helper copied between two skill folders is a deliberate choice |
| `orphan-css-class` | Every class name in generated markup has a matching selector |
| `paired-test-coverage` | Every public function in an established suite carries a behavioral test |
| `plain-illustrative-docstrings` | Docstring narrative reads plainly on the first pass |
| `prompt-workflow-context-controls` | Prompt workflows stay low-context |
| `pstack-models` | Portable role requirements for pstack delegation |
| `re-stage-before-commit` | Stage this session's edits right before the commit |
| `research-mode` | Cite sources, say "I don't know", use direct quotes |
| `shell-invocation` | Use pwsh, and keep shell substitution out of Bash commands |
| `testing` | Complete mocks, reference TEST_QUALITY.md |
| `vault-context` | Search prior sessions and decisions before substantive project work |
| `verify-before-asking` | Answer with a tool what a tool can answer |
| `verify-runtime-state` | A runtime verdict rests on a live probe from this session |
| `windows-filesystem-safe` | Safe tree removal for read-only Windows files |
| `workers-done-before-complete` | A task stays open while a worker it spawned still runs |
| `workflow-substitution-slots` | Mark every per-call value in a workflow template |

### Codex exec-policy files

Starlark `*.rules` files Codex loads from `~/.codex/rules`. The package ships `claude-dev-env.rules` so a local `default.rules` stays in place.

### Cursor rule files

The installer runs `sync_to_cursor.py` so each Claude `rules/*.md` file becomes `~/.cursor/rules/<stem>.mdc` with Cursor frontmatter (`alwaysApply` or a `globs` list from Claude `paths:`). Inventory files `CLAUDE.md` and `AGENTS.md` stay out of that folder.

### Docs

Reference documents that rules and agents point to for detailed standards.

| Document | Coverage |
|----------|----------|
| `CODE_RULES.md` | Hook-enforced rules, naming conventions, config patterns, type hints, readability rubric |
| `TEST_QUALITY.md` | Test writing standards, mock completeness, assertion patterns |
| `REACT_PATTERNS.md` | Component architecture, hooks, state management conventions |
| `DJANGO_PATTERNS.md` | Model patterns, view architecture, ORM best practices |
| `BDD_DISCOVERY_PROTOCOL.md` | Example Mapping to find test ideas before code |
| `BDD_SCENARIO_QUALITY.md` | Seven patterns for clear, focused scenarios |
| `BDD_TEST_LAYOUT.md` | Describe, when, and should layout for readable suites |
| `agent-spawn-protocol.md` | Full protocol behind the agent-spawn rule |
| `codex-compatibility.md` | The bridge from this source tree to Codex-compatible output |
| `host-pool-health-monitor.md` | Kernel pool counters and handle pressure on a Windows host |
| `nas-ssh-invocation.md` | Full detail behind the NAS ssh rule |
| `worker-completion-gate.md` | Full detail behind the worker completion rule |
| `wsl-docker-cowork-starter-matrix.md` | Host memory attribution under WSL2 and Docker Desktop |

### Agents (8)

Specialized agent prompts for common development tasks. Claude Code automatically discovers these and makes them available for delegation.

| Agent | Role |
|---------|------|
| `clean-coder` | Primary code-writing agent |
| `code-quality-agent` | Multi-file code quality review |
| `git-commit-crafter` | Conventional commit messages |
| `issue-tracker` | GitHub issue create, update, and close |
| `plan-packet-validator` | Fresh-context plan-packet validator |
| `pr-description-writer` | PR descriptions from the current diff |
| `session-advisor` | Standing reviewer; endorse/correction/plan/stop |
| `skill-writer-agent` | SKILL.md authoring specialist |

### Commands (1)

Slash commands for common workflows.

| Command | Purpose |
|---------|---------|
| `/sr-loop` | Loop /simplify then /code-review --fix until each pass is clean |

### Skills

Each skill lands under the agents home, with a directory pointer at `~/.claude/skills`.
A declared dependency package can add more; `node bin/install.mjs --help` names the groups
that carry them.

| Skill | Purpose |
|-------|---------|
| `cert-classification-rule` | Add or change a Samsung cert-failure classification rule |
| `e-code-review` | Max-recall code review at a selectable effort level |
| `e-simplify` | Cleanup pass on the current diff for reuse, simplification, and efficiency |
| `eli5` | Beginner-friendly presentation with large visuals and minimal text |
| `everything-search` | Fast Windows file search through the Everything es.exe tool |
| `fresh-branch` | Fresh branch from origin/main in an isolated worktree |
| `grok-spawn` | Spawn headless grok worker fleets through preflight and batch spawn |
| `issue-tracker` | File, update, and close GitHub work as one epic with native sub-issues |
| `orchestrator` | Turn the session into an advisor-orchestrator that spawns executor subagents |
| `orchestrator-refresh` | Re-assert orchestrator discipline on a delayed wake |
| `privacy-hygiene` | Full-repo sweep for personal data and secrets before a commit or post |
| `pull-request` | Validate and publish GitHub pull request actions |
| `recovering-codex-startup` | Diagnose Windows Codex startup with fresh read-only process evidence |
| `repairing-hook-boundaries` | Repair Claude and Codex hook failures at the first failing boundary |
| `session-continuity` | Carry session context forward for a clean pickup |
| `skill-builder` | Author a skill package to the house conventions |
| `source-command-logifix` | Restore the Logitech Gaming Software tray icon on Windows |
| `syncing-submodules` | Record a submodule's current commit in its parent repository |
| `task-build` | Gather open session tasks and register them on the task list |
| `team-advisor` | Standing reviewer for a session and the subagents it spawns |
| `test-runner` | Run pytest or Playwright through the repository's test command |
| `usage-pause` | Pause until the usage window resets |
| `windows-scheduled-task` | Register a repeating headless Windows task with a documented teardown |

### Hooks

Automated enforcement that runs on Claude Code events. The installer detects your Python 3 command and rewrites hook paths to absolute `~/.claude/hooks/` paths in `settings.json`.

#### PreToolUse (before tool execution)

| Matcher | Hook | What it does |
|---------|------|-------------|
| Write\|Edit | `write-existing-file-blocker` | Warns before overwriting files that should be edited |
| Write\|Edit | `sensitive-file-protector` | Blocks writes to .env, credentials, and sensitive files |
| Write\|Edit | `hook-format-validator` | Validates hook file format on write |
| Write\|Edit | `run_all_validators` | Runs the full validation suite (30+ checks) |
| Write\|Edit | `code_rules_enforcer` | Blocks CODE_RULES.md violations (comments, magic values, imports) |
| Write\|Edit | `tdd-enforcer` | Prompts TDD confirmation when writing production code |
| Write\|Edit | `state-description-blocker` | Blocks historical/comparative language in comments and .md files |
| Edit | `refactor-guard` | Ensures refactoring happens only after green tests |
| Edit | `migration-safety-advisor` | Warns about risky database migration patterns |
| Bash | `destructive-command-blocker` | Blocks rm -rf, git reset --hard, and other destructive commands |
| Bash | `block-main-commit` | Blocks direct commits to main/master branch |
| Bash | `test-preflight-check` | Validates server health and database before test runs |
| Task\|Agent | `parallel-task-blocker` | Limits concurrent Task/Agent delegations |
| AskUserQuestion | `attention-needed-notify` | Desktop notification when Claude needs your input |

#### Other Events

| Event | Hook | What it does |
|-------|------|-------------|
| SessionStart | `plugin-data-dir-cleanup` | Cleans stale plugin data on session start |
| Stop | `attention-needed-notify` | Desktop notification when Claude stops |
| Stop | `hedging-language-blocker` | Blocks responses with hedging language (anti-hallucination) |
| SessionEnd | `session-end-cleanup` | Cleans temporary state on session end |
| ConfigChange | `config-change-guard` | Guards against accidental settings changes |
| PostToolUse (Write\|Edit) | `mypy_validator` | Runs mypy type checking after file writes |
| PostToolUse (Write\|Edit) | `auto-formatter` | Auto-formats Python (ruff/black) and JS (prettier) on write |
| PostToolUse (Agent\|Task) | `investigation-tracker-reset` | Resets investigation tracker after delegation |
| Notification | `claude-notification-handler` | Routes Claude Code notifications to desktop |

#### Validators Module

The `hooks/validators/` directory contains 30+ individual check modules with a full test suite:

Abbreviations, code quality, comments, file structure, git conventions, magic values, mypy integration, PR references, Python antipatterns, Python style, React patterns, ruff integration, security, TODO tracking, type safety, useless test detection, and more.

## Also Available as a Plugin

If you prefer the Claude Code plugin system over npm:

```bash
claude plugin install jl-cmd/claude-dev-env
```

## Recommended Companion Plugins

These plugins provide additional skills and capabilities that complement this config:

```bash
claude plugin install anthropics/claude-code-plugins        # Official: frontend-design, code-review, playwright, hookify, skill-creator, claude-md-management, serena, pyright-lsp, typescript-lsp, claude-code-setup
claude plugin install anthropics/claude-code-workflows      # Official: python-dev, ui-design, unit-testing, context-management, agent-teams, and more
claude plugin install jl-cmd/claude-workflow                # Workflow definitions with YAML schemas
```

Run `node bin/install.mjs --help` for the group list this build defines.

GSD (project management) is available as an npm package:
```bash
npx get-shit-done-cc
```

## Customization

Installed rules merge with your project's `.claude/` config. To override a rule for a specific project, create a rule with the same filename in your project's `.claude/rules/` directory.

Installed hooks run alongside any hooks already in your `settings.json` or `settings.local.json`. The installer preserves existing hook entries.

## Requirements

- Node.js 18+ (for the installer)
- Python 3.8+ (for hooks)
- Claude Code CLI

## License

MIT
